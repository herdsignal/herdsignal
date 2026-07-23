"""SEC 표적 cover 원장 V4로 FINRA ticker-date PIT CIK coverage를 재감사한다."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from herd.finra_short_interest_coverage_audit_v1 import (
    MANIFEST,
    PROTOCOL as FINRA_PROTOCOL,
    ROOT,
    _sha256,
    audit,
)


SEC_PROTOCOL = Path(__file__).with_name("sec_time_valid_ticker_cik_ledger_v4.json")
SEC_REPORT = ROOT / "data/reports/sec_time_valid_ticker_cik_ledger_v4.json"
SEC_LEDGER = ROOT / "data/reports/sec_time_valid_ticker_cik_intervals_v4.csv"
REPORT = ROOT / "data/reports/finra_short_interest_coverage_audit_v4.json"
DETAIL = ROOT / "data/reports/finra_short_interest_ticker_coverage_v4.csv"


class FinraCoverageV4Error(RuntimeError):
    pass


def load_sec_intervals(
    protocol_path: Path = SEC_PROTOCOL,
    ledger_report_path: Path = SEC_REPORT,
    ledger_path: Path = SEC_LEDGER,
) -> tuple[list[dict], dict]:
    report = json.loads(ledger_report_path.read_text(encoding="utf-8"))
    if report["protocol_sha256"] != _sha256(protocol_path):
        raise FinraCoverageV4Error("SEC V4 protocol lineage mismatch")
    if report["ledger_sha256"] != _sha256(ledger_path):
        raise FinraCoverageV4Error("SEC V4 interval ledger hash mismatch")
    with ledger_path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    intervals = [
        {
            "ticker": row["reported_symbols"],
            "canonical_symbol": row["canonical_symbol"],
            "cik": row["cik"].zfill(10),
            "valid_from": row["valid_from"],
            "valid_to": row["valid_to"],
            "source": row["boundary_sources"],
        }
        for row in rows
        if row["status"] == "TIME_VALID_CIK_VERIFIED"
    ]
    if len(intervals) != report["verified_interval_count"]:
        raise FinraCoverageV4Error("SEC V4 verified interval count mismatch")
    return intervals, {
        "protocol_path": protocol_path.relative_to(ROOT).as_posix(),
        "protocol_sha256": _sha256(protocol_path),
        "ledger_report_path": ledger_report_path.relative_to(ROOT).as_posix(),
        "ledger_report_sha256": _sha256(ledger_report_path),
        "ledger_path": ledger_path.relative_to(ROOT).as_posix(),
        "ledger_sha256": _sha256(ledger_path),
        "verified_interval_count": len(intervals),
        "targeted_filing_count": report["targeted_filing_count"],
        "targeted_anchor_count": report["targeted_anchor_count"],
        "targeted_entity_count": report["targeted_entity_count"],
        "full_universe_rescan_performed": False,
        "current_ticker_backfill_performed": False,
    }


def audit_v4(
    report_path: Path = REPORT,
    detail_path: Path = DETAIL,
) -> dict:
    protocol = json.loads(SEC_PROTOCOL.read_text(encoding="utf-8"))
    policy = protocol["finra_reaudit_policy"]
    intervals, lineage = load_sec_intervals()
    result = audit(
        FINRA_PROTOCOL,
        MANIFEST,
        report_path,
        detail_path,
        intervals_override=intervals,
        strict_reference_cik=False,
        report_version="FINRA_SHORT_INTEREST_COVERAGE_AUDIT_V4",
        next_priority=(
            "KEEP_FINRA_IN_PROSPECTIVE_SHADOW_AND_DO_NOT_TUNE_"
            "A_DIRECTION_HYPOTHESIS_ON_THE_COVERAGE_SAMPLE"
        ),
        cohort_identity_aliases=policy["cohort_identity_aliases"],
    )
    required = set(policy["required_cohorts"])
    required_reports = [
        row for row in result["cohorts"] if row["cohort"] in required
    ]
    gate_passed = (
        len(required_reports) == len(required)
        and all(row["pit_identifier_gate_passed"] for row in required_reports)
    )
    result["sec_interval_ledger"] = lineage
    result["identifier_ledger"]["strict_reference_cik_required"] = False
    result["identifier_ledger"][
        "cohort_reference_cik_backfill_performed"
    ] = False
    result["identifier_ledger"]["unique_matching_cik_required_per_date"] = True
    result["identifier_ledger"]["bny_research_identity_symbols"] = ["BK", "BNY"]
    result["identifier_ledger"]["bny_issue_name_filter_required"] = True
    result["identifier_ledger"]["historical_unrelated_bny_assigned"] = False
    result["finra_shadow_identifier_gate_passed"] = gate_passed
    result["status"] = (
        "HASH_LOCKED_AND_PIT_IDENTIFIER_READY_FOR_SHADOW"
        if result["integrity"]["all_raw_hashes_verified"] and gate_passed
        else "HASH_LOCKED_PIT_IDENTIFIER_INCOMPLETE"
    )
    result["decision"] = (
        "ALLOW_PROSPECTIVE_SHADOW_OBSERVATION_ONLY"
        if gate_passed
        else "KEEP_PROSPECTIVE_SHADOW_COLLECTION_IDENTIFIER_INCOMPLETE"
    )
    result["primary_long_horizon_oos_allowed"] = False
    result["new_direction_hypothesis_preregistered"] = False
    result["price_outcomes_opened"] = False
    result["herd_formula_change_allowed"] = False
    result["operational_action_authority"] = False
    result["operational_action_ratio"] = 0.0
    report_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, default=REPORT)
    parser.add_argument("--detail", type=Path, default=DETAIL)
    args = parser.parse_args()
    result = audit_v4(args.report, args.detail)
    print(json.dumps({
        "status": result["status"],
        "decision": result["decision"],
        "cohorts": result["cohorts"],
        "primary_long_horizon_oos_allowed": (
            result["primary_long_horizon_oos_allowed"]
        ),
        "new_direction_hypothesis_preregistered": (
            result["new_direction_hypothesis_preregistered"]
        ),
        "next_priority": result["next_priority"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
