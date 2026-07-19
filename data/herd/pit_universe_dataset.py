"""S&P 500 point-in-time 구성원 원천을 검증 가능한 구간 데이터로 변환한다."""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import io
import json
import re
import shutil
import uuid
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

SOURCE_TIERS = {
    "LICENSED_AUTHORITATIVE",
    "OFFICIAL_RECONSTRUCTION",
    "COMMUNITY_RECONSTRUCTION",
}
FORMAT_VERSION = "herd-pit-universe-v1"
_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{2,80}$")


class PitUniverseError(RuntimeError):
    pass


@dataclass(frozen=True)
class Membership:
    index_id: str
    security_id: str
    ticker: str
    effective_from: str
    effective_to: str
    source_tier: str
    source_uri: str


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_json(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def _read_daily_memberships(path: Path) -> tuple[list[tuple[str, set[str]]], int]:
    by_date: dict[str, set[str]] = {}
    duplicate_dates = 0
    with Path(path).open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != ["date", "tickers"]:
            raise PitUniverseError("community CSV must contain date,tickers")
        previous = None
        for row in reader:
            observed = datetime.strptime(row["date"], "%Y-%m-%d").date().isoformat()
            if previous and observed < previous:
                raise PitUniverseError("source dates must be chronological")
            tickers = {ticker.strip().upper() for ticker in row["tickers"].split(",") if ticker.strip()}
            # 공개 재구성본의 결함도 보존해 진단하되 명백히 잘못된 파일은 거부한다.
            # 480 미만은 manifest에서 별도 품질 이상으로 기록한다.
            if not 400 <= len(tickers) <= 550:
                raise PitUniverseError(f"{observed}: implausible constituent count {len(tickers)}")
            if observed in by_date:
                duplicate_dates += 1
            # 같은 날짜의 충돌은 원본 순서상 마지막 스냅샷을 보존하고
            # manifest 품질 이상으로 공개한다.
            by_date[observed] = tickers
            previous = observed
    rows = list(by_date.items())
    if len(rows) < 2:
        raise PitUniverseError("at least two source observations are required")
    return rows, duplicate_dates


def community_intervals(
    source_csv: Path,
    *,
    source_uri: str,
) -> tuple[list[Membership], list[dict], dict]:
    snapshots, duplicate_dates = _read_daily_memberships(source_csv)
    open_since: dict[str, str] = {}
    memberships: list[Membership] = []
    events: list[dict] = []
    previous: set[str] = set()
    for position, (observed, current) in enumerate(snapshots):
        added = current - previous if position else current
        removed = previous - current if position else set()
        for ticker in sorted(added):
            open_since[ticker] = observed
            events.append({"effective_date": observed, "event": "ADD", "ticker": ticker})
        for ticker in sorted(removed):
            start = open_since.pop(ticker)
            memberships.append(
                Membership(
                    "SP500", "", ticker, start, observed,
                    "COMMUNITY_RECONSTRUCTION", source_uri,
                )
            )
            events.append({"effective_date": observed, "event": "REMOVE", "ticker": ticker})
        previous = current
    for ticker, start in sorted(open_since.items()):
        memberships.append(
            Membership(
                "SP500", "", ticker, start, "",
                "COMMUNITY_RECONSTRUCTION", source_uri,
            )
        )
    summary = {
        "first_observation": snapshots[0][0],
        "last_observation": snapshots[-1][0],
        "source_observations": len(snapshots),
        "unique_tickers": len({item.ticker for item in memberships}),
        "membership_intervals": len(memberships),
        "events_excluding_initial": max(0, len(events) - len(snapshots[0][1])),
        "minimum_constituents": min(len(value) for _, value in snapshots),
        "maximum_constituents": max(len(value) for _, value in snapshots),
        "duplicate_source_dates": duplicate_dates,
        "observations_below_480": sum(len(value) < 480 for _, value in snapshots),
        "observations_above_510": sum(len(value) > 510 for _, value in snapshots),
    }
    return sorted(memberships, key=lambda item: (item.ticker, item.effective_from)), events, summary


def _validate_intervals(memberships: list[Membership]) -> None:
    grouped: dict[tuple[str, str], list[Membership]] = defaultdict(list)
    for item in memberships:
        if item.source_tier not in SOURCE_TIERS:
            raise PitUniverseError("unknown source tier")
        identity = item.security_id or f"TICKER:{item.ticker}"
        grouped[(item.index_id, identity)].append(item)
    for records in grouped.values():
        records.sort(key=lambda item: item.effective_from)
        for current, following in zip(records, records[1:]):
            if not current.effective_to:
                raise PitUniverseError("open interval cannot precede another interval")
            if current.effective_to > following.effective_from:
                raise PitUniverseError("overlapping membership intervals")


def create_community_dataset(
    dataset_id: str,
    source_csv: Path,
    *,
    source_uri: str,
    root: Path,
    created_at: datetime | None = None,
) -> Path:
    if not _ID_PATTERN.fullmatch(dataset_id):
        raise PitUniverseError("unsafe dataset id")
    final = Path(root) / dataset_id
    if final.exists():
        raise PitUniverseError(f"dataset already exists: {final}")
    memberships, events, summary = community_intervals(source_csv, source_uri=source_uri)
    _validate_intervals(memberships)
    temp = Path(root) / f".{dataset_id}.tmp-{uuid.uuid4().hex}"
    temp.mkdir(parents=True)
    try:
        membership_path = temp / "memberships.csv.gz"
        with gzip.GzipFile(filename=str(membership_path), mode="wb", compresslevel=9, mtime=0) as raw:
            with io.TextIOWrapper(raw, encoding="utf-8", newline="") as text:
                writer = csv.DictWriter(text, fieldnames=list(asdict(memberships[0])))
                writer.writeheader()
                writer.writerows(asdict(item) for item in memberships)
        event_path = temp / "events.csv"
        with event_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=["effective_date", "event", "ticker"])
            writer.writeheader()
            writer.writerows(events)
        artifacts = {
            path.name: {"bytes": path.stat().st_size, "sha256": _sha256(path)}
            for path in (membership_path, event_path)
        }
        body = {
            "format_version": FORMAT_VERSION,
            "dataset_id": dataset_id,
            "created_at": (created_at or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat(),
            "source": {
                "tier": "COMMUNITY_RECONSTRUCTION",
                "uri": source_uri,
                "input_sha256": _sha256(Path(source_csv)),
            },
            "summary": summary,
            "quality": {
                "stable_security_ids": False,
                "official_cross_check": False,
                "constituent_count_anomalies": (
                    summary["observations_below_480"] + summary["observations_above_510"]
                ),
                "duplicate_source_dates": summary["duplicate_source_dates"],
                "survivorship_safe": False,
                "allowed_use": "PIPELINE_AND_GAP_RESEARCH_ONLY",
            },
            "artifacts": artifacts,
        }
        manifest = {**body, "dataset_sha256": hashlib.sha256(_canonical_json(body)).hexdigest()}
        (temp / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        Path(root).mkdir(parents=True, exist_ok=True)
        temp.rename(final)
        return final
    except Exception:
        shutil.rmtree(temp, ignore_errors=True)
        raise


def verify_dataset(path: Path) -> dict:
    directory = Path(path)
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    body = {key: value for key, value in manifest.items() if key != "dataset_sha256"}
    if manifest.get("format_version") != FORMAT_VERSION:
        raise PitUniverseError("unsupported dataset format")
    if hashlib.sha256(_canonical_json(body)).hexdigest() != manifest.get("dataset_sha256"):
        raise PitUniverseError("manifest checksum mismatch")
    for name, metadata in manifest["artifacts"].items():
        artifact = directory / name
        if not artifact.is_file() or artifact.stat().st_size != metadata["bytes"] or _sha256(artifact) != metadata["sha256"]:
            raise PitUniverseError(f"{name}: checksum mismatch")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    create = sub.add_parser("create-community")
    create.add_argument("dataset_id")
    create.add_argument("source_csv", type=Path)
    create.add_argument("--source-uri", required=True)
    create.add_argument("--root", type=Path, default=Path(__file__).resolve().parent.parent / "reference" / "point_in_time")
    verify = sub.add_parser("verify")
    verify.add_argument("dataset", type=Path)
    args = parser.parse_args()
    if args.command == "create-community":
        print(create_community_dataset(args.dataset_id, args.source_csv, source_uri=args.source_uri, root=args.root))
    else:
        print(json.dumps(verify_dataset(args.dataset), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
