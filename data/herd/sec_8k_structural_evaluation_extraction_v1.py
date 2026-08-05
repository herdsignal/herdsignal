"""잠긴 구조적 표지 파서 V2를 독립 SEC 원문에 변경 없이 실행한다."""

from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

from herd.sec_8k_structural_cover_extractor_v2 import extract_structural_symbols
from herd.sec_targeted_cover_corpus_v2 import extract_tagged_trading_symbols


ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = Path(__file__).with_suffix(".json")
FIELDS = [
    "evaluation_id",
    "accession_number",
    "cik",
    "filing_date",
    "matched_items",
    "extraction_method",
    "candidate_symbols",
    "source_sha256",
    "review_status",
]


class Sec8KStructuralEvaluationExtractionError(ValueError):
    """잠긴 파서나 독립 원문이 바뀌면 발생한다."""


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _rooted(relative: str) -> Path:
    path = (ROOT / relative).resolve()
    if not path.is_relative_to(ROOT):
        raise Sec8KStructuralEvaluationExtractionError(
            f"path escapes repository: {relative}"
        )
    return path


def _locked_paths(protocol: dict[str, Any]) -> dict[str, Path]:
    paths = {}
    for item in protocol["locked_inputs"]:
        path = _rooted(item["path"])
        if not path.is_file() or _sha256(path) != item["sha256"]:
            raise Sec8KStructuralEvaluationExtractionError(
                f"locked input changed: {item['path']}"
            )
        paths[item["role"]] = path
    return paths


def build(protocol_path: Path = PROTOCOL) -> tuple[list[dict[str, str]], dict[str, Any]]:
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    if (
        protocol.get("status") != "LOCKED_PARSER_BEFORE_INDEPENDENT_EXTRACTION"
        or protocol["parser"]["code_changes_allowed_after_lock"] is not False
        or protocol["authority"]["operational_action_ratio"] != 0.0
        or protocol["authority"]["identity_promotion_allowed"] is not False
    ):
        raise Sec8KStructuralEvaluationExtractionError(
            "independent extraction is not fail-closed"
        )
    paths = _locked_paths(protocol)
    collection = json.loads(paths["COLLECTION_REPORT"].read_text(encoding="utf-8"))
    if (
        collection.get("status") != "INDEPENDENT_PRIMARY_DOCUMENTS_COLLECTED"
        or collection.get("failed_documents") != 0
        or collection.get("canonical_symbols_exposed") != 0
    ):
        raise Sec8KStructuralEvaluationExtractionError(
            "independent collection is not extraction-ready"
        )
    with paths["COLLECTION_INDEX"].open(newline="", encoding="utf-8") as handle:
        sources = list(csv.DictReader(handle))
    snapshot = paths["SNAPSHOT_MANIFEST"].parent
    config = protocol["parser"]
    rows = []
    for source in sources:
        raw = snapshot / "raw" / f"{source['accession_number']}.html"
        if not raw.is_file() or _sha256(raw) != source["source_sha256"]:
            raise Sec8KStructuralEvaluationExtractionError(
                f"source bytes changed: {source['accession_number']}"
            )
        content = raw.read_bytes()
        tagged = extract_tagged_trading_symbols(content)
        symbols = tagged or extract_structural_symbols(
            content,
            maximum_rows=config["maximum_data_rows_after_header"],
            rejected=set(config["rejected_markup_tokens"]),
        )
        rows.append({
            "evaluation_id": source["evaluation_id"],
            "accession_number": source["accession_number"],
            "cik": source["cik"],
            "filing_date": source["filing_date"],
            "matched_items": source["matched_items"],
            "extraction_method": "XBRL_TAG" if tagged else "STRUCTURAL_TRADING_SYMBOL_COLUMN" if symbols else "NONE",
            "candidate_symbols": "|".join(symbols),
            "source_sha256": source["source_sha256"],
            "review_status": "PENDING" if symbols else "NO_CANDIDATE",
        })
    counts = Counter(row["extraction_method"] for row in rows)
    candidates = [row for row in rows if row["candidate_symbols"]]
    report = {
        "report_version": protocol["protocol_version"],
        "status": "INDEPENDENT_EXTRACTION_COMPLETE_SOURCE_REVIEW_REQUIRED",
        "documents": len(rows),
        "candidate_rows": len(candidates),
        "no_candidate_rows": len(rows) - len(candidates),
        "candidate_issuers": len({row["cik"] for row in candidates}),
        "extraction_method_counts": dict(sorted(counts.items())),
        "parser_code_sha256": _sha256(paths["FROZEN_PARSER_CODE"]),
        "parser_changed_after_lock": False,
        "human_labels_created": 0,
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
    candidates_path = _rooted(protocol["outputs"]["candidates"])
    with candidates_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    report["candidates_path"] = protocol["outputs"]["candidates"]
    report["candidates_sha256"] = _sha256(candidates_path)
    report_path = _rooted(protocol["outputs"]["report"])
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return report


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False, indent=2))
