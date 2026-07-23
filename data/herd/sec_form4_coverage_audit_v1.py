"""Form 4 검수 표본과 연구용 accession 모집단의 기업·연도 coverage를 감사한다."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd


class CoverageAuditError(RuntimeError):
    pass


IDENTITY = ("issuer_cik", "accession_number")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _identity(frame: pd.DataFrame) -> set[tuple[str, str]]:
    return set(map(tuple, frame[list(IDENTITY)].astype(str).to_numpy()))


def audit(
    catalog_path: Path,
    sample_path: Path,
    source_index_path: Path,
    source_manifest_path: Path,
    atomic_path: Path,
    rejection_path: Path,
    source_gate_path: Path,
    protocol_path: Path,
    detail_output: Path,
    report_output: Path,
) -> dict:
    gate = json.loads(source_gate_path.read_text(encoding="utf-8"))
    if gate.get("status") != "SOURCE_REVIEW_PASSED":
        raise CoverageAuditError("source accuracy gate must pass before coverage audit")
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    source_manifest = json.loads(
        source_manifest_path.read_text(encoding="utf-8")
    )
    catalog = pd.read_csv(catalog_path, keep_default_na=False, dtype=str)
    sample = pd.read_csv(sample_path, keep_default_na=False, dtype=str)
    source = pd.read_csv(source_index_path, keep_default_na=False, dtype=str)
    atomic = pd.read_csv(atomic_path, keep_default_na=False, dtype=str)
    rejected = pd.read_csv(rejection_path, keep_default_na=False, dtype=str)
    for name, frame in (
        ("catalog", catalog),
        ("sample", sample),
        ("source index", source),
    ):
        missing = set(IDENTITY) - set(frame.columns)
        if missing:
            raise CoverageAuditError(
                f"{name} missing accession identity: {sorted(missing)}"
            )
        if frame.duplicated(list(IDENTITY)).any():
            raise CoverageAuditError(f"{name} has duplicate accession identity")

    catalog_ids = _identity(catalog)
    sample_ids = _identity(sample)
    source_ids = _identity(source)
    required_rejection_columns = {"expected_issuer_cik", "accession_number"}
    missing_rejection_columns = required_rejection_columns - set(rejected.columns)
    if missing_rejection_columns:
        raise CoverageAuditError(
            "rejection ledger missing accession identity: "
            f"{sorted(missing_rejection_columns)}"
        )
    rejected_ids = set(
        map(
            tuple,
            rejected[["expected_issuer_cik", "accession_number"]]
            .rename(columns={"expected_issuer_cik": "issuer_cik"})
            .astype(str)
            .to_numpy(),
        )
    )
    if not sample_ids <= catalog_ids:
        raise CoverageAuditError("review sample contains accession outside catalog")
    if source_ids != sample_ids:
        raise CoverageAuditError("source corpus identities differ from review sample")
    if not rejected_ids <= source_ids:
        raise CoverageAuditError("rejection ledger contains accession outside source")

    catalog = catalog.assign(calendar_year=catalog["filing_date"].str[:4])
    sample = sample.assign(calendar_year=sample["filing_date"].str[:4])
    source = source.assign(calendar_year=source["filing_date"].str[:4])
    parsed = (
        atomic[["issuerCik", "accessionNumber"]]
        .drop_duplicates()
        .rename(columns={
            "issuerCik": "issuer_cik",
            "accessionNumber": "accession_number",
        })
        .merge(
            catalog[list(IDENTITY) + ["calendar_year"]],
            on=list(IDENTITY),
            how="left",
            validate="one_to_one",
        )
    )
    if parsed["calendar_year"].eq("").any() or parsed["calendar_year"].isna().any():
        raise CoverageAuditError("parsed accession is not present in catalog")
    parsed_ids = set(map(tuple, parsed[list(IDENTITY)].astype(str).to_numpy()))
    overlap = parsed_ids & rejected_ids
    if overlap:
        raise CoverageAuditError(
            "accession cannot be both atomic-parsed and issuer-rejected"
        )
    unresolved_source_ids = source_ids - parsed_ids - rejected_ids

    rejected_detail = (
        rejected[["expected_issuer_cik", "accession_number"]]
        .rename(columns={"expected_issuer_cik": "issuer_cik"})
        .merge(
            catalog[list(IDENTITY) + ["calendar_year"]],
            on=list(IDENTITY),
            how="left",
            validate="one_to_one",
        )
    )
    unresolved_detail = pd.DataFrame(
        sorted(unresolved_source_ids), columns=list(IDENTITY)
    ).merge(
        catalog[list(IDENTITY) + ["calendar_year"]],
        on=list(IDENTITY),
        how="left",
        validate="one_to_one",
    )

    def counts(frame: pd.DataFrame, name: str) -> pd.DataFrame:
        return (
            frame.groupby(["issuer_cik", "calendar_year"])
            .size()
            .rename(name)
            .reset_index()
        )

    detail = counts(catalog, "catalogAccessions")
    for frame, column in (
        (sample, "reviewSampleAccessions"),
        (source, "downloadedAccessions"),
        (parsed, "parsedAccessions"),
        (rejected_detail, "issuerRejectedAccessions"),
        (unresolved_detail, "unresolvedSourceAccessions"),
    ):
        detail = detail.merge(
            counts(frame, column),
            on=["issuer_cik", "calendar_year"],
            how="left",
            validate="one_to_one",
        )
    count_columns = [
        "catalogAccessions",
        "reviewSampleAccessions",
        "downloadedAccessions",
        "parsedAccessions",
        "issuerRejectedAccessions",
        "unresolvedSourceAccessions",
    ]
    detail[count_columns] = detail[count_columns].fillna(0).astype(int)
    detail["downloadCoverage"] = (
        detail["downloadedAccessions"] / detail["catalogAccessions"]
    )
    detail["parseCoverage"] = (
        detail["parsedAccessions"] / detail["catalogAccessions"]
    )
    detail["cellComplete"] = (
        detail["downloadedAccessions"] == detail["catalogAccessions"]
    ) & (
        detail["unresolvedSourceAccessions"] == 0
    )
    detail = detail.sort_values(["issuer_cik", "calendar_year"])
    detail_output.parent.mkdir(parents=True, exist_ok=True)
    detail.to_csv(detail_output, index=False)

    protocol_role = protocol.get("scope", {}).get("role")
    full_census = source_ids == catalog_ids
    all_sources_classified = not unresolved_source_ids
    role_authorized = protocol_role == "RESEARCH_CENSUS"
    sample_manifest_match = (
        source_manifest.get("source_sample_sha256") == _sha256(sample_path)
    )
    index_manifest_match = (
        source_manifest.get("index_sha256") == _sha256(source_index_path)
    )
    lineage_consistent = sample_manifest_match and index_manifest_match
    passed = (
        full_census
        and all_sources_classified
        and role_authorized
        and lineage_consistent
    )
    report = {
        "report_version": "HERD_SEC_FORM4_COVERAGE_AUDIT_V1",
        "status": (
            "RESEARCH_CENSUS_COVERAGE_PASSED"
            if passed else "REVIEW_SAMPLE_NOT_RESEARCH_CENSUS"
        ),
        "protocol_role": protocol_role,
        "catalog_accessions": len(catalog_ids),
        "review_sample_accessions": len(sample_ids),
        "downloaded_accessions": len(source_ids),
        "issuer_validated_accessions": len(source_ids - rejected_ids),
        "atomic_parsed_accessions": len(parsed_ids),
        "issuer_rejected_accessions": len(rejected_ids),
        "unresolved_source_accessions": len(unresolved_source_ids),
        "download_coverage": len(source_ids) / len(catalog_ids),
        "atomic_parse_coverage": len(parsed_ids) / len(catalog_ids),
        "catalog_issuers": int(catalog["issuer_cik"].nunique()),
        "catalog_years": int(catalog["calendar_year"].nunique()),
        "issuer_year_cells": len(detail),
        "complete_issuer_year_cells": int(detail["cellComplete"].sum()),
        "complete_issuer_year_cell_ratio": float(detail["cellComplete"].mean()),
        "minimum_issuer_year_download_coverage": float(
            detail["downloadCoverage"].min()
        ),
        "median_issuer_year_download_coverage": float(
            detail["downloadCoverage"].median()
        ),
        "review_sample_identity_matches_source_corpus": source_ids == sample_ids,
        "source_sample_manifest_hash_matches_current_sample": (
            sample_manifest_match
        ),
        "source_index_manifest_hash_matches_current_index": index_manifest_match,
        "source_lineage_consistent": lineage_consistent,
        "all_downloaded_sources_classified": all_sources_classified,
        "research_census_complete": full_census and all_sources_classified,
        "research_role_authorized": role_authorized,
        "source_accuracy_gate_passed": True,
        "single_hypothesis_preregistration_allowed": passed,
        "price_outcomes_opened": False,
        "operational_action_authority": False,
        "hashes": {
            "catalog_sha256": _sha256(catalog_path),
            "review_sample_sha256": _sha256(sample_path),
            "source_index_sha256": _sha256(source_index_path),
            "source_manifest_sha256": _sha256(source_manifest_path),
            "atomic_sha256": _sha256(atomic_path),
            "rejection_ledger_sha256": _sha256(rejection_path),
            "source_gate_sha256": _sha256(source_gate_path),
            "detail_sha256": _sha256(detail_output),
        },
        "blocking_reasons": [
            reason
            for condition, reason in (
                (
                    not role_authorized,
                    "CORPUS_ROLE_IS_PARSER_AND_SOURCE_REVIEW_DEVELOPMENT_ONLY",
                ),
                (
                    not full_census,
                    "DOWNLOADED_ACCESSIONS_DO_NOT_COVER_LOCKED_CATALOG",
                ),
                (
                    bool(unresolved_source_ids),
                    "VALIDATED_DOCUMENTS_WITHOUT_ATOMIC_TRANSACTIONS_REQUIRE_REVIEW",
                ),
                (
                    not lineage_consistent,
                    "SOURCE_CORPUS_MANIFEST_LINEAGE_MISMATCH",
                ),
            )
            if condition
        ],
        "next_decision": (
            "PREREGISTER_ONE_FORM4_HYPOTHESIS"
            if passed else "LOCK_AND_BUILD_COMPLETE_FORM4_RESEARCH_CENSUS"
        ),
    }
    report_output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("catalog", type=Path)
    parser.add_argument("sample", type=Path)
    parser.add_argument("source_index", type=Path)
    parser.add_argument("source_manifest", type=Path)
    parser.add_argument("atomic", type=Path)
    parser.add_argument("rejections", type=Path)
    parser.add_argument("--source-gate", type=Path, required=True)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--detail-output", type=Path, required=True)
    parser.add_argument("--report-output", type=Path, required=True)
    args = parser.parse_args()
    result = audit(
        args.catalog,
        args.sample,
        args.source_index,
        args.source_manifest,
        args.atomic,
        args.rejections,
        args.source_gate,
        args.protocol,
        args.detail_output,
        args.report_output,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
