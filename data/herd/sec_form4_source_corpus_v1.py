"""잠긴 Form 4 표본의 SEC 원문 XML을 내용 주소 방식으로 고정한다."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import shutil
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import requests

from herd.sec_master_index import resolve_user_agent


class Form4CorpusError(RuntimeError):
    pass


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _file_sha256(path: Path) -> str:
    return _sha256(path.read_bytes())


def _looks_like_ownership_xml(content: bytes) -> bool:
    head = content[:2000].lower()
    return b"<ownershipdocument" in head or (
        b"<?xml" in head and b"<issuercik>" in content.lower()
    )


def collect(
    sample_path: Path,
    output_root: Path,
    *,
    snapshot_id: str,
    user_agent: str,
    delay_seconds: float = 0.12,
    session: requests.Session | None = None,
) -> Path:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{2,80}", snapshot_id):
        raise Form4CorpusError("unsafe snapshot id")
    final = output_root / snapshot_id
    if final.exists():
        raise Form4CorpusError(f"snapshot already exists: {final}")
    with sample_path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows or len({row["accession_number"] for row in rows}) != len(rows):
        raise Form4CorpusError("source sample must contain unique accessions")

    temp = output_root / f".{snapshot_id}.tmp-{uuid.uuid4().hex}"
    raw = temp / "raw"
    raw.mkdir(parents=True)
    client = session or requests.Session()
    client.headers.update({
        "User-Agent": user_agent,
        "Accept-Encoding": "gzip, deflate",
    })
    index: list[dict] = []
    try:
        for row in rows:
            response = client.get(row["source_url"], timeout=60)
            response.raise_for_status()
            content = response.content
            if not _looks_like_ownership_xml(content):
                raise Form4CorpusError(
                    f"primary document is not ownership XML: {row['accession_number']}"
                )
            digest = _sha256(content)
            target = raw / f"{digest}.xml"
            if target.exists() and target.read_bytes() != content:
                raise Form4CorpusError("SHA-256 content collision")
            target.write_bytes(content)
            index.append({
                **{
                    key: row[key] for key in (
                        "issuer_cik", "candidate_tickers", "reporting_owner_cik",
                        "accession_number", "form", "filing_date", "report_date",
                        "acceptance_datetime", "primary_document", "source_url",
                    )
                },
                "source_sha256": digest,
                "bytes": len(content),
                "path": f"raw/{target.name}",
            })
            if session is None:
                time.sleep(delay_seconds)

        index_path = temp / "index.csv"
        with index_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(index[0]))
            writer.writeheader()
            writer.writerows(index)
        manifest = {
            "format_version": "herd-sec-form4-source-corpus-v1",
            "snapshot_id": snapshot_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "source": "SEC EDGAR Archives primaryDocument",
            "source_sample_sha256": _file_sha256(sample_path),
            "index_sha256": _file_sha256(index_path),
            "documents": len(index),
            "issuers": len({row["issuer_cik"] for row in index}),
            "bytes": sum(int(row["bytes"]) for row in index),
            "price_outcomes_opened": False,
            "transaction_content_used_for_selection": False,
            "operational_action_authority": False,
        }
        (temp / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        output_root.mkdir(parents=True, exist_ok=True)
        temp.rename(final)
        return final
    except Exception:
        shutil.rmtree(temp, ignore_errors=True)
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("sample", type=Path)
    parser.add_argument("snapshot_id")
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parent.parent / "reference" / "sec",
    )
    args = parser.parse_args()
    print(collect(
        args.sample,
        args.root,
        snapshot_id=args.snapshot_id,
        user_agent=resolve_user_agent(args.env_file),
    ))


if __name__ == "__main__":
    main()
