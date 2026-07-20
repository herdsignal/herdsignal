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
from urllib.parse import urlparse

import requests

from herd.sec_master_index import resolve_user_agent
from lxml import html

ARCHIVE_URL = "https://press.spglobal.com/index.php?l=100&o={offset}&s=2429"
RELEASE_DATE = re.compile(r"press\.spglobal\.com/(\d{4}-\d{2}-\d{2})-")
CHANGE_TITLE_PATTERNS = (
    re.compile(r"(?:set to|to)\s+join\s+(?:the\s+)?s&p 500", re.IGNORECASE),
    re.compile(r"set to\s+(?:the\s+)?s&p 500", re.IGNORECASE),
    re.compile(r"(?:addition to|continues in)\s+(?:the\s+)?s&p 500", re.IGNORECASE),
    re.compile(r"s&p 500\s+(?:changes|quarterly)", re.IGNORECASE),
    re.compile(r"\breplace\b", re.IGNORECASE),
    re.compile(
        r"s&p\s+(?:dow jones indices|u\.?s\.? indices).{0,100}"
        r"(?:changes|adjustments|rebalance)",
        re.IGNORECASE,
    ),
)


class ReleaseArchiveError(RuntimeError):
    pass


OFFICIAL_RELEASE_HOSTS = {"press.spglobal.com"}


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
        normalized_title = title.lower()
        broad_us_index_change = (
            ("s&p u.s. indices" in normalized_title
             or "s&p dow jones indices" in normalized_title)
            and any(
                term in normalized_title
                for term in ("change", "adjustment", "rebalance")
            )
        )
        if not start_date <= published <= end_date:
            continue
        if "s&p 500" not in normalized_title and not broad_us_index_change:
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


def collect_direct_release_corpus(
    claims_path: Path,
    output_dir: Path,
    *,
    user_agent: str,
    delay_seconds: float = 0.2,
    session: requests.Session | None = None,
    seed_corpus: Path | None = None,
) -> dict:
    """명시한 S&P 보도자료 URL을 원문·해시와 함께 고정한다."""
    if len(user_agent.strip()) < 10:
        raise ReleaseArchiveError("a descriptive user agent is required")
    destination = Path(output_dir)
    if destination.exists():
        raise ReleaseArchiveError("output directory already exists")
    with Path(claims_path).open(encoding="utf-8", newline="") as handle:
        claims = list(csv.DictReader(handle))
    required = {"published_date", "title", "source_url"}
    if not claims or not required.issubset(claims[0]):
        raise ReleaseArchiveError("direct release claims schema mismatch")

    seed_rows = []
    seed_by_url = {}
    if seed_corpus:
        with (Path(seed_corpus) / "release_index.csv").open(
            encoding="utf-8", newline=""
        ) as handle:
            seed_rows = list(csv.DictReader(handle))
        seed_by_url = {row["source_url"]: row for row in seed_rows}
    client = session or requests.Session()
    client.headers["User-Agent"] = user_agent
    rows = []
    documents = []
    claims_by_url = {
        row["source_url"]: row for row in [*seed_rows, *claims]
    }
    for claim in claims_by_url.values():
        published = date.fromisoformat(claim["published_date"])
        source_url = claim["source_url"].strip()
        if urlparse(source_url).hostname not in OFFICIAL_RELEASE_HOSTS:
            raise ReleaseArchiveError(f"non-official release host: {source_url}")
        match = RELEASE_DATE.search(source_url)
        if not match or date.fromisoformat(match.group(1)) != published:
            raise ReleaseArchiveError("release URL date does not match published_date")
        seed = seed_by_url.get(source_url)
        if seed:
            matches = list(
                (Path(seed_corpus) / "evidence").glob(
                    f"{seed['source_sha256']}.*"
                )
            )
            if len(matches) != 1:
                raise ReleaseArchiveError(
                    f"seed evidence missing: {source_url}"
                )
            content = matches[0].read_bytes()
            digest = hashlib.sha256(content).hexdigest()
            if digest != seed["source_sha256"]:
                raise ReleaseArchiveError(
                    f"seed evidence hash mismatch: {source_url}"
                )
            suffix = matches[0].suffix
        else:
            response = client.get(source_url, timeout=60)
            response.raise_for_status()
            content = response.content
            digest = hashlib.sha256(content).hexdigest()
            suffix = (
                ".pdf"
                if "pdf" in response.headers.get("Content-Type", "").lower()
                else ".html"
            )
        documents.append((digest, suffix, content))
        rows.append({
            **claim,
            "status": "DIRECT_OFFICIAL_SOURCE_ARCHIVED",
            "source_sha256": digest,
        })
        if session is None and not seed:
            time.sleep(delay_seconds)

    evidence_dir = destination / "evidence"
    evidence_dir.mkdir(parents=True)
    for digest, suffix, content in documents:
        (evidence_dir / f"{digest}{suffix}").write_bytes(content)
    index_path = destination / "release_index.csv"
    fields = list(rows[0])
    with index_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    manifest = {
        "source": "S&P Global direct public press release URLs",
        "release_documents": len(rows),
        "seed_corpus": str(seed_corpus) if seed_corpus else "",
        "seed_documents": len(seed_rows),
        "use": "OFFICIAL_DOCUMENT_ARCHIVE; claims require independent verification",
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
    parser.add_argument("--start", type=date.fromisoformat)
    parser.add_argument("--end", type=date.fromisoformat)
    parser.add_argument("--user-agent")
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--direct-claims", type=Path)
    parser.add_argument("--seed-corpus", type=Path)
    args = parser.parse_args()
    user_agent = (
        args.user_agent
        or resolve_user_agent(args.env_file or Path(".env"))
    )
    if not args.direct_claims and (not args.start or not args.end):
        parser.error("--start and --end are required for archive discovery")
    collector = (
        collect_direct_release_corpus(
            args.direct_claims,
            args.output_dir,
            user_agent=user_agent,
            seed_corpus=args.seed_corpus,
        )
        if args.direct_claims
        else collect_release_corpus(
            args.output_dir,
            start_date=args.start,
            end_date=args.end,
            user_agent=user_agent,
        )
    )
    print(json.dumps(collector, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
