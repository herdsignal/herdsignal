"""고정 SEC submissions에서 issuer-linked Form 4 accession과 검수 표본을 잠근다."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

import pandas as pd

from herd.validation_universe import TICKERS


ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = Path(__file__).with_name("sec_form4_corpus_v1.json")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_protocol(path: Path = PROTOCOL) -> dict:
    protocol = json.loads(path.read_text(encoding="utf-8"))
    if protocol.get("status") != "LOCKED_BEFORE_ACCESSION_CATALOG":
        raise ValueError("Form 4 corpus protocol must be locked before catalog")
    forbidden = set(protocol.get("forbidden", []))
    if {"USE_PRICE_OUTCOMES", "TREAT_ALL_SALES_AS_BEARISH", "DROP_FOOTNOTES"} - forbidden:
        raise ValueError("Form 4 authority firewall is incomplete")
    return protocol


def _filing_rows(payload: dict) -> list[dict]:
    if "filings" in payload:
        payload = payload.get("filings", {}).get("recent", {})
    if not payload:
        return []
    lengths = {len(value) for value in payload.values() if isinstance(value, list)}
    if len(lengths) > 1:
        raise ValueError("SEC submissions columns have inconsistent lengths")
    count = next(iter(lengths), 0)
    return [
        {
            key: value[index] for key, value in payload.items()
            if isinstance(value, list)
        }
        for index in range(count)
    ]


def _selected_filing_rows(
    payload: dict, forms: set[str], start: str, end: str
):
    """대형 submissions 배열을 행 객체 전체로 펼치지 않고 필요한 공시만 순회한다."""
    if "filings" in payload:
        payload = payload.get("filings", {}).get("recent", {})
    if not payload:
        return
    columns = {
        key: value for key, value in payload.items()
        if isinstance(value, list)
    }
    lengths = {len(value) for value in columns.values()}
    if len(lengths) > 1:
        raise ValueError("SEC submissions columns have inconsistent lengths")
    form_values = columns.get("form", [])
    date_values = columns.get("filingDate", [])
    for index, form in enumerate(form_values):
        filing_date = str(date_values[index])
        if str(form) in forms and start <= filing_date <= end:
            yield {key: value[index] for key, value in columns.items()}


def _issuer_submission_files(corpus: Path) -> list[tuple[Path, list[Path]]]:
    raw = corpus / "raw"
    result = []
    for main in sorted(
        path
        for path in raw.glob("CIK*-submissions.json")
        if re.fullmatch(r"CIK\d{10}-submissions\.json", path.name)
    ):
        issuer = main.name[3:13]
        history = sorted(raw.glob(f"CIK{issuer}-history-*.json"))
        result.append((main, history))
    return result


def build_catalog(protocol_path: Path = PROTOCOL) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    protocol = load_protocol(protocol_path)
    scope = protocol["scope"]
    start, end = scope["start_inclusive"], scope["end_inclusive"]
    forms = set(scope["forms"])
    equities = set(TICKERS) - set(scope["context_only_tickers"])
    source_hashes, records = {}, {}
    issuer_tickers: dict[str, set[str]] = {}
    for relative in scope["submission_corpora"]:
        corpus = (ROOT / relative).resolve()
        if not corpus.is_relative_to(ROOT) or not corpus.is_dir():
            raise ValueError(f"unsafe or missing submissions corpus: {relative}")
        manifest = corpus / "manifest.json"
        source_hashes[relative] = _sha256(manifest)
        for main, history_files in _issuer_submission_files(corpus):
            payload = json.loads(main.read_text(encoding="utf-8"))
            issuer_cik = f"{int(payload['cik']):010d}"
            candidates = set(map(str.upper, payload.get("tickers", []))) & equities
            if not candidates:
                continue
            issuer_tickers.setdefault(issuer_cik, set()).update(candidates)
            for path in [main, *history_files]:
                filing_payload = payload if path == main else json.loads(path.read_text(encoding="utf-8"))
                for row in _selected_filing_rows(filing_payload, forms, start, end):
                    form = str(row.get("form", ""))
                    filing_date = str(row.get("filingDate", ""))
                    accession = str(row.get("accessionNumber", ""))
                    primary = str(row.get("primaryDocument", ""))
                    if not accession or not primary:
                        continue
                    reporting_owner_cik = f"{int(accession.split('-')[0]):010d}"
                    accession_compact = accession.replace("-", "")
                    archive_document = Path(primary).name
                    source_url = (
                        f"https://www.sec.gov/Archives/edgar/data/{int(reporting_owner_cik)}/"
                        f"{accession_compact}/{archive_document}"
                    )
                    key = (issuer_cik, accession)
                    candidate = {
                        "issuer_cik": issuer_cik,
                        "candidate_tickers": "",
                        "reporting_owner_cik": reporting_owner_cik,
                        "accession_number": accession,
                        "form": form,
                        "filing_date": filing_date,
                        "report_date": str(row.get("reportDate", "")),
                        "acceptance_datetime": str(row.get("acceptanceDateTime", "")),
                        "primary_document": primary,
                        "source_url": source_url,
                    }
                    previous = records.get(key)
                    if previous is not None and previous != candidate:
                        raise ValueError(f"conflicting accession metadata: {key}")
                    records[key] = candidate
    for (issuer_cik, _), row in records.items():
        row["candidate_tickers"] = "|".join(sorted(issuer_tickers[issuer_cik]))
    catalog = pd.DataFrame(records.values()).sort_values(
        ["issuer_cik", "filing_date", "accession_number"]
    ).reset_index(drop=True)
    expected = equities
    covered = set(
        ticker for value in catalog["candidate_tickers"] for ticker in value.split("|")
    )
    if missing := expected - covered:
        raise ValueError(f"Form 4 accession coverage missing equities: {sorted(missing)}")
    limit = int(protocol["review_sample"]["maximum_accessions_per_issuer_year"])
    catalog["calendar_year"] = catalog["filing_date"].str[:4].astype(int)
    catalog["selection_hash"] = catalog.apply(
        lambda row: hashlib.sha256(
            f"{row.issuer_cik}|{row.calendar_year}|{row.accession_number}".encode()
        ).hexdigest(),
        axis=1,
    )
    sample = (
        catalog.sort_values(["issuer_cik", "calendar_year", "selection_hash"])
        .groupby(["issuer_cik", "calendar_year"], sort=True, group_keys=False)
        .head(limit)
        .sort_values(["issuer_cik", "filing_date", "accession_number"])
        .reset_index(drop=True)
    )
    report = {
        "report_version": "HERD_SEC_FORM4_ACCESSION_CATALOG_V1",
        "status": "ACCESSION_CATALOG_AND_SOURCE_SAMPLE_LOCKED",
        "protocol_sha256": _sha256(protocol_path),
        "source_manifest_hashes": source_hashes,
        "accessions": len(catalog),
        "issuers": int(catalog["issuer_cik"].nunique()),
        "covered_tickers": len(covered),
        "first_filing_date": catalog["filing_date"].min(),
        "last_filing_date": catalog["filing_date"].max(),
        "form_counts": catalog["form"].value_counts().to_dict(),
        "missing_acceptance_datetimes": int(
            catalog["acceptance_datetime"].fillna("").eq("").sum()
        ),
        "review_source_accessions": len(sample),
        "review_source_issuers": int(sample["issuer_cik"].nunique()),
        "review_source_years": int(sample["calendar_year"].nunique()),
        "selection_used_transaction_content": False,
        "selection_used_price_outcome": False,
        "price_outcomes_opened": False,
        "direction_hypothesis_allowed": False,
        "operational_action_authority": False,
        "blind_holdout_access": False,
        "next_decision": "COLLECT_HASH_LOCKED_PRIMARY_XML",
    }
    return catalog, sample, report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, default=PROTOCOL)
    parser.add_argument("--catalog-output", type=Path, required=True)
    parser.add_argument("--sample-output", type=Path, required=True)
    parser.add_argument("--report-output", type=Path, required=True)
    args = parser.parse_args()
    catalog, sample, report = build_catalog(args.protocol)
    args.catalog_output.parent.mkdir(parents=True, exist_ok=True)
    catalog.to_csv(args.catalog_output, index=False)
    sample.to_csv(args.sample_output, index=False)
    report["catalog_sha256"] = _sha256(args.catalog_output)
    report["review_sample_sha256"] = _sha256(args.sample_output)
    args.report_output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
