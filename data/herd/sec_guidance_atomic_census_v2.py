"""가격을 열지 않고 SEC 가이던스 atomic source-review 모집단을 잠근다."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import html
import json
from pathlib import Path

import pandas as pd


PROTOCOL = Path(__file__).with_suffix(".json")
LOCATOR = [
    "source_sha256",
    "range_offset",
    "metric",
    "fiscal_period",
    "accounting_basis",
    "metric_subtype",
    "unit",
    "lower_bound",
    "upper_bound",
]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _verify_input(item: dict) -> Path:
    path = Path(item["path"])
    if _sha256(path) != item["sha256"]:
        raise ValueError(f"locked input changed: {path}")
    return path


def _normalize_cik(series: pd.Series) -> pd.Series:
    return series.astype(str).str.replace(r"\.0$", "", regex=True).str.zfill(10)


def _text(series: pd.Series) -> pd.Series:
    return series.fillna("").astype(str).str.strip()


def _pair_stats(frame: pd.DataFrame, identity: list[str]) -> tuple[int, int]:
    total = 0
    tickers: set[str] = set()
    for _, group in frame.groupby(identity, dropna=False):
        pair_count = max(0, group["accession_number"].astype(str).nunique() - 1)
        total += pair_count
        if pair_count:
            tickers.update(group["ticker"].dropna().astype(str))
    return total, len(tickers)


def _source_index(protocol: dict) -> dict[str, Path]:
    result: dict[str, Path] = {}
    for corpus in sorted(Path().glob(protocol["source_corpus_glob"])):
        index_path = corpus / "index.csv"
        if not index_path.is_file():
            continue
        index = pd.read_csv(index_path, usecols=["source_sha256", "path"])
        for row in index.itertuples(index=False):
            path = corpus / str(row.path)
            if path.is_file():
                result.setdefault(str(row.source_sha256), path)
    return result


def build(protocol: dict) -> tuple[pd.DataFrame, dict]:
    existing_path = _verify_input(protocol["existing_atomic_bindings"])
    existing = pd.read_csv(existing_path, dtype={"cik": str})
    candidates = []
    input_hashes = {str(existing_path): _sha256(existing_path)}
    for item in protocol["candidate_sources"]:
        path = _verify_input(item)
        input_hashes[str(path)] = _sha256(path)
        frame = pd.read_csv(path, dtype={"cik": str})
        frame["candidate_source"] = str(path)
        candidates.append(frame)
    candidate = pd.concat(candidates, ignore_index=True, sort=False)

    required = protocol["required_semantics"]
    missing_columns = sorted(set(required) - set(candidate.columns))
    if missing_columns:
        raise ValueError(f"candidate columns missing: {missing_columns}")
    candidate["cik"] = _normalize_cik(candidate["cik"])
    existing["cik"] = _normalize_cik(existing["cik"])
    for column in [
        "ticker", "accession_number", "accepted_at", "source_url", "source_sha256",
        "metric", "fiscal_period", "accounting_basis", "metric_subtype", "unit",
        "source_excerpt", "numeric_role", "semantic_role",
    ]:
        candidate[column] = _text(candidate[column])
    complete = candidate[required].apply(
        lambda column: column.notna() & column.astype(str).str.strip().ne("")
    ).all(axis=1)
    contract = protocol["candidate_contract"]
    strict = candidate.loc[
        complete
        & candidate["numeric_role"].eq(contract["numeric_role"])
        & candidate["semantic_role"].eq(contract["semantic_role"])
        & ~candidate["accounting_basis"].isin(contract["excluded_accounting_basis"])
        & ~candidate["metric_subtype"].isin(contract["excluded_metric_subtype"])
    ].copy()
    strict = strict.drop_duplicates(LOCATOR, keep="first")

    existing_locator = set(
        map(tuple, existing.reindex(columns=LOCATOR).fillna("").itertuples(index=False, name=None))
    )
    strict = strict.loc[
        ~strict.reindex(columns=LOCATOR).fillna("").apply(tuple, axis=1).isin(existing_locator)
    ].copy()

    source_paths = _source_index(protocol)
    strict["source_path"] = strict["source_sha256"].map(
        lambda value: str(source_paths.get(value, ""))
    )
    strict["source_available"] = strict["source_path"].ne("")
    if not strict["source_available"].all():
        missing = strict.loc[~strict["source_available"], "source_sha256"].unique().tolist()
        raise ValueError(f"source documents missing for {len(missing)} locked candidates")

    identity = protocol["pair_identity"]
    combined = pd.concat(
        [
            existing.loc[existing["pair_eligible"].eq(True)].assign(_candidate=False),
            strict.assign(_candidate=True),
        ],
        ignore_index=True,
        sort=False,
    )
    viable_keys = set()
    for key, group in combined.groupby(identity, dropna=False):
        if group["accession_number"].nunique() >= 2 and group["_candidate"].any():
            viable_keys.add(key if isinstance(key, tuple) else (key,))
    strict["_identity"] = strict.apply(lambda row: tuple(row[column] for column in identity), axis=1)
    review = strict.loc[strict["_identity"].isin(viable_keys)].drop(columns="_identity").copy()
    review["review_priority"] = review.apply(
        lambda row: hashlib.sha256(
            "|".join(str(row[column]) for column in [
                "cik", "metric", "fiscal_period", "accounting_basis", "metric_subtype",
                "unit", "accepted_at", "source_sha256", "range_offset",
            ]).encode()
        ).hexdigest(),
        axis=1,
    )
    review = review.sort_values(
        ["ticker", "metric", "fiscal_period", "accepted_at", "review_priority"]
    ).reset_index(drop=True)
    review.insert(0, "review_id", [f"SGA2-{index:04d}" for index in range(1, len(review) + 1)])
    review["review_decision"] = contract["all_rows_start_as"]
    review["review_reason"] = ""
    review["reviewer"] = ""
    review["reviewed_at"] = ""

    potential = pd.concat(
        [
            existing.loc[existing["pair_eligible"].eq(True)],
            review,
        ],
        ignore_index=True,
        sort=False,
    )
    current_pairs, current_pair_tickers = _pair_stats(
        existing.loc[existing["pair_eligible"].eq(True)], identity
    )
    potential_pairs, potential_pair_tickers = _pair_stats(potential, identity)
    report = {
        "report_version": "herd-sec-guidance-atomic-census-v2",
        "status": "LOCKED_PENDING_SOURCE_REVIEW",
        "existing_pair_eligible_bindings": int(existing["pair_eligible"].sum()),
        "existing_revision_pairs": current_pairs,
        "existing_revision_pair_tickers": current_pair_tickers,
        "raw_candidate_rows": sum(
            len(pd.read_csv(item["path"])) for item in protocol["candidate_sources"]
        ),
        "strict_unique_candidate_rows": len(strict),
        "locked_review_rows": len(review),
        "locked_review_tickers": int(review["ticker"].nunique()),
        "locked_review_accessions": int(review["accession_number"].nunique()),
        "potential_revision_pairs_if_all_valid": potential_pairs,
        "potential_revision_pair_tickers_if_all_valid": potential_pair_tickers,
        "potential_pair_uplift_if_all_valid": potential_pairs - current_pairs,
        "coverage_target_revision_pairs": protocol["coverage_gate"][
            "minimum_source_reviewed_revision_pairs"
        ],
        "source_documents_available": int(review["source_available"].sum()),
        "all_rows_pending": bool(review["review_decision"].eq("PENDING").all()),
        "source_review_complete": False,
        "price_outcomes_observed": False,
        "direction_hypothesis_preregistered": False,
        "operational_action_ratio": 0.0,
        "input_hashes": input_hashes,
        "next_decision": "COMPLETE_ATOMIC_SOURCE_REVIEW",
    }
    if potential_pairs < protocol["coverage_gate"]["minimum_source_reviewed_revision_pairs"]:
        report["status"] = "STOP_INSUFFICIENT_POTENTIAL_PAIR_COVERAGE"
        report["next_decision"] = "SEEK_NEW_MANAGEMENT_GUIDANCE_SOURCE_DOCUMENTS"
    return review, report


def render_workbench(review: pd.DataFrame, output: Path) -> None:
    cards = []
    for row in review.itertuples(index=False):
        source_path = Path(row.source_path)
        with gzip.open(source_path, "rb") as source:
            digest = hashlib.sha256(source.read()).hexdigest()
        integrity = "OK" if digest == row.source_sha256 else "HASH_MISMATCH"
        cards.append(
            "<article>"
            f"<h2>{html.escape(row.review_id)} · {html.escape(row.ticker)} · "
            f"{html.escape(row.metric)} · {html.escape(row.fiscal_period)}</h2>"
            f"<p>{html.escape(row.accounting_basis)} · {html.escape(row.metric_subtype)} · "
            f"{html.escape(row.unit)} · {row.lower_bound:g}–{row.upper_bound:g}</p>"
            f"<blockquote>{html.escape(row.source_excerpt)}</blockquote>"
            f"<p><a href=\"{html.escape(row.source_url)}\">SEC 원문</a> · "
            f"{html.escape(row.accepted_at)} · {integrity}</p>"
            "<p class=\"decision\">VALID / INVALID / AMBIGUOUS</p>"
            "</article>"
        )
    document = """<!doctype html><html lang="ko"><meta charset="utf-8">
<title>SEC Guidance Atomic Census V2</title>
<style>
body{font:14px/1.55 system-ui;background:#0b111b;color:#dbe5f5;margin:32px auto;max-width:1100px}
article{border:1px solid #26344a;border-radius:12px;padding:20px;margin:16px 0;background:#111a28}
h2{font-size:17px}blockquote{color:#b8c7dc;border-left:3px solid #4d8cff;margin:16px 0;padding:8px 16px}
a{color:#74a7ff}.decision{letter-spacing:.08em;color:#ffb35c}
</style><body><h1>SEC Guidance Atomic Census V2</h1>
<p>가격 결과 비개방 · 각 행의 지표/기간/회계기준/범위/현재 전망 여부를 원문으로 판정</p>
""" + "\n".join(cards) + "</body></html>\n"
    output.write_text(document, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--review", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--workbench", type=Path)
    args = parser.parse_args()
    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    review, report = build(protocol)
    review.to_csv(args.review, index=False, float_format="%.12g", lineterminator="\n")
    report["protocol_sha256"] = _sha256(PROTOCOL)
    report["review_sha256"] = _sha256(args.review)
    args.report.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    if args.workbench:
        render_workbench(review, args.workbench)
        report["workbench_sha256"] = _sha256(args.workbench)
        args.report.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
