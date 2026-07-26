"""Form 4 timing-non-routine 매도 사건의 가격 비참조 coverage를 감사한다."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

import pandas as pd

from herd.sec_form4_bulk_v2 import verify_normalized


ROOT = Path(__file__).resolve().parents[2]
PROTOCOL_PATH = Path(__file__).with_suffix(".json")
SNAPSHOT = ROOT / "data/reference/sec/sec-form4-bulk-v2-2012q1-2026q2-20260723"
OUTPUT_PATH = ROOT / "data/reports/sec_form4_nonroutine_sale_events_v1.csv"
REPORT_PATH = ROOT / "data/reports/sec_form4_nonroutine_sale_feasibility_v1.json"
VERSION = "HERD_SEC_FORM4_NONROUTINE_SALE_FEASIBILITY_V1"


class NonroutineSaleFeasibilityError(RuntimeError):
    """Form 4 매도 feasibility 계약 위반."""


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _positive(value: object) -> bool:
    try:
        return float(str(value).strip()) > 0
    except (TypeError, ValueError):
        return False


def _bool(value: object) -> bool:
    return str(value or "").strip().casefold() in {"1", "true", "yes"}


def _tenb5(text: object) -> bool:
    return bool(re.search(r"\b10b5-?1\b", str(text or ""), flags=re.IGNORECASE))


def _eligible_relationship(value: object, allowed: list[str]) -> bool:
    normalized = str(value or "").casefold()
    return any(role.casefold() in normalized for role in allowed)


def _load_protocol() -> dict[str, Any]:
    protocol = json.loads(PROTOCOL_PATH.read_text())
    if (
        protocol.get("protocol_version") != VERSION
        or protocol.get("status") != "LOCKED_BEFORE_SALE_EVENT_BUILD"
    ):
        raise NonroutineSaleFeasibilityError("sale feasibility protocol is not locked")
    for specification in protocol["inputs"]:
        path = ROOT / specification["path"]
        if _hash(path) != specification["sha256"]:
            raise NonroutineSaleFeasibilityError(f"input hash changed: {specification['path']}")
    firewall = protocol["firewall"]
    if (
        firewall["price_or_return_outcomes_opened"] is not False
        or firewall["direction_hypothesis_executed"] is not False
        or firewall["threshold_search"] is not False
        or firewall["legacy_v4_or_v61_formula_reuse"] is not False
        or firewall["blind_holdout_access"] is not False
        or firewall["operational_action_ratio"] != 0.0
    ):
        raise NonroutineSaleFeasibilityError("research firewall was widened")
    return protocol


def build_feasibility(
    output_path: Path = OUTPUT_PATH,
    report_path: Path = REPORT_PATH,
) -> dict[str, Any]:
    protocol = _load_protocol()
    verify_normalized(SNAPSHOT)
    normalized = SNAPSHOT / "normalized"
    submissions = pd.read_csv(normalized / "submissions.csv", dtype=str, keep_default_na=False)
    owners = pd.read_csv(normalized / "reporting_owners.csv", dtype=str, keep_default_na=False)
    transactions = pd.read_csv(normalized / "transactions.csv", dtype=str, keep_default_na=False)
    definition = protocol["event_definition"]
    filings = submissions[
        submissions["researchSplit"].eq(definition["research_split"])
        & submissions["documentType"].eq(definition["document_type"])
        & ~submissions["isAmendment"].map(_bool)
    ][
        ["accessionNumber", "issuerCik", "issuerTradingSymbol", "filingDate", "aff10b5one"]
    ].copy()
    sales = transactions[
        transactions["accessionNumber"].isin(filings["accessionNumber"])
        & transactions["transactionTable"].eq(definition["transaction_table"])
        & transactions["transactionCode"].eq(definition["transaction_code"])
        & transactions["directOrIndirectOwnership"].eq("D")
        & transactions["transactionShares"].map(_positive)
        & transactions["transactionPricePerShare"].map(_positive)
    ][
        [
            "accessionNumber",
            "transactionDate",
            "transactionShares",
            "transactionPricePerShare",
            "referencedFootnoteText",
        ]
    ].copy()
    sales = sales.merge(filings, on="accessionNumber", validate="many_to_one")
    eligible_owners = owners[
        owners["accessionNumber"].isin(sales["accessionNumber"])
        & owners["relationship"].map(
            lambda value: _eligible_relationship(
                value, definition["eligible_owner_relationships"]
            )
        )
    ][
        ["accessionNumber", "reportingOwnerCik", "reportingOwnerName", "relationship", "officerTitle"]
    ].copy()
    events = sales.merge(eligible_owners, on="accessionNumber", validate="many_to_many")
    events = events.drop_duplicates(["issuerCik", "reportingOwnerCik", "accessionNumber"]).copy()
    events["filingDate"] = pd.to_datetime(events["filingDate"])
    events["explicit10b5One"] = events["aff10b5one"].map(_bool) | events[
        "referencedFootnoteText"
    ].map(_tenb5)
    events = events.sort_values(
        ["issuerCik", "reportingOwnerCik", "filingDate", "accessionNumber"]
    )
    history: dict[tuple[str, str], set[tuple[int, int]]] = defaultdict(set)
    first_year: dict[tuple[str, str], int] = {}
    statuses = []
    for row in events.itertuples(index=False):
        key = (row.issuerCik, row.reportingOwnerCik)
        year, month = row.filingDate.year, row.filingDate.month
        first_year.setdefault(key, year)
        prior = history[key]
        if year - first_year[key] < 3:
            status = "UNKNOWN_WARMUP"
        elif all((year - offset, month) in prior for offset in (1, 2, 3)):
            status = "ROUTINE"
        else:
            status = "TIMING_NON_ROUTINE_CANDIDATE"
        statuses.append(status)
        prior.add((year, month))
    events["timingStatus"] = statuses
    events["candidateEligible"] = (
        events["timingStatus"].eq("TIMING_NON_ROUTINE_CANDIDATE")
        & ~events["explicit10b5One"]
    )
    events["ownerSaleEventId"] = events.apply(
        lambda row: hashlib.sha256(
            f"{row.issuerCik}|{row.reportingOwnerCik}|{row.accessionNumber}".encode()
        ).hexdigest(),
        axis=1,
    )
    columns = [
        "ownerSaleEventId",
        "issuerCik",
        "issuerTradingSymbol",
        "reportingOwnerCik",
        "reportingOwnerName",
        "relationship",
        "officerTitle",
        "accessionNumber",
        "filingDate",
        "transactionDate",
        "transactionShares",
        "transactionPricePerShare",
        "explicit10b5One",
        "timingStatus",
        "candidateEligible",
    ]
    events["filingDate"] = events["filingDate"].dt.date.astype(str)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    events[columns].to_csv(output_path, index=False)
    candidates = events[events["candidateEligible"]]
    years = pd.to_datetime(events["filingDate"]).dt.year
    gates = protocol["coverage_gates"]
    checks = {
        "minimum_owner_sale_events": len(events) >= gates["minimum_owner_sale_events"],
        "minimum_timing_nonroutine_nonplan_events": len(candidates)
        >= gates["minimum_timing_nonroutine_nonplan_events"],
        "minimum_candidate_issuers": candidates["issuerCik"].nunique()
        >= gates["minimum_candidate_issuers"],
        "minimum_candidate_owners": candidates["reportingOwnerCik"].nunique()
        >= gates["minimum_candidate_owners"],
        "minimum_source_years": years.nunique() >= gates["minimum_source_years"],
    }
    report = {
        "report_version": VERSION,
        "status": "SALE_FEASIBILITY_COMPLETE",
        "owner_sale_events": len(events),
        "distinct_issuers": int(events["issuerCik"].nunique()),
        "distinct_owners": int(events["reportingOwnerCik"].nunique()),
        "source_years": int(years.nunique()),
        "explicit_10b5_1_events": int(events["explicit10b5One"].sum()),
        "timing_status_counts": events["timingStatus"].value_counts().to_dict(),
        "candidate_events": len(candidates),
        "candidate_issuers": int(candidates["issuerCik"].nunique()),
        "candidate_owners": int(candidates["reportingOwnerCik"].nunique()),
        "checks": checks,
        "coverage_gate_passed": all(checks.values()),
        "price_or_return_outcomes_opened": False,
        "direction_hypothesis_executed": False,
        "operational_action_ratio": 0.0,
        "events_path": str(output_path.relative_to(ROOT)),
        "events_sha256": _hash(output_path),
    }
    report_path.write_text(json.dumps(report, indent=2) + "\n")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.parse_args()
    print(json.dumps(build_feasibility(), indent=2))
