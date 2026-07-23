"""Form 4 벌크 census의 coverage·원문 동등성·연구 권한을 감사한다."""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from pathlib import Path

import pandas as pd

from herd.sec_form4_atomic_v1 import CLASS_BY_CODE
from herd.sec_form4_bulk_v2 import (
    PROTOCOL,
    load_protocol,
    sha256,
    verify_download,
    verify_normalized,
)
from herd.sec_guidance_table_review_gate_v1 import wilson_lower


class Form4CensusGateError(RuntimeError):
    pass


CORE_FIELDS = (
    "transactionDate",
    "transactionCode",
    "transactionShares",
    "transactionPricePerShare",
    "acquiredDisposedCode",
    "sharesOwnedFollowingTransaction",
    "directOrIndirectOwnership",
)
NUMERIC_FIELDS = {
    "transactionShares",
    "transactionPricePerShare",
    "sharesOwnedFollowingTransaction",
}


def _normalize_scalar(value: object) -> str:
    if value is None or pd.isna(value):
        return ""
    return str(value).strip()


def _normalize_numeric(value: object) -> str:
    text = _normalize_scalar(value)
    if not text:
        return ""
    try:
        number = Decimal(text).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except InvalidOperation:
        return text
    normalized = format(number.normalize(), "f")
    return "0" if normalized in {"-0", ""} else normalized


def _normalize_date(value: object) -> str:
    text = _normalize_scalar(value)
    if re_match := re.match(r"^(\d{4}-\d{2}-\d{2})", text):
        return re_match.group(1)
    return text


def _normalize_bool(value: object) -> bool:
    return _normalize_scalar(value).lower() in {"1", "true", "yes"}


def _candidate_matches(review: pd.Series, candidate: pd.Series) -> dict[str, bool]:
    matches = {}
    for field in CORE_FIELDS:
        if field in NUMERIC_FIELDS:
            normalizer = _normalize_numeric
        elif field == "transactionDate":
            normalizer = _normalize_date
        else:
            normalizer = _normalize_scalar
        matches[field] = normalizer(review.get(field)) == normalizer(candidate.get(field))
    matches["isDerivative"] = _normalize_bool(
        review.get("isDerivative")
    ) == _normalize_bool(candidate.get("isDerivative"))
    return matches


def crosscheck_primary_xml(
    transactions: pd.DataFrame,
    adjudicated: pd.DataFrame,
    *,
    scope_end_date: str | None = None,
) -> tuple[pd.DataFrame, dict]:
    valid = adjudicated[
        adjudicated["reviewDecision"].astype(str).eq("VALID")
    ].copy()
    if scope_end_date is not None:
        valid = valid[
            valid["filingDate"].astype(str).str[:10].le(scope_end_date)
        ].copy()
    candidates = {
        accession: frame
        for accession, frame in transactions.groupby("accessionNumber", sort=False)
    }
    rows = []
    for _, review in valid.iterrows():
        accession = str(review["accessionNumber"])
        best: dict[str, bool] | None = None
        for _, candidate in candidates.get(accession, pd.DataFrame()).iterrows():
            matched = _candidate_matches(review, candidate)
            if best is None or sum(matched.values()) > sum(best.values()):
                best = matched
        best = best or {field: False for field in (*CORE_FIELDS, "isDerivative")}
        rows.append({
            "atomicTransactionIdV1": review["atomicTransactionId"],
            "accessionNumber": accession,
            **{f"{field}Match": result for field, result in best.items()},
            "exactMatch": all(best.values()),
            "bulkCandidateFound": accession in candidates,
        })
    detail = pd.DataFrame(rows)
    exact = int(detail["exactMatch"].sum()) if not detail.empty else 0
    reviewed = len(detail)
    field_rates = {
        field: (
            float(detail[f"{field}Match"].mean()) if reviewed else 0.0
        )
        for field in (*CORE_FIELDS, "isDerivative")
    }
    return detail, {
        "reviewed_primary_xml_transactions": reviewed,
        "bulk_candidate_found": (
            int(detail["bulkCandidateFound"].sum()) if reviewed else 0
        ),
        "exact_matches": exact,
        "exact_match_rate": exact / reviewed if reviewed else 0.0,
        "exact_match_wilson_95_lower": wilson_lower(exact, reviewed),
        "field_match_rates": field_rates,
    }


def _issuer_year_coverage(
    eligible: pd.DataFrame,
    submissions: pd.DataFrame,
    transactions: pd.DataFrame,
    start_year: int,
    end_year: int,
) -> pd.DataFrame:
    submission_counts = Counter(
        zip(
            submissions["issuerCik"],
            submissions["filingDate"].str[:4].astype(int),
        )
    )
    transaction_accession = transactions.merge(
        submissions[["accessionNumber", "issuerCik", "filingDate"]],
        on="accessionNumber",
        how="left",
        validate="many_to_one",
    )
    transaction_counts = Counter(
        zip(
            transaction_accession["issuerCik"],
            transaction_accession["filingDate"].str[:4].astype(int),
        )
    )
    rows = []
    for item in eligible.itertuples(index=False):
        for year in range(start_year, end_year + 1):
            key = (item.issuer_cik, year)
            rows.append({
                "ticker": item.ticker,
                "issuer_cik": item.issuer_cik,
                "calendar_year": year,
                "coverage_state": "OBSERVED_OFFICIAL_BULK",
                "form4_submissions": submission_counts[key],
                "atomic_transactions": transaction_counts[key],
                "zero_filing_is_observed": submission_counts[key] == 0,
            })
    return pd.DataFrame(rows)


def evaluate(
    snapshot: Path,
    *,
    independent_universe: Path,
    adjudicated_review: Path,
    output_report: Path,
    output_coverage: Path,
    output_crosscheck: Path,
    protocol_path: Path = PROTOCOL,
) -> dict:
    protocol = load_protocol(protocol_path)
    download_manifest = verify_download(snapshot, protocol_path=protocol_path)
    normalized_manifest = verify_normalized(snapshot, protocol_path=protocol_path)
    normalized = snapshot / "normalized"
    submissions = pd.read_csv(
        normalized / "submissions.csv", dtype=str, keep_default_na=False
    )
    owners = pd.read_csv(
        normalized / "reporting_owners.csv", dtype=str, keep_default_na=False
    )
    transactions = pd.read_csv(
        normalized / "transactions.csv", dtype=str, keep_default_na=False
    )
    independent = pd.read_csv(
        normalized / "independent_universe.csv",
        dtype={"issuer_cik": str},
        keep_default_na=False,
    )
    adjudicated = pd.read_csv(
        adjudicated_review, dtype=str, keep_default_na=False
    )
    crosscheck, crosscheck_summary = crosscheck_primary_xml(
        transactions,
        adjudicated,
        scope_end_date=pd.Period(
            download_manifest["quarter_end"], freq="Q"
        ).end_time.date().isoformat(),
    )

    start_year = int(download_manifest["quarter_start"][:4])
    end_year = int(download_manifest["quarter_end"][:4])
    coverage = _issuer_year_coverage(
        independent,
        submissions[
            submissions["researchSplit"].eq("INDEPENDENT_CURRENT_CONSTITUENT")
        ],
        transactions[
            transactions["accessionNumber"].isin(
                submissions.loc[
                    submissions["researchSplit"].eq(
                        "INDEPENDENT_CURRENT_CONSTITUENT"
                    ),
                    "accessionNumber",
                ]
            )
        ],
        start_year,
        end_year,
    )
    known = transactions["transactionCode"].map(
        lambda code: code in CLASS_BY_CODE
    )
    known_code_rate = float(known.mean()) if len(transactions) else 0.0
    independent_accessions = set(
        submissions.loc[
            submissions["researchSplit"].eq(
                "INDEPENDENT_CURRENT_CONSTITUENT"
            ),
            "accessionNumber",
        ]
    )
    independent_transactions = transactions[
        transactions["accessionNumber"].isin(independent_accessions)
    ]
    ps = independent_transactions[
        ~independent_transactions["isDerivative"].map(_normalize_bool)
        & independent_transactions["transactionCode"].isin({"P", "S"})
    ]
    ps_with_owner_rate = (
        float(ps["reportingOwnerCiks"].str.strip().ne("").mean())
        if len(ps) else 0.0
    )
    thresholds = protocol["coverage_gate"]
    expected_quarters = (
        (end_year - start_year) * 4
        + int(download_manifest["quarter_end"][-1])
        - int(download_manifest["quarter_start"][-1])
        + 1
    )
    checks = {
        "all_quarters_present": (
            int(download_manifest["quarter_count"]) == expected_quarters
        ),
        "minimum_oos_issuers": (
            int(independent["issuer_cik"].nunique())
            >= int(thresholds["minimum_oos_issuers"])
        ),
        "minimum_primary_xml_crosscheck_transactions": (
            crosscheck_summary["reviewed_primary_xml_transactions"]
            >= int(thresholds["minimum_primary_xml_crosscheck_transactions"])
        ),
        "minimum_bulk_to_primary_exact_match_rate": (
            crosscheck_summary["exact_match_rate"]
            >= float(thresholds["minimum_bulk_to_primary_exact_match_rate"])
        ),
        "minimum_exact_match_wilson_95_lower": (
            crosscheck_summary["exact_match_wilson_95_lower"]
            >= float(thresholds["minimum_exact_match_wilson_95_lower"])
        ),
        "minimum_known_transaction_code_rate": (
            known_code_rate
            >= float(thresholds["minimum_known_transaction_code_rate"])
        ),
        "minimum_p_or_s_with_owner_rate": (
            ps_with_owner_rate
            >= float(
                thresholds["minimum_non_derivative_code_p_or_s_with_owner_rate"]
            )
        ),
        "lineage_verified": True,
        "price_outcomes_remained_closed": (
            normalized_manifest.get("price_outcomes_opened") is False
        ),
        "action_authority_remained_zero": (
            normalized_manifest.get("operational_action_authority") is False
        ),
    }
    passed = all(checks.values())
    output_coverage.parent.mkdir(parents=True, exist_ok=True)
    coverage.to_csv(output_coverage, index=False)
    crosscheck.to_csv(output_crosscheck, index=False)
    report = {
        "report_version": "HERD_SEC_FORM4_CENSUS_GATE_V2",
        "status": (
            "RESEARCH_CENSUS_READY_FOR_ONE_PREREGISTERED_HYPOTHESIS"
            if passed else "RESEARCH_CENSUS_BLOCKED"
        ),
        "passed": passed,
        "checks": checks,
        "quarter_count": int(download_manifest["quarter_count"]),
        "independent_issuers": int(independent["issuer_cik"].nunique()),
        "independent_issuer_year_cells": len(coverage),
        "observed_zero_filing_cells": int(
            coverage["zero_filing_is_observed"].sum()
        ),
        "submissions": len(submissions),
        "transactions": len(transactions),
        "known_transaction_code_rate": known_code_rate,
        "independent_non_derivative_p_or_s_transactions": len(ps),
        "p_or_s_with_reporting_owner_rate": ps_with_owner_rate,
        "primary_xml_crosscheck": crosscheck_summary,
        "hashes": {
            "protocol_sha256": sha256(protocol_path),
            "download_manifest_sha256": sha256(snapshot / "manifest.json"),
            "normalized_manifest_sha256": sha256(
                snapshot / "normalized_manifest.json"
            ),
            "independent_universe_sha256": sha256(independent_universe),
            "adjudicated_review_sha256": sha256(adjudicated_review),
            "coverage_sha256": sha256(output_coverage),
            "crosscheck_sha256": sha256(output_crosscheck),
        },
        "claim_boundary": (
            "hypothesis-specific current-constituent robustness; "
            "not blind and not survivorship safe"
        ),
        "price_outcomes_opened": False,
        "blind_holdout_access": False,
        "survivorship_safe": False,
        "operational_action_authority": False,
        "single_hypothesis_preregistration_allowed": passed,
        "next_decision": (
            "LOCK_ONE_INSIDER_PURCHASE_SUPPORT_HYPOTHESIS"
            if passed else "REPAIR_CENSUS_WITHOUT_OPENING_PRICE_OUTCOMES"
        ),
    }
    output_report.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("snapshot", type=Path)
    parser.add_argument(
        "--independent-universe",
        type=Path,
        default=Path("data/reports/independent_universe_v1.csv"),
    )
    parser.add_argument(
        "--adjudicated-review",
        type=Path,
        default=Path("data/reports/sec_form4_review_adjudicated_v1.csv"),
    )
    parser.add_argument(
        "--output-report",
        type=Path,
        default=Path("data/reports/sec_form4_census_gate_v2.json"),
    )
    parser.add_argument(
        "--output-coverage",
        type=Path,
        default=Path("data/reports/sec_form4_issuer_year_coverage_v2.csv"),
    )
    parser.add_argument(
        "--output-crosscheck",
        type=Path,
        default=Path("data/reports/sec_form4_bulk_primary_crosscheck_v2.csv"),
    )
    args = parser.parse_args()
    print(json.dumps(evaluate(
        args.snapshot,
        independent_universe=args.independent_universe,
        adjudicated_review=args.adjudicated_review,
        output_report=args.output_report,
        output_coverage=args.output_coverage,
        output_crosscheck=args.output_crosscheck,
    ), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
