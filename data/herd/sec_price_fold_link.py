"""가격 ticker를 SEC CIK·접수 시각 사실·Walk-forward fold에 연결한다."""

from __future__ import annotations

import argparse
import csv
import json
from datetime import date, datetime, time, timezone
from pathlib import Path

from herd.sec_point_in_time_fundamentals import (
    build_acceptance_index,
    facts_as_of,
    normalize_companyfacts,
)

NON_CORPORATE_FUNDS = {"DIA", "IWM", "QQQ", "SPY"}


class SecPriceFoldLinkError(RuntimeError):
    pass


def _read_csv(path: Path) -> list[dict]:
    with Path(path).open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _current_cik_index(rows: list[dict]) -> dict[str, dict]:
    grouped: dict[str, list[dict]] = {}
    for row in rows:
        grouped.setdefault(row["ticker"].upper(), []).append(row)
    index = {}
    for ticker, matches in grouped.items():
        ciks = {f"{int(row['cik']):010d}" for row in matches if row["cik"]}
        if len(ciks) == 1:
            index[ticker] = {
                "cik": next(iter(ciks)),
                "company_name": matches[0].get("company_name", ""),
                "mapping_status": "UNIQUE_CURRENT_CIK",
            }
        elif len(ciks) > 1:
            index[ticker] = {
                "cik": "",
                "company_name": "",
                "mapping_status": "AMBIGUOUS_CURRENT_CIK",
            }
    return index


def _load_cik_facts(
    corpora: list[Path],
    cik: str,
    *,
    filed_from: date,
    filed_to: date,
) -> tuple[list[dict], str]:
    raw = next(
        (
            Path(corpus) / "raw"
            for corpus in corpora
            if (
                Path(corpus)
                / "raw"
                / f"CIK{cik}-submissions.json"
            ).is_file()
        ),
        None,
    )
    if raw is None:
        return [], "SUBMISSIONS_MISSING"
    submissions_path = raw / f"CIK{cik}-submissions.json"
    facts_path = raw / f"CIK{cik}-companyfacts.json"
    if not submissions_path.is_file():
        return [], "SUBMISSIONS_MISSING"
    if not facts_path.is_file():
        return [], "COMPANYFACTS_MISSING"
    payloads = [json.loads(submissions_path.read_text(encoding="utf-8"))]
    payloads.extend(
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted(raw.glob(f"CIK{cik}-history-*.json"))
    )
    acceptance = build_acceptance_index(payloads)
    facts, audit = normalize_companyfacts(
        json.loads(facts_path.read_text(encoding="utf-8")),
        acceptance,
        strict_acceptance=True,
        filed_from=filed_from,
        filed_to=filed_to,
    )
    if audit["missing_acceptances"]:
        return facts, "MISSING_ACCEPTANCE_LINKS"
    return facts, "PIT_FACTS_READY"


def build_links(
    price_manifest: dict,
    ticker_cik_rows: list[dict],
    corpus: Path | list[Path],
    folds: list[dict],
) -> tuple[list[dict], dict]:
    tickers = price_manifest.get("completed_tickers", [])
    if not tickers or not folds:
        raise SecPriceFoldLinkError("price tickers and folds are required")
    cik_index = _current_cik_index(ticker_cik_rows)
    corpora = (
        [Path(item) for item in corpus]
        if isinstance(corpus, list)
        else [Path(corpus)]
    )
    filed_from = min(
        date.fromisoformat(fold["train_start"]) for fold in folds
    )
    filed_to = max(
        date.fromisoformat(fold["test_end"]) for fold in folds
    )
    rows = []
    cache: dict[str, tuple[list[dict], str]] = {}
    for ticker in sorted(tickers):
        if ticker in NON_CORPORATE_FUNDS:
            for fold in folds:
                rows.append({
                    "ticker": ticker,
                    "asset_type": "ETF",
                    "cik": "",
                    "fold_id": fold["fold_id"],
                    "as_of": fold["test_start"],
                    "available_fact_rows": 0,
                    "available_accessions": 0,
                    "available_concepts": 0,
                    "status": "NOT_APPLICABLE_ETF",
                })
            continue
        mapping = cik_index.get(ticker)
        if not mapping or not mapping["cik"]:
            status = (
                mapping["mapping_status"]
                if mapping
                else "NO_CURRENT_CIK"
            )
            for fold in folds:
                rows.append({
                    "ticker": ticker,
                    "asset_type": "EQUITY",
                    "cik": "",
                    "fold_id": fold["fold_id"],
                    "as_of": fold["test_start"],
                    "available_fact_rows": 0,
                    "available_accessions": 0,
                    "available_concepts": 0,
                    "status": status,
                })
            continue
        cik = mapping["cik"]
        if cik not in cache:
            cache[cik] = _load_cik_facts(
                corpora,
                cik,
                filed_from=filed_from,
                filed_to=filed_to,
            )
        facts, corpus_status = cache[cik]
        for fold in folds:
            boundary = datetime.combine(
                datetime.fromisoformat(fold["test_start"]).date(),
                time.min,
                tzinfo=timezone.utc,
            )
            available = facts_as_of(facts, boundary)
            status = corpus_status
            if status == "PIT_FACTS_READY" and not available:
                status = "NO_FACTS_BEFORE_FOLD"
            rows.append({
                "ticker": ticker,
                "asset_type": "EQUITY",
                "cik": cik,
                "fold_id": fold["fold_id"],
                "as_of": fold["test_start"],
                "available_fact_rows": len(available),
                "available_accessions": len({
                    row["accession_number"] for row in available
                }),
                "available_concepts": len({
                    (row["taxonomy"], row["concept"])
                    for row in available
                }),
                "status": status,
            })

    equity_rows = [row for row in rows if row["asset_type"] == "EQUITY"]
    ready_rows = [
        row for row in equity_rows if row["status"] == "PIT_FACTS_READY"
    ]
    latest_fold = max(row["fold_id"] for row in equity_rows)
    latest = [row for row in equity_rows if row["fold_id"] == latest_fold]
    ready_tickers = {
        row["ticker"] for row in latest if row["status"] == "PIT_FACTS_READY"
    }
    equity_tickers = {row["ticker"] for row in latest}
    statuses = {}
    for row in latest:
        statuses[row["status"]] = statuses.get(row["status"], 0) + 1
    return rows, {
        "format_version": "herd-sec-price-fold-link-v1",
        "price_snapshot_id": price_manifest.get("snapshot_id"),
        "folds": len(folds),
        "equity_tickers": len(equity_tickers),
        "etf_tickers": len(set(tickers) & NON_CORPORATE_FUNDS),
        "latest_fold": latest_fold,
        "latest_fold_ready_tickers": len(ready_tickers),
        "latest_fold_coverage": (
            len(ready_tickers) / len(equity_tickers)
            if equity_tickers
            else 0
        ),
        "all_fold_ready_rows": len(ready_rows),
        "all_fold_equity_rows": len(equity_rows),
        "latest_fold_statuses": statuses,
        "research_ready": bool(equity_tickers)
        and len(ready_tickers) == len(equity_tickers),
    }


def write_links(path: Path, rows: list[dict]) -> None:
    if not rows:
        raise SecPriceFoldLinkError("no link rows")
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with Path(path).open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def collection_queue(rows: list[dict]) -> list[dict]:
    queued = {}
    for row in rows:
        if row["asset_type"] != "EQUITY" or not row["cik"]:
            continue
        if row["status"] not in {
            "SUBMISSIONS_MISSING",
            "COMPANYFACTS_MISSING",
        }:
            continue
        queued[(row["ticker"], row["cik"])] = {
            "ticker": row["ticker"],
            "cik": row["cik"],
            "cik_link_status": "UNIQUE_CIK_NAME_CANDIDATE",
            "collection_reason": row["status"],
        }
    return [queued[key] for key in sorted(queued)]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("price_manifest", type=Path)
    parser.add_argument("ticker_cik", type=Path)
    parser.add_argument("sec_corpus", type=Path)
    parser.add_argument("folds", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument(
        "--additional-corpus",
        type=Path,
        action="append",
        default=[],
    )
    parser.add_argument("--collection-queue", type=Path)
    args = parser.parse_args()
    rows, audit = build_links(
        json.loads(args.price_manifest.read_text(encoding="utf-8")),
        _read_csv(args.ticker_cik),
        [args.sec_corpus, *args.additional_corpus],
        _read_csv(args.folds),
    )
    write_links(args.output, rows)
    if args.collection_queue:
        write_links(args.collection_queue, collection_queue(rows))
    print(json.dumps(audit, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
