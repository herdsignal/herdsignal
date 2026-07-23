"""사람이 원문 판정한 VALID 행만 불변 SEC 가이던스 fact로 승격한다."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd


PROTOCOL = Path(__file__).with_suffix(".json")
LOCATOR = ["source_sha256", "source_kind", "block_path", "source_structure", "range_offset"]
SEMANTIC_KEY = ["metric", "fiscal_period", "accounting_basis", "metric_subtype", "unit"]
BOUNDS = ["lower_bound", "upper_bound"]
OUTPUT_COLUMNS = [
    "binding_id", "ticker", "cik", "accession_number", "accepted_at", "document_name",
    "source_url", "source_sha256", "source_kind", "block_path", "source_structure",
    "range_offset", "metric", "fiscal_period", "accounting_basis", "metric_subtype",
    "unit", "lower_bound", "upper_bound", "midpoint", "review_id", "reviewer",
    "reviewed_at", "review_ledger", "review_ledger_sha256", "semantic_locator_collision",
    "pair_eligible", "atomic_binding_authority", "direction_authority", "veto_authority",
]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _text(value: object) -> str:
    return "" if pd.isna(value) else str(value).strip()


def build(protocol: dict) -> tuple[pd.DataFrame, dict]:
    source_review_report = {}
    if protocol.get("source_review_report"):
        source_review_report_path = Path(protocol["source_review_report"])
        source_review_report = json.loads(source_review_report_path.read_text(encoding="utf-8"))
        if not source_review_report.get("source_review_gate_passed", False):
            raise ValueError("source review gate did not pass")
    frames = []
    ledger_hashes = {}
    for name in protocol["review_ledgers"]:
        path = Path(name)
        digest = _sha256(path)
        ledger_hashes[name] = digest
        if (
            name == protocol.get("gated_review_ledger")
            and digest != source_review_report.get("reviewed_sha256")
        ):
            raise ValueError("gated review ledger hash differs from source review report")
        frame = pd.read_csv(path, dtype={"cik": str})
        frame["review_ledger"] = name
        frame["review_ledger_sha256"] = digest
        frames.append(frame)
    reviewed = pd.concat(frames, ignore_index=True, sort=False)
    valid = reviewed.loc[reviewed["review_decision"].eq("VALID")].copy()
    missing_required = valid[protocol["required_fields"]].apply(
        lambda column: column.isna() | column.astype(str).str.strip().eq("")
    ).any(axis=1)
    if missing_required.any():
        ids = valid.loc[missing_required, "review_id"].astype(str).tolist()
        raise ValueError(f"VALID bindings have missing provenance or semantics: {ids}")
    for column in [*LOCATOR, "metric_subtype"]:
        if column not in valid:
            valid[column] = ""
        valid[column] = valid[column].map(_text)
    valid["cik"] = valid["cik"].astype(str).str.replace(r"\.0$", "", regex=True).str.zfill(10)
    valid["midpoint"] = (valid["lower_bound"].astype(float) + valid["upper_bound"].astype(float)) / 2

    locator_semantic = [*LOCATOR, *SEMANTIC_KEY]
    collision_keys = set()
    for key, group in valid.groupby(locator_semantic, dropna=False):
        if len(group[BOUNDS].drop_duplicates()) > 1:
            collision_keys.add(key if isinstance(key, tuple) else (key,))
    valid["semantic_locator_collision"] = valid.apply(
        lambda row: tuple(row[column] for column in locator_semantic) in collision_keys,
        axis=1,
    )
    invalid_basis = set(protocol["pair_ineligible_accounting_basis"])
    invalid_subtype = set(protocol["pair_ineligible_metric_subtype"])
    valid["pair_eligible"] = (
        ~valid["semantic_locator_collision"]
        & ~valid["accounting_basis"].isin(invalid_basis)
        & ~valid["metric_subtype"].isin(invalid_subtype)
    )
    valid["binding_id"] = valid.apply(
        lambda row: hashlib.sha256("|".join(
            _text(row[column]) for column in [
                "source_sha256", "range_offset", *SEMANTIC_KEY, *BOUNDS, "review_id"
            ]
        ).encode()).hexdigest(),
        axis=1,
    )
    valid["atomic_binding_authority"] = "SOURCE_REVIEWED_FACT_ONLY"
    valid["direction_authority"] = False
    valid["veto_authority"] = False
    output = valid[OUTPUT_COLUMNS].sort_values(["accepted_at", "ticker", "binding_id"]).reset_index(drop=True)
    if output["binding_id"].duplicated().any():
        raise ValueError("atomic binding id collision")
    report = {
        "report_version": protocol.get(
            "report_version", "herd-sec-guidance-atomic-bindings-v1"
        ),
        "review_rows_audited": len(reviewed),
        "valid_rows_promoted": len(output),
        "distinct_tickers": int(output["ticker"].nunique()),
        "distinct_accessions": int(output["accession_number"].nunique()),
        "semantic_locator_collision_rows": int(output["semantic_locator_collision"].sum()),
        "pair_eligible_rows": int(output["pair_eligible"].sum()),
        "direction_authorized_rows": int(output["direction_authority"].sum()),
        "veto_authorized_rows": int(output["veto_authority"].sum()),
        "unreviewed_v10_rows_promoted": 0,
        "source_fact_authority_only": True,
        "ready_for_revision_pair_build": bool(output["pair_eligible"].any()),
        "ready_for_direction_research": False,
        "ledger_hashes": ledger_hashes,
        "source_review_report_sha256": (
            _sha256(Path(protocol["source_review_report"]))
            if protocol.get("source_review_report") else None
        ),
        "operational_action_ratio": 0.0,
    }
    return output, report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bindings", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    protocol = json.loads(PROTOCOL.read_text())
    bindings, report = build(protocol)
    bindings.to_csv(args.bindings, index=False, float_format="%.12g", lineterminator="\n")
    report["protocol_sha256"] = _sha256(PROTOCOL)
    report["bindings_sha256"] = _sha256(args.bindings)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
