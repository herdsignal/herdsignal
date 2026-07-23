"""V5 SEC 원장으로 FINRA identity-observed lifecycle coverage를 감사한다."""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path

from herd.finra_short_interest_coverage_audit_v1 import (
    MANIFEST,
    PROTOCOL as FINRA_PROTOCOL,
    ROOT,
    _sha256,
    _display_path,
    audit,
)
from herd.finra_short_interest_coverage_audit_v4 import load_sec_intervals


SEC_PROTOCOL = Path(__file__).with_name("sec_time_valid_ticker_cik_ledger_v5.json")
SEC_REPORT = ROOT / "data/reports/sec_time_valid_ticker_cik_ledger_v5.json"
SEC_LEDGER = ROOT / "data/reports/sec_time_valid_ticker_cik_intervals_v5.csv"
TARGET_QUEUE_ROLE = "IDENTIFIER_GAP_QUEUE"
REPORT = ROOT / "data/reports/finra_short_interest_lifecycle_coverage_v5.json"
DETAIL = ROOT / "data/reports/finra_short_interest_lifecycle_ticker_coverage_v5.csv"


class FinraLifecycleCoverageV5Error(RuntimeError):
    pass


def _intervals() -> tuple[list[dict], dict]:
    intervals, lineage = load_sec_intervals(
        SEC_PROTOCOL,
        SEC_REPORT,
        SEC_LEDGER,
    )
    return intervals, {
        **lineage,
        "ledger_version": "V5",
    }


def _read_csv(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def _locked_input(protocol: dict, role: str) -> Path:
    relative = next(
        row["path"] for row in protocol["locked_inputs"]
        if row["role"] == role
    )
    return ROOT / relative


def _target_gap_audit(
    protocol: dict,
    details: list[dict],
    minimum: float,
) -> dict:
    target_rows = _read_csv(_locked_input(protocol, TARGET_QUEUE_ROLE))
    current = {
        row["ticker"]: row
        for row in details
        if row["cohort"] == "CURRENT_SP500_REFERENCE_503"
    }
    results = []
    for target in target_rows:
        ticker = target["reference_ticker"]
        if ticker not in current:
            raise FinraLifecycleCoverageV5Error(
                f"target queue ticker absent from current cohort: {ticker}"
            )
        row = current[ticker]
        observed = int(row["observed_settlement_dates"])
        linked = int(row["time_valid_cik_linked_dates"])
        coverage = linked / observed if observed else 0.0
        passed = coverage >= minimum
        results.append({
            "ticker": ticker,
            "cik": row["cik"],
            "identity_observed_opportunities": observed,
            "time_valid_cik_linked_opportunities": linked,
            "identity_observed_pit_link_coverage": coverage,
            "required_coverage": minimum,
            "individual_identifier_gate_passed": passed,
            "blocker": (
                None
                if passed
                else "PUBLIC_PRIMARY_ANCHOR_GAP_AFTER_SOURCE_EXHAUSTION"
            ),
        })
    blockers = [
        row for row in results
        if not row["individual_identifier_gate_passed"]
    ]
    return {
        "target_entity_count": len(results),
        "individual_minimum_coverage": minimum,
        "complete_target_count": len(results) - len(blockers),
        "blocked_target_count": len(blockers),
        "all_target_identifiers_complete": not blockers,
        "blocked_targets": blockers,
        "current_ticker_backfill_performed": False,
        "unsupported_symbol_normalization_performed": False,
        "source_exhaustion_is_not_treated_as_identity_proof": True,
    }


def audit_lifecycle_v5(
    report_path: Path = REPORT,
    detail_path: Path = DETAIL,
) -> dict:
    protocol = json.loads(SEC_PROTOCOL.read_text(encoding="utf-8"))
    intervals, lineage = _intervals()
    temporary_report = report_path.with_suffix(".raw.json")
    temporary_detail = detail_path.with_suffix(".raw.csv")
    result = audit(
        FINRA_PROTOCOL,
        MANIFEST,
        temporary_report,
        temporary_detail,
        intervals_override=intervals,
        strict_reference_cik=False,
        report_version="FINRA_SHORT_INTEREST_LIFECYCLE_COVERAGE_V5",
        next_priority="BUILD_UNIFIED_PROSPECTIVE_PIT_SHADOW_PANEL",
        cohort_identity_aliases=protocol["finra_identity_aliases"],
    )
    details = _read_csv(temporary_detail)
    totals: dict[str, dict[str, int]] = defaultdict(
        lambda: {"identity_observed": 0, "linked": 0, "zero_observation": 0}
    )
    for row in details:
        observed = int(row["observed_settlement_dates"])
        linked = int(row["time_valid_cik_linked_dates"])
        row["identity_observed_pit_link_coverage"] = (
            str(linked / observed) if observed else ""
        )
        row["lifecycle_denominator_status"] = (
            "IDENTITY_OBSERVED"
            if observed
            else "NO_MATCHING_IDENTITY_OBSERVATION"
        )
        cohort = totals[row["cohort"]]
        cohort["identity_observed"] += observed
        cohort["linked"] += linked
        cohort["zero_observation"] += int(observed == 0)

    with detail_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=list(details[0]),
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(details)
    temporary_report.unlink(missing_ok=True)
    temporary_detail.unlink(missing_ok=True)

    required = set(
        protocol["lifecycle_coverage_policy"]["required_cohorts"]
    )
    minimum = protocol["lifecycle_coverage_policy"]["minimum_coverage"]
    lifecycle_reports = []
    for raw in result["cohorts"]:
        values = totals[raw["cohort"]]
        coverage = (
            values["linked"] / values["identity_observed"]
            if values["identity_observed"]
            else 0.0
        )
        lifecycle_reports.append({
            "cohort": raw["cohort"],
            "calendar_ticker_date_opportunities": (
                raw["ticker_date_opportunities"]
            ),
            "calendar_time_valid_cik_link_coverage": (
                raw["time_valid_cik_link_coverage"]
            ),
            "identity_observed_opportunities": values["identity_observed"],
            "time_valid_cik_linked_opportunities": values["linked"],
            "identity_observed_pit_link_coverage": coverage,
            "tickers_without_matching_identity_observation": (
                values["zero_observation"]
            ),
            "required_coverage": minimum,
            "lifecycle_identifier_gate_passed": coverage >= minimum,
        })
    gate = all(
        row["lifecycle_identifier_gate_passed"]
        for row in lifecycle_reports
        if row["cohort"] in required
    )
    target_gap_audit = _target_gap_audit(protocol, details, minimum)
    result["sec_interval_ledger"] = lineage
    result["cohorts"] = lifecycle_reports
    result["lifecycle_denominator"] = protocol[
        "lifecycle_coverage_policy"
    ]["denominator"]
    result["lifecycle_denominator_is_not_sec_interval_span"] = True
    result["first_finra_observation_used_as_sec_identity_proof"] = False
    result["detail_path"] = _display_path(detail_path)
    result["detail_sha256"] = _sha256(detail_path)
    result["finra_shadow_identifier_gate_passed"] = gate
    result["target_gap_audit"] = target_gap_audit
    result["all_target_identifiers_complete"] = target_gap_audit[
        "all_target_identifiers_complete"
    ]
    result["status"] = (
        "HASH_LOCKED_LIFECYCLE_IDENTIFIER_READY_FOR_SHADOW"
        if result["integrity"]["all_raw_hashes_verified"] and gate
        else "HASH_LOCKED_LIFECYCLE_IDENTIFIER_INCOMPLETE"
    )
    result["decision"] = (
        "ALLOW_PROSPECTIVE_SHADOW_WITH_EXPLICIT_TARGET_BLOCKERS"
        if gate
        else "KEEP_SHADOW_IDENTIFIER_INCOMPLETE"
    )
    result["primary_long_horizon_oos_allowed"] = False
    result["price_outcomes_opened"] = False
    result["new_direction_hypothesis_preregistered"] = False
    result["herd_formula_change_allowed"] = False
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
    print(json.dumps(
        audit_lifecycle_v5(args.report, args.detail),
        ensure_ascii=False,
        indent=2,
    ))


if __name__ == "__main__":
    main()
