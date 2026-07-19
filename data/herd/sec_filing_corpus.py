"""SEC filing URL 목록을 원문·SHA-256 corpus로 고정한다."""

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

try:
    from herd.sec_master_index import resolve_user_agent
except ModuleNotFoundError:
    from sec_master_index import resolve_user_agent


class SecFilingCorpusError(RuntimeError):
    pass


def collect_filing_corpus(
    rows: list[dict],
    output_root: Path,
    *,
    snapshot_id: str,
    user_agent: str,
    delay_seconds: float = 0.15,
) -> Path:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{2,80}", snapshot_id):
        raise SecFilingCorpusError("unsafe snapshot id")
    final = Path(output_root) / snapshot_id
    if final.exists():
        raise SecFilingCorpusError(f"snapshot already exists: {final}")
    urls = sorted({row["filing_url"] for row in rows if row.get("filing_url")})
    if not urls:
        raise SecFilingCorpusError("no SEC filing URLs")
    temp = Path(output_root) / f".{snapshot_id}.tmp-{uuid.uuid4().hex}"
    raw = temp / "raw"
    raw.mkdir(parents=True)
    session = requests.Session()
    session.headers.update({"User-Agent": user_agent, "Accept-Encoding": "gzip, deflate"})
    index = []
    try:
        for url in urls:
            response = session.get(url, timeout=60)
            response.raise_for_status()
            digest = hashlib.sha256(response.content).hexdigest()
            path = raw / f"{digest}.txt"
            path.write_bytes(response.content)
            index.append({
                "filing_url": url, "source_sha256": digest,
                "bytes": len(response.content), "path": f"raw/{path.name}",
            })
            time.sleep(delay_seconds)
        with (temp / "index.csv").open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(index[0]))
            writer.writeheader()
            writer.writerows(index)
        manifest = {
            "format_version": "herd-sec-filing-corpus-v1",
            "snapshot_id": snapshot_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "source": "SEC EDGAR Archives",
            "user_agent_configured": True,
            "documents": len(index),
            "bytes": sum(row["bytes"] for row in index),
        }
        (temp / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        Path(output_root).mkdir(parents=True, exist_ok=True)
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
    parser.add_argument("input", type=Path)
    parser.add_argument("snapshot_id")
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    parser.add_argument(
        "--root", type=Path,
        default=Path(__file__).resolve().parent.parent / "reference" / "sec",
    )
    args = parser.parse_args()
    print(collect_filing_corpus(
        read_csv(args.input), args.root, snapshot_id=args.snapshot_id,
        user_agent=resolve_user_agent(args.env_file),
    ))


if __name__ == "__main__":
    main()
