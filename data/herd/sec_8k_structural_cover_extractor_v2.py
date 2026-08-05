"""SEC 8-K 표지의 실제 Trading Symbol 열에서 후보를 추출한다."""

from __future__ import annotations

import csv
import hashlib
import json
import re
from pathlib import Path
from typing import Any

from lxml import html

from herd.sec_targeted_cover_corpus_v2 import extract_tagged_trading_symbols


ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = Path(__file__).with_suffix(".json")
SYMBOL = re.compile(r"^[A-Z][A-Z0-9./-]{0,14}$")
FIELDS = [
    "accession_number",
    "cik",
    "filing_date",
    "prior_extraction_status",
    "extraction_method",
    "candidate_symbols",
    "source_sha256",
    "review_role",
    "development_regression_status",
]


class Sec8KStructuralCoverExtractorError(ValueError):
    """잠긴 입력이나 fail-closed 권한이 바뀌면 발생한다."""


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _rooted(relative: str) -> Path:
    path = (ROOT / relative).resolve()
    if not path.is_relative_to(ROOT):
        raise Sec8KStructuralCoverExtractorError(f"path escapes repository: {relative}")
    return path


def _locked_paths(protocol: dict[str, Any]) -> dict[str, Path]:
    paths = {}
    for item in protocol["locked_inputs"]:
        path = _rooted(item["path"])
        if not path.is_file() or _sha256(path) != item["sha256"]:
            raise Sec8KStructuralCoverExtractorError(f"locked input changed: {item['path']}")
        paths[item["role"]] = path
    return paths


def extract_structural_symbols(
    content: bytes,
    *,
    maximum_rows: int = 15,
    rejected: set[str] | None = None,
) -> list[str]:
    """Trading Symbol 헤더와 같은 열의 후속 셀만 읽는다."""
    rejected = rejected or {"DIV", "TD"}
    try:
        document = html.fromstring(content)
    except (ValueError, html.etree.ParserError):
        return []
    symbols = set()
    for table in document.xpath("//table"):
        rows = table.xpath(".//tr")
        for index, row in enumerate(rows):
            cells = row.xpath("./th|./td")
            values = [" ".join(cell.text_content().split()) for cell in cells]
            columns = [
                column
                for column, value in enumerate(values)
                if re.search(r"Trading\s+Symbol(?:\(s\))?", value, re.IGNORECASE)
            ]
            for column in columns:
                for data_row in rows[index + 1:index + 1 + maximum_rows]:
                    data_cells = data_row.xpath("./th|./td")
                    if column >= len(data_cells):
                        continue
                    candidate = " ".join(data_cells[column].text_content().split()).upper()
                    if SYMBOL.fullmatch(candidate) and candidate not in rejected:
                        symbols.add(candidate)
    return sorted(symbols)


def build(protocol_path: Path = PROTOCOL) -> tuple[list[dict[str, str]], dict[str, Any]]:
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    expected_authority = {
        "identity_promotion_allowed": False,
        "price_outcomes_opened": False,
        "direction_hypothesis_allowed": False,
        "blind_holdout_access": False,
        "operational_action_ratio": 0.0,
    }
    if (
        protocol.get("status") != "LOCKED_DEVELOPMENT_AFTER_FAILURE_AUDIT"
        or protocol.get("authority") != expected_authority
        or protocol["evaluation"]["independent_precision_claim_allowed"] is not False
    ):
        raise Sec8KStructuralCoverExtractorError("V2 extractor is not fail-closed")
    paths = _locked_paths(protocol)
    failure = json.loads(paths["FAILURE_AUDIT"].read_text(encoding="utf-8"))
    if failure.get("status") != "FAILURE_AUDIT_COMPLETE_PARSER_CHANGE_ALLOWED":
        raise Sec8KStructuralCoverExtractorError("failure audit does not allow parser development")
    with paths["COLLECTION_INDEX"].open(newline="", encoding="utf-8") as handle:
        collection = list(csv.DictReader(handle))
    with paths["SOURCE_REVIEW_LABELS"].open(newline="", encoding="utf-8") as handle:
        labels = {row["accession_number"]: row for row in csv.DictReader(handle)}
    snapshot = paths["LOCAL_SNAPSHOT_MANIFEST"].parent
    config = protocol["parser"]
    rejected = set(config["rejected_markup_tokens"])
    rows = []
    for source in collection:
        raw = snapshot / "raw" / f"{source['accession_number']}.html"
        if not raw.is_file() or _sha256(raw) != source["source_sha256"]:
            raise Sec8KStructuralCoverExtractorError(
                f"source bytes changed: {source['accession_number']}"
            )
        content = raw.read_bytes()
        tagged = extract_tagged_trading_symbols(content)
        symbols = tagged or extract_structural_symbols(
            content,
            maximum_rows=config["maximum_data_rows_after_header"],
            rejected=rejected,
        )
        label = labels.get(source["accession_number"])
        regression = "NOT_REVIEWED"
        if label:
            if label["decision"] == "VALID":
                regression = (
                    "PASS" if label["approved_symbol"] in symbols else "FAIL_APPROVED_SYMBOL_MISSING"
                )
            else:
                regression = (
                    "PASS" if symbols and not (set(symbols) & rejected) else "FAIL_FALSE_TOKEN_RETAINED"
                )
        rows.append({
            "accession_number": source["accession_number"],
            "cik": source["cik"],
            "filing_date": source["filing_date"],
            "prior_extraction_status": source["extraction_status"],
            "extraction_method": "XBRL_TAG" if tagged else "STRUCTURAL_TRADING_SYMBOL_COLUMN" if symbols else "NONE",
            "candidate_symbols": "|".join(symbols),
            "source_sha256": source["source_sha256"],
            "review_role": "DEVELOPMENT_REGRESSION" if label else "UNSEEN_HUMAN_REVIEW",
            "development_regression_status": regression,
        })
    regression = [row for row in rows if row["review_role"] == "DEVELOPMENT_REGRESSION"]
    unseen = [row for row in rows if row["review_role"] == "UNSEEN_HUMAN_REVIEW"]
    unseen_candidates = [row for row in unseen if row["candidate_symbols"]]
    report = {
        "report_version": protocol["protocol_version"],
        "status": "V2_DEVELOPMENT_COMPLETE_UNSEEN_REVIEW_REQUIRED",
        "documents": len(rows),
        "candidate_documents": sum(bool(row["candidate_symbols"]) for row in rows),
        "development_regression_rows": len(regression),
        "development_regression_passed": sum(
            row["development_regression_status"] == "PASS" for row in regression
        ),
        "unseen_rows": len(unseen),
        "unseen_candidate_rows": len(unseen_candidates),
        "unseen_candidate_accessions": [row["accession_number"] for row in unseen_candidates],
        "independent_precision_claim_allowed": False,
        "identity_promotion_allowed": False,
        "price_outcomes_opened": False,
        "direction_hypothesis_allowed": False,
        "blind_holdout_access": False,
        "operational_action_ratio": 0.0,
        "next_stage": protocol["next_stage"],
    }
    return rows, report


def run() -> dict[str, Any]:
    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    rows, report = build()
    csv_path = _rooted(protocol["outputs"]["candidates"])
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    report["candidates_path"] = protocol["outputs"]["candidates"]
    report["candidates_sha256"] = _sha256(csv_path)
    report_path = _rooted(protocol["outputs"]["report"])
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False, indent=2))
