"""공식 근거로 누락된 과거 증권을 기준 구성에 진단 범위로 복원한다."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

from lxml import html
from pypdf import PdfReader

VERIFIED_STATUS = "VERIFIED_BASELINE_CONTINUITY_BACKCAST"
CORRECTION_TYPE = "RESTORE_MISSING_HISTORICAL_SECURITY"
OFFICIAL_HOSTS = {"press.spglobal.com", "www.spglobal.com"}


class BaselineCorrectionError(RuntimeError):
    pass


def _normalized_text(content: bytes, suffix: str) -> str:
    if suffix.lower() == ".pdf":
        reader = PdfReader(io.BytesIO(content))
        value = " ".join(page.extract_text() or "" for page in reader.pages)
    else:
        value = html.fromstring(content).text_content()
    return " ".join(value.split()).casefold()


def _read_csv(path: Path) -> list[dict]:
    with Path(path).open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def verify_baseline_corrections(
    claims: list[dict],
    release_index: list[dict],
    evidence_dir: Path,
    candidate_events: list[dict],
) -> tuple[list[dict], dict]:
    releases = {row["source_url"]: row for row in release_index}
    corrections = []
    seen_entities: set[str] = set()
    seen_tickers: set[str] = set()
    for claim in claims:
        as_of = date.fromisoformat(claim["as_of"])
        evidence_date = date.fromisoformat(claim["evidence_date"])
        ticker = claim["ticker"].upper()
        entity_id = claim["entity_id"].strip()
        cik = claim["cik"].zfill(10)
        if (
            claim["action"] != "ADD"
            or claim["correction_type"] != CORRECTION_TYPE
            or not entity_id
            or len(cik) != 10
            or not cik.isdigit()
        ):
            raise BaselineCorrectionError("invalid historical security restoration")
        if entity_id in seen_entities or ticker in seen_tickers:
            raise BaselineCorrectionError("duplicate baseline identity restoration")
        seen_entities.add(entity_id)
        seen_tickers.add(ticker)
        release = releases.get(claim["source_url"])
        if not release or release.get("status") != "DIRECT_OFFICIAL_SOURCE_ARCHIVED":
            raise BaselineCorrectionError(f"official release not archived: {ticker}")
        if urlparse(claim["source_url"]).hostname not in OFFICIAL_HOSTS:
            raise BaselineCorrectionError(f"non-official source: {ticker}")
        if release["published_date"] != claim["evidence_date"]:
            raise BaselineCorrectionError(f"evidence date mismatch: {ticker}")
        digest = release["source_sha256"].lower()
        matches = list(Path(evidence_dir).glob(f"{digest}.*"))
        if len(matches) != 1:
            raise BaselineCorrectionError(f"missing evidence file: {ticker}")
        content = matches[0].read_bytes()
        if hashlib.sha256(content).hexdigest() != digest:
            raise BaselineCorrectionError(f"evidence hash mismatch: {ticker}")
        text = _normalized_text(content, matches[0].suffix)
        required_terms = [
            term.strip() for term in claim["required_terms"].split("||") if term.strip()
        ]
        if not required_terms or not all(term.casefold() in text for term in required_terms):
            raise BaselineCorrectionError(f"required official language missing: {ticker}")

        interval_start, interval_end = sorted((as_of, evidence_date))
        intervening = [
            row for row in candidate_events
            if row.get("ticker", "").upper() == ticker
            and row.get("action", row.get("event", "")).upper() in {"ADD", "REMOVE"}
            and row.get("effective_date")
            and interval_start < date.fromisoformat(row["effective_date"]) <= interval_end
        ]
        if intervening:
            raise BaselineCorrectionError(
                f"intervening membership event prevents backcast: {ticker}"
            )
        corrections.append({
            "as_of": as_of.isoformat(),
            "entity_id": entity_id,
            "cik": cik,
            "ticker": ticker,
            "correction_type": CORRECTION_TYPE,
            "action": "ADD",
            "event_status": VERIFIED_STATUS,
            "evidence_date": evidence_date.isoformat(),
            "source_url": claim["source_url"],
            "source_sha256": digest,
            "evidence_direction": (
                "PRIOR_TO_BASELINE" if evidence_date <= as_of else "AFTER_BASELINE"
            ),
            "inference": "true",
            "promotion_scope": "DIAGNOSTIC_BASELINE_ONLY",
        })
    return corrections, {
        "claims": len(claims),
        "verified_corrections": len(corrections),
        "inference": True,
        "promotion_scope": "DIAGNOSTIC_BASELINE_ONLY",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("claims", type=Path)
    parser.add_argument("release_corpus", type=Path)
    parser.add_argument("candidate_events", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    corrections, audit = verify_baseline_corrections(
        _read_csv(args.claims),
        _read_csv(args.release_corpus / "release_index.csv"),
        args.release_corpus / "evidence",
        _read_csv(args.candidate_events),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(corrections[0]))
        writer.writeheader()
        writer.writerows(corrections)
    print(json.dumps(audit, ensure_ascii=False))


if __name__ == "__main__":
    main()
