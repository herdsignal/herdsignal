"""S&P Global 보도자료의 공식 asPDF=1 보조 원문을 해시 고정한다."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
import shutil
import time
import uuid
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import requests
from pypdf import PdfReader


class SpglobalPdfArchiveError(RuntimeError):
    pass


def as_pdf_url(source_url: str) -> str:
    parsed = urlparse(source_url)
    host = (parsed.hostname or "").lower()
    if host != "spglobal.com" and not host.endswith(".spglobal.com"):
        raise SpglobalPdfArchiveError(f"non-official source host: {host}")
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query["asPDF"] = "1"
    return urlunparse(parsed._replace(query=urlencode(query)))


def extract_pdf_text(content: bytes) -> str:
    if not content.startswith(b"%PDF-"):
        raise SpglobalPdfArchiveError("asPDF response is not a PDF")
    reader = PdfReader(io.BytesIO(content), strict=True)
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    normalized = " ".join(text.replace("\xa0", " ").split())
    if len(normalized) < 100:
        raise SpglobalPdfArchiveError("PDF contains insufficient extractable text")
    return normalized


def corroborates_release(pdf_text: str, release: dict) -> bool:
    title_tokens = {
        token.lower()
        for token in re.findall(r"[A-Za-z0-9]+", release["title"])
        if len(token) >= 4
    }
    normalized = pdf_text.lower()
    matched_tokens = sum(token in normalized for token in title_tokens)
    title_coverage = matched_tokens / len(title_tokens) if title_tokens else 0
    return "s&p 500" in normalized and title_coverage >= 0.6


def collect_pdf_corpus(
    release_index: Path,
    output_root: Path,
    *,
    snapshot_id: str,
    user_agent: str,
    delay_seconds: float = 0.2,
    session: requests.Session | None = None,
) -> Path:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{2,80}", snapshot_id):
        raise SpglobalPdfArchiveError("unsafe snapshot id")
    if len(user_agent.strip()) < 10:
        raise SpglobalPdfArchiveError("a descriptive user agent is required")
    final = Path(output_root) / snapshot_id
    if final.exists():
        raise SpglobalPdfArchiveError(f"snapshot already exists: {final}")
    temporary = Path(output_root) / f".{snapshot_id}.{uuid.uuid4().hex}.tmp"
    evidence = temporary / "evidence"
    evidence.mkdir(parents=True)
    client = session or requests.Session()
    client.headers["User-Agent"] = user_agent
    try:
        with Path(release_index).open(encoding="utf-8", newline="") as handle:
            releases = list(csv.DictReader(handle))
        rows = []
        for release in releases:
            url = as_pdf_url(release["source_url"])
            response = client.get(url, timeout=60)
            response.raise_for_status()
            text = extract_pdf_text(response.content)
            digest = hashlib.sha256(response.content).hexdigest()
            (evidence / f"{digest}.pdf").write_bytes(response.content)
            rows.append({
                "published_date": release["published_date"],
                "title": release["title"],
                "source_url": release["source_url"],
                "pdf_url": url,
                "html_sha256": release["source_sha256"],
                "pdf_sha256": digest,
                "pdf_bytes": len(response.content),
                "extracted_characters": len(text),
                "corroborates_release": corroborates_release(text, release),
                "evidence_role": "AUXILIARY_OFFICIAL_COPY",
            })
            time.sleep(delay_seconds)
        if not rows or not all(row["corroborates_release"] for row in rows):
            raise SpglobalPdfArchiveError(
                "one or more PDFs do not corroborate their release"
            )
        index_path = temporary / "pdf_index.csv"
        with index_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        manifest = {
            "source": "S&P Global official press release asPDF=1",
            "release_documents": len(rows),
            "corroborated_documents": sum(
                row["corroborates_release"] for row in rows
            ),
            "total_bytes": sum(row["pdf_bytes"] for row in rows),
            "index_sha256": hashlib.sha256(index_path.read_bytes()).hexdigest(),
            "evidence_role": (
                "AUXILIARY_ONLY; HTML/prose event semantics remain primary"
            ),
        }
        (temporary / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        temporary.rename(final)
        return final
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("release_index", type=Path)
    parser.add_argument("output_root", type=Path)
    parser.add_argument("--snapshot-id", required=True)
    parser.add_argument("--user-agent", required=True)
    args = parser.parse_args()
    result = collect_pdf_corpus(
        args.release_index,
        args.output_root,
        snapshot_id=args.snapshot_id,
        user_agent=args.user_agent,
    )
    print(result)


if __name__ == "__main__":
    main()
