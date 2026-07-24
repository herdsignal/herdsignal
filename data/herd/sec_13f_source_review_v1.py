"""13F PIT 원장을 잠긴 층화 표본의 SEC 원문과 직접 교차검증한다."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import shutil
import sqlite3
import time
import uuid
import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import requests

from herd.sec_13f_pit_holdings_v1 import (
    DATABASE,
    REPORT as PIT_REPORT,
    Sec13fPitHoldingsError,
    next_market_session,
)
from herd.sec_13f_security_ledger_v1 import ROOT, sha256
from herd.sec_guidance_table_review_gate_v1 import wilson_lower
from herd.sec_master_index import resolve_user_agent


CONTRACT = ROOT / "data/herd/sec_13f_source_review_v1.json"
SAMPLE = ROOT / "data/reports/sec_13f_source_review_sample_v1.csv"
REVIEW = ROOT / "data/reports/sec_13f_source_review_v1.csv"
REPORT = ROOT / "data/reports/sec_13f_source_review_v1.json"
CORPUS = ROOT / "data/reference/sec/sec-13f-source-review-v1"
DOWNLOAD_CACHE = ROOT / "data/reference/sec/.sec-13f-source-review-v1-cache"
FORMAT_VERSION = "SEC_13F_SOURCE_REVIEW_V1"
ACCEPTANCE_PATTERN = re.compile(
    rb"<ACCEPTANCE-DATETIME>\s*(\d{14})", re.IGNORECASE
)
SUBMISSION_TYPE_PATTERN = re.compile(
    rb"(?:<CONFORMED-SUBMISSION-TYPE>\s*|"
    rb"CONFORMED SUBMISSION TYPE:\s*)([^\r\n<]+)",
    re.IGNORECASE,
)
XML_BLOCK_PATTERN = re.compile(
    rb"<XML>\s*(.*?)\s*</XML>", re.IGNORECASE | re.DOTALL
)


class Sec13fSourceReviewError(RuntimeError):
    """SEC 원문 표본·해시·구조 대조 경계 위반 시 발생한다."""


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].lower()


def _text(element: ET.Element, name: str) -> str:
    target = name.lower()
    for child in element.iter():
        if _local_name(child.tag) == target:
            return (child.text or "").strip()
    return ""


def _int_text(element: ET.Element, name: str) -> int:
    value = _text(element, name)
    if not value:
        return 0
    return int(value.replace(",", ""))


def _era(year: int, eras: dict[str, list[int]]) -> str:
    for label, (start, end) in eras.items():
        if start <= year <= end:
            return label
    raise Sec13fSourceReviewError(f"filing year outside locked eras: {year}")


def _rank(seed: str, *values: str) -> str:
    return hashlib.sha256("|".join((seed, *values)).encode()).hexdigest()


def _first_event_amendments(connection: sqlite3.Connection) -> set[str]:
    return {
        row[0]
        for row in connection.execute(
            """
            WITH ordered AS (
                SELECT accession_number, is_amendment,
                       ROW_NUMBER() OVER (
                           PARTITION BY manager_cik, report_period
                           ORDER BY availability_date, filing_date,
                                    accession_number
                       ) AS sequence_number
                FROM filings
            )
            SELECT accession_number FROM ordered
            WHERE sequence_number=1 AND is_amendment=1
            """
        )
    }


def _representative_holding(
    connection: sqlite3.Connection,
    accession: str,
    seed: str,
) -> sqlite3.Row:
    rows = connection.execute(
        """
        SELECT * FROM holdings
        WHERE accession_number=?
        ORDER BY ticker, cusip
        """,
        (accession,),
    ).fetchall()
    if not rows:
        raise Sec13fSourceReviewError(
            f"sampled filing has no mapped holding: {accession}"
        )
    return min(
        rows,
        key=lambda row: _rank(seed, accession, str(row["cusip"])),
    )


def build_locked_sample(
    connection: sqlite3.Connection,
    contract: dict[str, Any],
) -> list[dict[str, str]]:
    connection.row_factory = sqlite3.Row
    sampling = contract["sampling"]
    seed = sampling["seed"]
    eras = sampling["eras"]
    candidates: dict[tuple[str, str], list[sqlite3.Row]] = defaultdict(list)
    filings = connection.execute(
        """
        SELECT * FROM filings
        ORDER BY filing_date, accession_number
        """
    ).fetchall()
    for filing in filings:
        label = _era(
            date.fromisoformat(filing["filing_date"]).year,
            eras,
        )
        candidates[(filing["amendment_operation"], label)].append(filing)

    selected: dict[str, tuple[sqlite3.Row, str]] = {}
    for operation, per_era in sampling["per_era_targets"].items():
        for era_label in eras:
            ranked = sorted(
                candidates[(operation, era_label)],
                key=lambda row: _rank(seed, operation, era_label, row["accession_number"]),
            )
            if len(ranked) < per_era:
                raise Sec13fSourceReviewError(
                    f"source review stratum underfilled: "
                    f"{operation}/{era_label}={len(ranked)}<{per_era}"
                )
            for filing in ranked[:per_era]:
                selected[filing["accession_number"]] = (
                    filing,
                    f"{operation}__{era_label}",
                )
    for operation in sampling.get("include_all_operations", []):
        for era_label in eras:
            for filing in candidates[(operation, era_label)]:
                selected[filing["accession_number"]] = (
                    filing,
                    f"{operation}__{era_label}",
                )

    first_events = _first_event_amendments(connection)
    selected_first = first_events & set(selected)
    required_first = sampling["minimum_first_event_amendments"]
    if len(selected_first) < required_first:
        by_accession = {
            filing["accession_number"]: filing for filing in filings
        }
        remaining = sorted(
            first_events - set(selected),
            key=lambda accession: _rank(seed, "FIRST_EVENT", accession),
        )
        for accession in remaining[: required_first - len(selected_first)]:
            filing = by_accession[accession]
            selected[accession] = (
                filing,
                f"FIRST_EVENT_AMENDMENT__{_era(date.fromisoformat(filing['filing_date']).year, eras)}",
            )

    sample: list[dict[str, str]] = []
    for accession, (filing, stratum) in sorted(selected.items()):
        holding = _representative_holding(connection, accession, seed)
        accession_compact = accession.replace("-", "")
        source_url = (
            "https://www.sec.gov/Archives/edgar/data/"
            f"{int(filing['manager_cik'])}/{accession_compact}/"
            f"{accession}.txt"
        )
        sample.append(
            {
                "sample_id": f"13FSR-{len(sample) + 1:04d}",
                "stratum": stratum,
                "first_event_amendment": str(accession in first_events).lower(),
                "accession_number": accession,
                "manager_cik": filing["manager_cik"],
                "manager_name": filing["manager_name"],
                "report_period": filing["report_period"],
                "filing_date": filing["filing_date"],
                "conservative_availability_date": filing["availability_date"],
                "submission_type": filing["submission_type"],
                "amendment_type": filing["amendment_type"],
                "amendment_operation": filing["amendment_operation"],
                "amendment_usable": str(filing["amendment_usable"]),
                "ticker": holding["ticker"],
                "issuer_cik": holding["issuer_cik"],
                "cusip": holding["cusip"],
                "expected_issuer_names": holding["issuer_names"],
                "expected_class_titles": holding["class_titles"],
                "expected_reported_value": str(holding["reported_value"]),
                "expected_reported_shares": str(holding["reported_shares"]),
                "expected_investment_discretions": holding[
                    "investment_discretions"
                ],
                "expected_voting_sole": str(holding["voting_sole"]),
                "expected_voting_shared": str(holding["voting_shared"]),
                "expected_voting_none": str(holding["voting_none"]),
                "source_url": source_url,
            }
        )
    return sample


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        raise Sec13fSourceReviewError(f"cannot write empty CSV: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=list(rows[0]),
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)


def _xml_roots(content: bytes) -> list[ET.Element]:
    roots = []
    for block in XML_BLOCK_PATTERN.findall(content):
        try:
            roots.append(ET.fromstring(block.strip()))
        except ET.ParseError:
            continue
    return roots


def _normalize_cusip(value: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", value.upper())


def _parse_original_submission(
    content: bytes,
    expected_cusip: str,
) -> dict[str, Any]:
    acceptance_match = ACCEPTANCE_PATTERN.search(content)
    if acceptance_match is None:
        raise Sec13fSourceReviewError("SEC submission lacks acceptance datetime")
    acceptance = datetime.strptime(
        acceptance_match.group(1).decode(),
        "%Y%m%d%H%M%S",
    ).replace(tzinfo=timezone.utc)
    submission_type_match = SUBMISSION_TYPE_PATTERN.search(content)
    if submission_type_match is None:
        raise Sec13fSourceReviewError("SEC submission lacks conformed type")
    roots = _xml_roots(content)
    cover = next(
        (
            root
            for root in roots
            if _local_name(root.tag) in {"edgarsubmission", "form13ffiler"}
            or _text(root, "reportCalendarOrQuarter")
        ),
        None,
    )
    information = next(
        (
            root
            for root in roots
            if _local_name(root.tag) == "informationtable"
        ),
        None,
    )
    if cover is None or information is None:
        raise Sec13fSourceReviewError(
            "SEC submission lacks cover or information table XML"
        )

    matching_entries = []
    for entry in information.iter():
        if _local_name(entry.tag) != "infotable":
            continue
        if _normalize_cusip(_text(entry, "cusip")) != expected_cusip:
            continue
        if _text(entry, "putCall"):
            continue
        if _text(entry, "sshPrnamtType").upper() != "SH":
            continue
        matching_entries.append(entry)
    if not matching_entries:
        raise Sec13fSourceReviewError(
            f"expected CUSIP missing in SEC information table: {expected_cusip}"
        )

    issuer_names = sorted({_text(row, "nameOfIssuer") for row in matching_entries})
    class_titles = sorted({_text(row, "titleOfClass") for row in matching_entries})
    discretions = sorted(
        {_text(row, "investmentDiscretion") for row in matching_entries}
    )
    amendment_type = _text(cover, "amendmentType").upper()
    return {
        "acceptance_datetime": acceptance.isoformat().replace("+00:00", "Z"),
        "acceptance_date": acceptance.date().isoformat(),
        "submission_type": submission_type_match.group(1)
        .decode()
        .strip()
        .upper(),
        "manager_cik": _text(cover, "cik").zfill(10),
        "report_period": datetime.strptime(
            _text(cover, "reportCalendarOrQuarter"),
            "%m-%d-%Y",
        ).date().isoformat(),
        "is_amendment": _text(cover, "isAmendment").lower()
        in {"true", "1", "y"},
        "amendment_type": re.sub(r"\s+", " ", amendment_type),
        "issuer_names": "|".join(issuer_names),
        "class_titles": "|".join(class_titles),
        "reported_value": sum(_int_text(row, "value") for row in matching_entries),
        "reported_shares": sum(
            _int_text(row, "sshPrnamt") for row in matching_entries
        ),
        "investment_discretions": "|".join(discretions),
        "voting_sole": sum(_int_text(row, "sole") for row in matching_entries),
        "voting_shared": sum(_int_text(row, "shared") for row in matching_entries),
        "voting_none": sum(_int_text(row, "none") for row in matching_entries),
    }


def _expected_is_amendment(row: dict[str, str]) -> bool:
    return row["submission_type"].endswith("/A")


def _compare(row: dict[str, str], actual: dict[str, Any]) -> list[str]:
    mismatches = []
    expected: dict[str, Any] = {
        "manager_cik": row["manager_cik"],
        "report_period": row["report_period"],
        "submission_type": row["submission_type"],
        "amendment_type": row["amendment_type"],
        "issuer_names": row["expected_issuer_names"],
        "class_titles": row["expected_class_titles"],
        "reported_value": int(row["expected_reported_value"]),
        "reported_shares": int(row["expected_reported_shares"]),
        "investment_discretions": row[
            "expected_investment_discretions"
        ],
        "voting_sole": int(row["expected_voting_sole"]),
        "voting_shared": int(row["expected_voting_shared"]),
        "voting_none": int(row["expected_voting_none"]),
    }
    for field, expected_value in expected.items():
        if actual[field] != expected_value:
            mismatches.append(field)
    if (
        row["amendment_operation"]
        != "EXCLUDE_UNKNOWN_AMENDMENT_SEMANTICS"
        and actual["is_amendment"] != _expected_is_amendment(row)
    ):
        mismatches.append("is_amendment")
    conservative = next_market_session(
        date.fromisoformat(actual["acceptance_date"])
    ).isoformat()
    if row["conservative_availability_date"] < conservative:
        mismatches.append("availability_before_exact_acceptance")
    return mismatches


def _download_with_retry(
    client: requests.Session,
    url: str,
    *,
    attempts: int = 6,
) -> bytes:
    for attempt in range(attempts):
        response = client.get(url, timeout=90)
        if response.status_code < 400:
            return response.content
        if response.status_code not in {403, 429, 500, 502, 503, 504}:
            response.raise_for_status()
        if attempt == attempts - 1:
            response.raise_for_status()
        retry_after = response.headers.get("Retry-After", "")
        delay = float(retry_after) if retry_after.isdigit() else min(
            2**attempt, 16
        )
        time.sleep(delay)
    raise AssertionError("unreachable")


def collect_and_review(
    sample: list[dict[str, str]],
    corpus_path: Path,
    *,
    user_agent: str,
    session: requests.Session | None = None,
    delay_seconds: float = 0.12,
    cache_path: Path = DOWNLOAD_CACHE,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    temporary = corpus_path.parent / f".{corpus_path.name}.tmp-{uuid.uuid4().hex}"
    raw_dir = temporary / "raw"
    raw_dir.mkdir(parents=True)
    client = session or requests.Session()
    client.headers.update(
        {"User-Agent": user_agent, "Accept-Encoding": "gzip, deflate"}
    )
    cache_path.mkdir(parents=True, exist_ok=True)
    reviewed = []
    documents = []
    try:
        for index, row in enumerate(sample, start=1):
            cached = cache_path / f"{row['accession_number']}.txt"
            if cached.is_file():
                content = cached.read_bytes()
            else:
                content = _download_with_retry(client, row["source_url"])
                cached.write_bytes(content)
            if row["accession_number"].encode() not in content[:20_000]:
                raise Sec13fSourceReviewError(
                    f"wrong SEC submission returned: {row['accession_number']}"
                )
            digest = hashlib.sha256(content).hexdigest()
            raw_path = raw_dir / f"{digest}.txt"
            if raw_path.exists() and raw_path.read_bytes() != content:
                raise Sec13fSourceReviewError("SHA-256 content collision")
            raw_path.write_bytes(content)
            try:
                actual = _parse_original_submission(content, row["cusip"])
                mismatches = _compare(row, actual)
                status = "VALID" if not mismatches else "INVALID"
                error = ""
            except Exception as source_error:
                actual = {
                    "acceptance_datetime": "",
                    "acceptance_date": "",
                    "submission_type": "",
                }
                mismatches = ["SOURCE_PARSE"]
                status = "INVALID"
                error = f"{type(source_error).__name__}: {source_error}"
            reviewed.append(
                {
                    **row,
                    "source_sha256": digest,
                    "source_bytes": len(content),
                    "acceptance_datetime": actual["acceptance_datetime"],
                    "exact_availability_date": (
                        next_market_session(
                            date.fromisoformat(actual["acceptance_date"])
                        ).isoformat()
                        if actual["acceptance_date"]
                        else ""
                    ),
                    "validation_status": status,
                    "mismatch_fields": "|".join(mismatches),
                    "validation_error": error,
                }
            )
            documents.append(
                {
                    "accession_number": row["accession_number"],
                    "source_url": row["source_url"],
                    "sha256": digest,
                    "bytes": len(content),
                    "path": f"raw/{raw_path.name}",
                }
            )
            print(
                f"[13F source review] {index}/{len(sample)} "
                f"{row['accession_number']} {status} "
                f"{'|'.join(mismatches) if mismatches else ''}",
                flush=True,
            )
            if session is None:
                time.sleep(delay_seconds)
        index_path = temporary / "index.csv"
        _write_csv(index_path, documents)
        manifest = {
            "format_version": FORMAT_VERSION,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "source": "SEC_EDGAR_COMPLETE_SUBMISSION_TEXT",
            "documents": len(documents),
            "bytes": sum(item["bytes"] for item in documents),
            "index_sha256": sha256(index_path),
            "price_outcomes_opened": False,
        }
        (temporary / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        if corpus_path.exists():
            shutil.rmtree(corpus_path)
        temporary.rename(corpus_path)
        return reviewed, manifest
    except BaseException:
        shutil.rmtree(temporary, ignore_errors=True)
        raise


def _verify_corpus(
    corpus_path: Path,
    manifest: dict[str, Any],
) -> int:
    index_path = corpus_path / "index.csv"
    if not index_path.is_file() or sha256(index_path) != manifest["index_sha256"]:
        return 1
    mismatches = 0
    with index_path.open(newline="", encoding="utf-8") as handle:
        documents = list(csv.DictReader(handle))
    if len(documents) != manifest["documents"]:
        mismatches += 1
    for document in documents:
        path = corpus_path / document["path"]
        if (
            not path.is_file()
            or sha256(path) != document["sha256"]
            or path.stat().st_size != int(document["bytes"])
        ):
            mismatches += 1
    return mismatches


def _gate_report(
    contract: dict[str, Any],
    sample: list[dict[str, str]],
    reviewed: list[dict[str, Any]],
    manifest: dict[str, Any],
) -> dict[str, Any]:
    gates = contract["gates"]
    valid = sum(row["validation_status"] == "VALID" for row in reviewed)
    lower = wilson_lower(valid, len(reviewed))
    exact_acceptance = sum(bool(row["acceptance_datetime"]) for row in reviewed)
    future_rows = sum(
        bool(row["acceptance_datetime"])
        and row["conservative_availability_date"]
        <= row["acceptance_datetime"][:10]
        for row in reviewed
    )
    source_hash_mismatches = _verify_corpus(CORPUS, manifest)
    results = {
        "minimum_locked_rows": len(sample) >= gates["minimum_locked_rows"],
        "minimum_distinct_managers": len(
            {row["manager_cik"] for row in sample}
        )
        >= gates["minimum_distinct_managers"],
        "minimum_distinct_securities": len({row["cusip"] for row in sample})
        >= gates["minimum_distinct_securities"],
        "minimum_distinct_eras": len(
            {row["stratum"].rsplit("__", 1)[-1] for row in sample}
        )
        >= gates["minimum_distinct_eras"],
        "minimum_first_event_amendments": sum(
            row["first_event_amendment"] == "true" for row in sample
        )
        >= gates["minimum_first_event_amendments"],
        "minimum_exact_acceptance_fraction": (
            exact_acceptance / len(reviewed)
            >= gates["minimum_exact_acceptance_fraction"]
        ),
        "minimum_wilson_95_lower_bound": (
            lower is not None
            and lower >= gates["minimum_wilson_95_lower_bound"]
        ),
        "maximum_source_hash_mismatches": (
            source_hash_mismatches
            <= gates["maximum_source_hash_mismatches"]
        ),
        "maximum_future_available_rows": (
            future_rows <= gates["maximum_future_available_rows"]
        ),
    }
    passed = all(results.values())
    return {
        "report_version": FORMAT_VERSION,
        "status": (
            "STRATIFIED_SEC_SOURCE_REVIEW_GATE_PASSED"
            if passed
            else "STRATIFIED_SEC_SOURCE_REVIEW_GATE_FAILED"
        ),
        "sample": {
            "path": SAMPLE.relative_to(ROOT).as_posix(),
            "sha256": sha256(SAMPLE),
            "rows": len(sample),
            "distinct_managers": len({row["manager_cik"] for row in sample}),
            "distinct_securities": len({row["cusip"] for row in sample}),
            "first_event_amendments": sum(
                row["first_event_amendment"] == "true" for row in sample
            ),
        },
        "review": {
            "path": REVIEW.relative_to(ROOT).as_posix(),
            "sha256": sha256(REVIEW),
            "valid": valid,
            "invalid": len(reviewed) - valid,
            "wilson_95_lower_bound": lower,
            "exact_acceptance_rows": exact_acceptance,
        },
        "corpus": {
            "path": corpus_path_string(CORPUS),
            "manifest_sha256": sha256(CORPUS / "manifest.json"),
            "documents": manifest["documents"],
            "bytes": manifest["bytes"],
            "hash_mismatches": source_hash_mismatches,
        },
        "gate_results": results,
        "price_outcomes_opened": False,
        "direction_hypothesis_executed": False,
        "operational_action_ratio": 0.0,
        "blind_holdout_access": False,
        "next_step": (
            "BUILD_13F_SLOW_CONTEXT_FEATURES"
            if passed
            else "STOP_AND_REPAIR_13F_SOURCE_LEDGER"
        ),
    }


def corpus_path_string(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def generate(
    *,
    database_path: Path = DATABASE,
    contract_path: Path = CONTRACT,
    sample_path: Path = SAMPLE,
    review_path: Path = REVIEW,
    report_path: Path = REPORT,
    corpus_path: Path = CORPUS,
    env_file: Path = ROOT / ".env",
    session: requests.Session | None = None,
) -> dict[str, Any]:
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    pit_report = json.loads(PIT_REPORT.read_text(encoding="utf-8"))
    expected = contract["input_report"]["required_status"]
    if pit_report["status"] != expected:
        raise Sec13fSourceReviewError("PIT holdings input gate is not passed")
    try:
        connection = sqlite3.connect(database_path)
        sample = build_locked_sample(connection, contract)
    finally:
        connection.close()
    _write_csv(sample_path, sample)
    user_agent = (
        "HerdSignal test research@example.com"
        if session is not None
        else resolve_user_agent(env_file)
    )
    reviewed, manifest = collect_and_review(
        sample,
        corpus_path,
        user_agent=user_agent,
        session=session,
        delay_seconds=0.0 if session is not None else 0.12,
    )
    _write_csv(review_path, reviewed)
    report = _gate_report(contract, sample, reviewed, manifest)
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return report


def verify_outputs(report_path: Path = REPORT) -> dict[str, Any]:
    report = json.loads(report_path.read_text(encoding="utf-8"))
    if report.get("report_version") != FORMAT_VERSION:
        raise Sec13fSourceReviewError("unexpected 13F source review report")
    for key in ("sample", "review"):
        item = report[key]
        path = ROOT / item["path"]
        if not path.is_file() or sha256(path) != item["sha256"]:
            raise Sec13fSourceReviewError(
                f"source review output hash changed: {item['path']}"
            )
    manifest = CORPUS / "manifest.json"
    if (
        not manifest.is_file()
        or sha256(manifest) != report["corpus"]["manifest_sha256"]
    ):
        raise Sec13fSourceReviewError("source review corpus hash changed")
    manifest_data = json.loads(manifest.read_text(encoding="utf-8"))
    if _verify_corpus(CORPUS, manifest_data):
        raise Sec13fSourceReviewError("source review document hash changed")
    if report["price_outcomes_opened"] or report["blind_holdout_access"]:
        raise Sec13fSourceReviewError("research firewall changed")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    report = verify_outputs() if args.verify_only else generate()
    print(json.dumps(report, ensure_ascii=False))
    return 0 if report["status"].endswith("PASSED") else 1


if __name__ == "__main__":
    raise SystemExit(main())
