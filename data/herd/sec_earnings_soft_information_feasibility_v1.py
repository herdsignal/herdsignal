"""SEC 실적 발표문 soft-information 연구의 가격 비참조 coverage를 감사한다."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
PROTOCOL_PATH = Path(__file__).with_suffix(".json")
OUTPUT_PATH = ROOT / "data/reports/sec_earnings_soft_information_pairs_v1.csv"
REPORT_PATH = ROOT / "data/reports/sec_earnings_soft_information_feasibility_v1.json"
VERSION = "HERD_SEC_EARNINGS_SOFT_INFORMATION_FEASIBILITY_V1"


class EarningsSoftInformationFeasibilityError(ValueError):
    """입력 불변성 또는 연구 방화벽이 깨졌을 때 발생한다."""


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _display_path(path: Path) -> str:
    resolved = path.resolve()
    if resolved.is_relative_to(ROOT):
        return str(resolved.relative_to(ROOT))
    return str(resolved)


def _load_protocol(protocol_path: Path = PROTOCOL_PATH) -> dict[str, Any]:
    protocol = json.loads(protocol_path.read_text())
    if (
        protocol.get("protocolVersion") != VERSION
        or protocol.get("status")
        != "LOCKED_BEFORE_TEXT_MEASUREMENT_OR_PRICE_OUTCOMES"
    ):
        raise EarningsSoftInformationFeasibilityError(
            "soft-information feasibility protocol is not locked"
        )
    for item in protocol.get("pinnedInputs", []):
        path = (ROOT / item["path"]).resolve()
        if not path.is_relative_to(ROOT) or not path.is_file():
            raise EarningsSoftInformationFeasibilityError(
                f"missing input: {item['path']}"
            )
        if _sha256(path) != item["sha256"]:
            raise EarningsSoftInformationFeasibilityError(
                f"input changed: {item['path']}"
            )
    _validate_firewall(protocol)
    return protocol


def _validate_firewall(protocol: dict[str, Any]) -> None:
    firewall = protocol.get("firewall", {})
    false_fields = {
        "textDirectionScoreComputed",
        "priceOrReturnOutcomesOpened",
        "directionHypothesisPreregistered",
        "sameSampleThresholdSearch",
        "rejectedFeatureRecombination",
        "legacyFormulaReuse",
        "blindHoldoutAccess",
        "herdFormulaChangeAllowed",
        "operationalActionAllowed",
    }
    if (
        any(firewall.get(field) is not False for field in false_fields)
        or firewall.get("operationalAction") != "HOLD"
        or firewall.get("operationalActionRatio") != 0.0
    ):
        raise EarningsSoftInformationFeasibilityError(
            "soft-information research firewall was weakened"
        )
    measurement = protocol.get("measurementDesign", {})
    license_policy = measurement.get("licensePolicy", {})
    if (
        measurement.get("stage") != "NOT_YET_AUTHORIZED"
        or license_policy.get("remoteLlmApiAllowed") is not False
        or license_policy.get("unpinnedModelAllowed") is not False
        or license_policy.get("companyExhibitRedistribution") is not False
        or license_policy.get("storeDerivedFactsAndSourceHashesOnly") is not True
    ):
        raise EarningsSoftInformationFeasibilityError(
            "measurement or licensing boundary was weakened"
        )


def _pair_id(current: pd.Series) -> str:
    payload = "|".join(
        (
            str(current["cik"]),
            str(current["prior_accession_number"]),
            str(current["accession_number"]),
        )
    )
    return hashlib.sha256(payload.encode()).hexdigest()


def build_feasibility(
    output_path: Path = OUTPUT_PATH,
    report_path: Path = REPORT_PATH,
    *,
    protocol: dict[str, Any] | None = None,
) -> dict[str, Any]:
    protocol = protocol or _load_protocol()
    _validate_firewall(protocol)
    source = protocol["sourceSelection"]
    index_spec = next(
        item for item in protocol["pinnedInputs"] if item["path"].endswith("index.csv")
    )
    index_path = ROOT / index_spec["path"]
    snapshot_path = index_path.parent
    frame = pd.read_csv(index_path, dtype=str, keep_default_na=False)
    required_columns = {
        "ticker",
        "cik",
        "accession_number",
        "accepted_at",
        "items",
        "document_role",
        "source_sha256",
        "source_bytes",
        "path",
    }
    if not required_columns.issubset(frame.columns):
        raise EarningsSoftInformationFeasibilityError("source index schema changed")

    eligible = frame[
        frame["items"].str.contains(source["requiredItem"], regex=False)
        & frame["document_role"].eq(source["requiredDocumentRole"])
    ].copy()
    eligible["accepted_at"] = pd.to_datetime(
        eligible["accepted_at"], utc=True, errors="raise"
    )
    eligible["source_bytes_number"] = pd.to_numeric(
        eligible["source_bytes"], errors="raise"
    )
    eligible = (
        eligible.sort_values(
            ["accession_number", "source_bytes_number", "source_sha256"],
            ascending=[True, False, True],
        )
        .drop_duplicates("accession_number", keep="first")
        .sort_values(["cik", "accepted_at", "accession_number"])
        .reset_index(drop=True)
    )
    path_valid = eligible.apply(
        lambda row: (snapshot_path / row["path"]).is_file()
        and Path(row["path"]).name == f"{row['source_sha256']}.gz",
        axis=1,
    )
    if not bool(path_valid.all()):
        raise EarningsSoftInformationFeasibilityError(
            "source document path or content-addressed filename changed"
        )

    grouped = eligible.groupby("cik", sort=False)
    eligible["prior_accession_number"] = grouped["accession_number"].shift()
    eligible["prior_accepted_at"] = grouped["accepted_at"].shift()
    eligible["prior_source_sha256"] = grouped["source_sha256"].shift()
    eligible["prior_path"] = grouped["path"].shift()
    eligible["gap_days"] = (
        eligible["accepted_at"] - eligible["prior_accepted_at"]
    ).dt.days
    pairs = eligible[
        eligible["prior_accession_number"].notna()
        & eligible["gap_days"].between(
            source["minimumPriorGapDays"], source["maximumPriorGapDays"]
        )
    ].copy()
    pairs["pair_id"] = pairs.apply(_pair_id, axis=1)
    pairs["source_use"] = source["sourceUse"]
    output_columns = [
        "pair_id",
        "ticker",
        "cik",
        "prior_accession_number",
        "prior_accepted_at",
        "prior_source_sha256",
        "prior_path",
        "accession_number",
        "accepted_at",
        "source_sha256",
        "path",
        "gap_days",
        "source_use",
    ]
    for column in ("prior_accepted_at", "accepted_at"):
        pairs[column] = pairs[column].dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    pairs = pairs[output_columns].sort_values(
        ["accepted_at", "cik", "accession_number"]
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    pairs.to_csv(output_path, index=False)

    gates = protocol["coverageGates"]
    accepted_years = pd.to_datetime(pairs["accepted_at"], utc=True).dt.year
    if pairs.empty:
        era_count = 0
    else:
        first_year = int(accepted_years.min())
        era_count = int(
            ((accepted_years - first_year) // gates["eraLengthYears"]).nunique()
        )
    issuer_document_counts = eligible.groupby("cik").size()
    checks = {
        "minimum_documents": len(eligible) >= gates["minimumDocuments"],
        "minimum_comparable_pairs": len(pairs) >= gates["minimumComparablePairs"],
        "minimum_issuers": pairs["cik"].nunique() >= gates["minimumIssuers"],
        "minimum_calendar_years": accepted_years.nunique()
        >= gates["minimumCalendarYears"],
        "minimum_eras": era_count >= gates["minimumEras"],
        "minimum_median_documents_per_issuer": float(issuer_document_counts.median())
        >= gates["minimumMedianDocumentsPerIssuer"],
    }
    coverage_passed = all(checks.values())
    report = {
        "reportVersion": VERSION,
        "status": (
            "SOURCE_COVERAGE_PASSED_MEASUREMENT_NOT_STARTED"
            if coverage_passed
            else "SOURCE_COVERAGE_FAILED"
        ),
        "documents": len(eligible),
        "comparablePairs": len(pairs),
        "issuers": int(pairs["cik"].nunique()),
        "calendarYears": int(accepted_years.nunique()),
        "eras": era_count,
        "firstAcceptedAt": pairs["accepted_at"].min() if not pairs.empty else None,
        "lastAcceptedAt": pairs["accepted_at"].max() if not pairs.empty else None,
        "medianGapDays": float(pairs["gap_days"].median()) if not pairs.empty else None,
        "medianDocumentsPerIssuer": float(issuer_document_counts.median()),
        "checks": checks,
        "coveragePassed": coverage_passed,
        "developmentUniverseOnly": True,
        "independentDirectionOosReady": False,
        "textMeasurementAuthorized": coverage_passed,
        "textDirectionScoreComputed": False,
        "priceOrReturnOutcomesOpened": False,
        "directionHypothesisPreregistered": False,
        "herdFormulaChangeAllowed": False,
        "operationalActionAllowed": False,
        "operationalAction": "HOLD",
        "operationalActionRatio": 0.0,
        "pairsPath": _display_path(output_path),
        "pairsSha256": _sha256(output_path),
        "nextGate": protocol["nextGate"] if coverage_passed else "STOP_AND_REDESIGN_SOURCE",
    }
    report_path.write_text(json.dumps(report, indent=2) + "\n")
    return report


if __name__ == "__main__":
    print(json.dumps(build_feasibility(), indent=2))
