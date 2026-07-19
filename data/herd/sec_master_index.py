"""SEC EDGAR 분기별 master index를 원본 해시와 함께 고정한다."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import time
import uuid
from datetime import date, datetime, timezone
from pathlib import Path

import requests

MASTER_URL = "https://www.sec.gov/Archives/edgar/full-index/{year}/QTR{quarter}/master.idx"
HEADER = "CIK|Company Name|Form Type|Date Filed|Filename"


class SecMasterIndexError(RuntimeError):
    pass


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def load_env_value(path: Path, key: str) -> str:
    for raw_line in Path(path).read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        if name.strip() == key:
            return value.strip().strip("\"'")
    return ""


def resolve_user_agent(env_file: Path) -> str:
    configured = load_env_value(env_file, "SEC_USER_AGENT")
    if configured:
        user_agent = configured
    else:
        email = load_env_value(env_file, "HERDSIGNAL_OWNER_EMAIL")
        user_agent = f"HerdSignal research {email}" if email else ""
    if len(user_agent) < 10 or "@" not in user_agent:
        raise SecMasterIndexError("SEC User-Agent must contain an application and contact email")
    return user_agent


def quarter_range(start: date, end: date) -> list[tuple[int, int]]:
    if start > end:
        raise SecMasterIndexError("start date cannot follow end date")
    result = []
    year, quarter = start.year, (start.month - 1) // 3 + 1
    end_key = (end.year, (end.month - 1) // 3 + 1)
    while (year, quarter) <= end_key:
        result.append((year, quarter))
        quarter += 1
        if quarter == 5:
            year, quarter = year + 1, 1
    return result


def parse_master_index(content: bytes) -> list[dict]:
    text = content.decode("latin-1")
    position = text.find(HEADER)
    if position < 0:
        raise SecMasterIndexError("SEC master index header not found")
    rows = []
    for line in text[position + len(HEADER):].splitlines():
        line = line.strip()
        if not line:
            continue
        if set(line) == {"-"}:
            continue
        parts = line.split("|")
        if len(parts) != 5:
            raise SecMasterIndexError(f"invalid master index row: {line[:80]}")
        cik, company_name, form, filed, filename = parts
        int(cik)
        date.fromisoformat(filed)
        if not filename.startswith("edgar/data/"):
            raise SecMasterIndexError(f"unexpected filing path: {filename}")
        rows.append({
            "cik": f"{int(cik):010d}",
            "company_name": company_name.strip(),
            "form": form.strip(),
            "filed_date": filed,
            "filename": filename,
        })
    if not rows:
        raise SecMasterIndexError("SEC master index contains no rows")
    return rows


def collect_master_indexes(
    output_root: Path,
    *,
    snapshot_id: str,
    start_date: date,
    end_date: date,
    user_agent: str,
    delay_seconds: float = 0.15,
) -> Path:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{2,80}", snapshot_id):
        raise SecMasterIndexError("unsafe snapshot id")
    final = Path(output_root) / snapshot_id
    if final.exists():
        raise SecMasterIndexError(f"snapshot already exists: {final}")
    temp = Path(output_root) / f".{snapshot_id}.tmp-{uuid.uuid4().hex}"
    raw_dir = temp / "raw"
    raw_dir.mkdir(parents=True)
    session = requests.Session()
    session.headers.update({
        "User-Agent": user_agent,
        "Accept-Encoding": "gzip, deflate",
    })
    files = []
    try:
        for year, quarter in quarter_range(start_date, end_date):
            url = MASTER_URL.format(year=year, quarter=quarter)
            response = session.get(url, timeout=60)
            response.raise_for_status()
            rows = parse_master_index(response.content)
            name = f"{year}-Q{quarter}-master.idx"
            destination = raw_dir / name
            destination.write_bytes(response.content)
            files.append({
                "year": year,
                "quarter": quarter,
                "url": url,
                "path": f"raw/{name}",
                "bytes": len(response.content),
                "sha256": sha256_bytes(response.content),
                "rows": len(rows),
                "first_filed_date": min(row["filed_date"] for row in rows),
                "last_filed_date": max(row["filed_date"] for row in rows),
            })
            time.sleep(delay_seconds)
        manifest = {
            "format_version": "herd-sec-master-index-v1",
            "snapshot_id": snapshot_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "requested_start": start_date.isoformat(),
            "requested_end": end_date.isoformat(),
            "source": "SEC EDGAR full-index master.idx",
            "user_agent_configured": True,
            "files": files,
            "file_count": len(files),
            "row_count": sum(item["rows"] for item in files),
        }
        (temp / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        Path(output_root).mkdir(parents=True, exist_ok=True)
        temp.rename(final)
        return final
    except Exception:
        shutil.rmtree(temp, ignore_errors=True)
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("snapshot_id")
    parser.add_argument("--start", type=date.fromisoformat, required=True)
    parser.add_argument("--end", type=date.fromisoformat, required=True)
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    parser.add_argument(
        "--root", type=Path,
        default=Path(__file__).resolve().parent.parent / "reference" / "sec",
    )
    args = parser.parse_args()
    path = collect_master_indexes(
        args.root,
        snapshot_id=args.snapshot_id,
        start_date=args.start,
        end_date=args.end,
        user_agent=resolve_user_agent(args.env_file),
    )
    print(path)


if __name__ == "__main__":
    main()
