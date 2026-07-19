"""대상 CIK의 SEC submissions·Company Facts와 과거 filing 조각을 고정한다."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
import time
import uuid
from datetime import date, datetime, timezone
from pathlib import Path

import requests

try:
    from herd.sec_master_index import resolve_user_agent
except ModuleNotFoundError:
    from sec_master_index import resolve_user_agent

SUBMISSIONS = "https://data.sec.gov/submissions/CIK{cik}.json"
COMPANYFACTS = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
SUBMISSION_FILE = "https://data.sec.gov/submissions/{name}"


class SecPitCorpusError(RuntimeError):
    pass


def unique_ciks(rows: list[dict]) -> list[str]:
    return sorted({
        f"{int(row['cik']):010d}" for row in rows
        if row.get("cik") and row.get("cik_link_status") == "UNIQUE_CIK_NAME_CANDIDATE"
    })


def overlapping_submission_files(payload: dict, start: date, end: date) -> list[str]:
    names = []
    for item in payload.get("filings", {}).get("files", []):
        first = date.fromisoformat(item["filingFrom"])
        last = date.fromisoformat(item["filingTo"])
        if first <= end and start <= last:
            names.append(item["name"])
    return sorted(set(names))


def collect_sec_pit_corpus(
    rows: list[dict],
    root: Path,
    *,
    snapshot_id: str,
    start_date: date,
    end_date: date,
    user_agent: str,
    delay_seconds: float = 0.15,
) -> Path:
    final = Path(root) / snapshot_id
    if final.exists():
        raise SecPitCorpusError(f"snapshot exists: {final}")
    ciks = unique_ciks(rows)
    if not ciks:
        raise SecPitCorpusError("no unique CIK candidates")
    temp = Path(root) / f".{snapshot_id}.tmp-{uuid.uuid4().hex}"
    raw = temp / "raw"
    raw.mkdir(parents=True)
    session = requests.Session()
    session.headers.update({"User-Agent": user_agent, "Accept-Encoding": "gzip, deflate"})
    artifacts = []
    unavailable = []

    def fetch(url: str, name: str, *, allow_not_found: bool = False) -> dict | None:
        response = session.get(url, timeout=90)
        if response.status_code == 404 and allow_not_found:
            unavailable.append({"url": url, "reason": "HTTP_404"})
            time.sleep(delay_seconds)
            return None
        response.raise_for_status()
        # JSON schema와 차단 응답을 구분한다.
        payload = response.json()
        content = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode()
        digest = hashlib.sha256(content).hexdigest()
        destination = raw / name
        destination.write_bytes(content)
        time.sleep(delay_seconds)
        item = {
            "url": url, "path": f"raw/{name}", "sha256": digest,
            "bytes": len(content),
        }
        artifacts.append(item)
        return payload

    try:
        supplemental_count = 0
        for cik in ciks:
            submissions = fetch(
                SUBMISSIONS.format(cik=cik), f"CIK{cik}-submissions.json"
            )
            fetch(
                COMPANYFACTS.format(cik=cik),
                f"CIK{cik}-companyfacts.json",
                allow_not_found=True,
            )
            for name in overlapping_submission_files(
                submissions, start_date, end_date
            ):
                fetch(
                    SUBMISSION_FILE.format(name=name),
                    f"CIK{cik}-history-{name}",
                )
                supplemental_count += 1
        manifest = {
            "format_version": "herd-sec-pit-corpus-v1",
            "snapshot_id": snapshot_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "ciks": len(ciks),
            "documents": len(artifacts),
            "supplemental_submission_files": supplemental_count,
            "bytes": sum(item["bytes"] for item in artifacts),
            "unavailable_documents": unavailable,
            "companyfacts_unavailable": len(unavailable),
            "user_agent_configured": True,
            "artifacts": artifacts,
        }
        (temp / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        Path(root).mkdir(parents=True, exist_ok=True)
        temp.rename(final)
        return final
    except Exception:
        shutil.rmtree(temp, ignore_errors=True)
        raise


def read_csv(path: Path) -> list[dict]:
    with Path(path).open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("events", type=Path)
    parser.add_argument("snapshot_id")
    parser.add_argument("--start", type=date.fromisoformat, required=True)
    parser.add_argument("--end", type=date.fromisoformat, required=True)
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    parser.add_argument(
        "--root", type=Path,
        default=Path(__file__).resolve().parent.parent / "reference" / "sec",
    )
    args = parser.parse_args()
    print(collect_sec_pit_corpus(
        read_csv(args.events), args.root, snapshot_id=args.snapshot_id,
        start_date=args.start, end_date=args.end,
        user_agent=resolve_user_agent(args.env_file),
    ))


if __name__ == "__main__":
    main()
