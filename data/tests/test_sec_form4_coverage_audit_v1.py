import json
import hashlib

import pandas as pd

from herd.sec_form4_coverage_audit_v1 import audit


def _write_inputs(tmp_path, role, source_rows):
    catalog = pd.DataFrame([
        {
            "issuer_cik": "1",
            "accession_number": "a",
            "filing_date": "2024-01-01",
        },
        {
            "issuer_cik": "1",
            "accession_number": "b",
            "filing_date": "2024-02-01",
        },
    ])
    sample = catalog.iloc[:source_rows].copy()
    source = sample.copy()
    atomic = source.rename(columns={
        "issuer_cik": "issuerCik",
        "accession_number": "accessionNumber",
    })
    paths = {}
    for name, frame in (
        ("catalog", catalog),
        ("sample", sample),
        ("source", source),
        ("atomic", atomic),
    ):
        path = tmp_path / f"{name}.csv"
        frame.to_csv(path, index=False)
        paths[name] = path
    rejections = tmp_path / "rejections.csv"
    pd.DataFrame(columns=[
        "accession_number",
        "expected_issuer_cik",
    ]).to_csv(rejections, index=False)
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({
        "source_sample_sha256": hashlib.sha256(
            paths["sample"].read_bytes()
        ).hexdigest(),
        "index_sha256": hashlib.sha256(
            paths["source"].read_bytes()
        ).hexdigest(),
    }))
    gate = tmp_path / "gate.json"
    gate.write_text(json.dumps({"status": "SOURCE_REVIEW_PASSED"}))
    protocol = tmp_path / "protocol.json"
    protocol.write_text(json.dumps({"scope": {"role": role}}))
    paths.update(
        gate=gate,
        protocol=protocol,
        manifest=manifest,
        rejections=rejections,
    )
    return paths


def test_review_sample_is_not_promoted_to_research_census(tmp_path):
    paths = _write_inputs(
        tmp_path, "PARSER_AND_SOURCE_REVIEW_DEVELOPMENT_ONLY", 1
    )
    result = audit(
        paths["catalog"],
        paths["sample"],
        paths["source"],
        paths["manifest"],
        paths["atomic"],
        paths["rejections"],
        paths["gate"],
        paths["protocol"],
        tmp_path / "detail.csv",
        tmp_path / "report.json",
    )
    assert result["status"] == "REVIEW_SAMPLE_NOT_RESEARCH_CENSUS"
    assert result["single_hypothesis_preregistration_allowed"] is False
    assert result["blocking_reasons"] == [
        "CORPUS_ROLE_IS_PARSER_AND_SOURCE_REVIEW_DEVELOPMENT_ONLY",
        "DOWNLOADED_ACCESSIONS_DO_NOT_COVER_LOCKED_CATALOG",
    ]


def test_complete_authorized_census_can_pass_coverage(tmp_path):
    paths = _write_inputs(tmp_path, "RESEARCH_CENSUS", 2)
    result = audit(
        paths["catalog"],
        paths["sample"],
        paths["source"],
        paths["manifest"],
        paths["atomic"],
        paths["rejections"],
        paths["gate"],
        paths["protocol"],
        tmp_path / "detail.csv",
        tmp_path / "report.json",
    )
    assert result["status"] == "RESEARCH_CENSUS_COVERAGE_PASSED"
    assert result["single_hypothesis_preregistration_allowed"] is True


def test_downloaded_document_without_atomic_or_rejection_is_unresolved(tmp_path):
    paths = _write_inputs(tmp_path, "RESEARCH_CENSUS", 2)
    atomic = pd.read_csv(paths["atomic"], dtype=str).iloc[:1]
    atomic.to_csv(paths["atomic"], index=False)

    result = audit(
        paths["catalog"],
        paths["sample"],
        paths["source"],
        paths["manifest"],
        paths["atomic"],
        paths["rejections"],
        paths["gate"],
        paths["protocol"],
        tmp_path / "detail.csv",
        tmp_path / "report.json",
    )

    assert result["unresolved_source_accessions"] == 1
    assert result["single_hypothesis_preregistration_allowed"] is False
    assert (
        "VALIDATED_DOCUMENTS_WITHOUT_ATOMIC_TRANSACTIONS_REQUIRE_REVIEW"
        in result["blocking_reasons"]
    )
