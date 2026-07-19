"""S&P Global 공개 보도자료에서 S&P 500 구성 변경 근거 후보를 수집한다."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import time
from datetime import date
from pathlib import Path

import requests
from lxml import html

ARCHIVE_URL = "https://press.spglobal.com/index.php?l=100&o={offset}&s=2429"
RELEASE_DATE = re.compile(r"press\.spglobal\.com/(\d{4}-\d{2}-\d{2})-")
CHANGE_TITLE_PATTERNS = (
    re.compile(r"(?:set to|to)\s+join\s+(?:the\s+)?s&p 500", re.IGNORECASE),
    re.compile(r"set to\s+(?:the\s+)?s&p 500", re.IGNORECASE),
    re.compile(r"(?:addition to|continues in)\s+(?:the\s+)?s&p 500", re.IGNORECASE),
    re.compile(r"s&p 500\s+(?:changes|quarterly)", re.IGNORECASE),
    re.compile(r"\breplace\b", re.IGNORECASE),
)


class ReleaseArchiveError(RuntimeError):
    pass


def discover_release_links(content: bytes, start_date: date, end_date: date) -> list[dict]:
    document = html.fromstring(content)
    found = {}
    for anchor in document.xpath("//a[@href]"):
        url = anchor.get("href", "")
        match = RELEASE_DATE.search(url)
        if not match:
            continue
        published = date.fromisoformat(match.group(1))
        title = " ".join(anchor.text_content().split())
        if not start_date <= published <= end_date or "s&p 500" not in title.lower():
            continue
        if not any(pattern.search(title) for pattern in CHANGE_TITLE_PATTERNS):
            continue
        found[url] = {
            "published_date": published.isoformat(),
            "title": title,
            "source_url": url,
            "status": "REQUIRES_EVENT_EXTRACTION",
        }
    return sorted(found.values(), key=lambda row: (row["published_date"], row["source_url"]))


def collect_release_corpus(
    output_dir: Path,
    *,
    start_date: date,
    end_date: date,
    user_agent: str,
    maximum_pages: int = 40,
    delay_seconds: float = 0.2,
) -> dict:
    if len(user_agent.strip()) < 10:
        raise ReleaseArchiveError("a descriptive user agent is required")
    destination = Path(output_dir)
    if destination.exists():
        raise ReleaseArchiveError("output directory already exists")
    evidence_dir = destination / "evidence"
    evidence_dir.mkdir(parents=True)
    session = requests.Session()
    session.headers["User-Agent"] = user_agent
    releases = {}
    pages_scanned = 0
    for page in range(maximum_pages):
        response = session.get(ARCHIVE_URL.format(offset=page * 100), timeout=60)
        response.raise_for_status()
        pages_scanned += 1
        for row in discover_release_links(response.content, start_date, end_date):
            releases[row["source_url"]] = row
        all_dates = [
            date.fromisoformat(value)
            for value in RELEASE_DATE.findall(response.text)
        ]
        if all_dates and max(all_dates) < start_date:
            break
        time.sleep(delay_seconds)

    for url, row in sorted(releases.items()):
        response = session.get(url, timeout=60)
        response.raise_for_status()
        digest = hashlib.sha256(response.content).hexdigest()
        suffix = ".pdf" if "pdf" in response.headers.get("Content-Type", "").lower() else ".html"
        (evidence_dir / f"{digest}{suffix}").write_bytes(response.content)
        row["source_sha256"] = digest
        time.sleep(delay_seconds)

    index_path = destination / "release_index.csv"
    fields = ["published_date", "title", "source_url", "status", "source_sha256"]
    with index_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(sorted(releases.values(), key=lambda row: row["published_date"]))
    manifest = {
        "source": "S&P Global public press release archive",
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "pages_scanned": pages_scanned,
        "release_documents": len(releases),
        "use": "OFFICIAL_DOCUMENT_DISCOVERY; event rows require extraction and review",
        "index_sha256": hashlib.sha256(index_path.read_bytes()).hexdigest(),
    }
    (destination / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--start", type=date.fromisoformat, required=True)
    parser.add_argument("--end", type=date.fromisoformat, required=True)
    parser.add_argument("--user-agent", required=True)
    args = parser.parse_args()
    print(json.dumps(
        collect_release_corpus(
            args.output_dir,
            start_date=args.start,
            end_date=args.end,
            user_agent=args.user_agent,
        ),
        ensure_ascii=False,
        indent=2,
    ))


if __name__ == "__main__":
    main()
