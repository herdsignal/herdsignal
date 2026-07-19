"""검증용 가격 데이터를 불변 스냅샷으로 생성하고 검증한다."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import re
import shutil
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterable

import numpy as np
import pandas as pd

_DATA_DIR = Path(__file__).resolve().parent.parent
if str(_DATA_DIR) not in sys.path:
    sys.path.insert(0, str(_DATA_DIR))

from collectors.stock_collector import collect
from herd.validation_universe import TICKERS, UNIVERSE_VERSION

FORMAT_VERSION = "herd-price-snapshot-v1"
PRICE_COLUMNS = ("Date", "Open", "High", "Low", "Close", "Volume")
DEFAULT_ROOT = _DATA_DIR / "snapshots"
_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{2,80}$")


class SnapshotError(RuntimeError):
    """스냅샷 생성 또는 검증 실패."""


def _canonical_json(value: object) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _package_version(name: str) -> str:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return "unknown"


def normalize_prices(raw: pd.DataFrame, ticker: str) -> pd.DataFrame:
    missing = set(PRICE_COLUMNS) - set(raw.columns)
    if missing:
        raise SnapshotError(f"{ticker}: missing columns {sorted(missing)}")
    frame = raw.loc[:, PRICE_COLUMNS].copy()
    frame["Date"] = pd.to_datetime(frame["Date"], errors="raise").dt.tz_localize(None).dt.normalize()
    for column in PRICE_COLUMNS[1:]:
        frame[column] = pd.to_numeric(frame[column], errors="raise")
    frame = frame.sort_values("Date", kind="stable").reset_index(drop=True)

    if frame.empty:
        raise SnapshotError(f"{ticker}: empty price data")
    if frame["Date"].duplicated().any():
        raise SnapshotError(f"{ticker}: duplicate dates")
    numeric = frame.loc[:, PRICE_COLUMNS[1:]].to_numpy(dtype=float)
    if not np.isfinite(numeric).all():
        raise SnapshotError(f"{ticker}: non-finite price data")
    if (frame.loc[:, ("Open", "High", "Low", "Close")] <= 0).any().any():
        raise SnapshotError(f"{ticker}: OHLC must be positive")
    if (frame["Volume"] < 0).any():
        raise SnapshotError(f"{ticker}: volume must be non-negative")
    tolerance = 1e-8
    if (
        frame["High"] + tolerance
        < frame.loc[:, ("Open", "Low", "Close")].max(axis=1)
    ).any():
        raise SnapshotError(f"{ticker}: invalid high price")
    if (
        frame["Low"] - tolerance
        > frame.loc[:, ("Open", "High", "Close")].min(axis=1)
    ).any():
        raise SnapshotError(f"{ticker}: invalid low price")

    frame["Date"] = frame["Date"].dt.strftime("%Y-%m-%d")
    return frame


def _write_price_file(frame: pd.DataFrame, path: Path) -> None:
    frame.to_csv(
        path,
        index=False,
        float_format="%.10g",
        compression={"method": "gzip", "compresslevel": 9, "mtime": 0},
        lineterminator="\n",
    )


def create_snapshot(
    snapshot_id: str,
    *,
    tickers: Iterable[str] = TICKERS,
    period: str = "10y",
    root: Path = DEFAULT_ROOT,
    collector: Callable[..., pd.DataFrame] = collect,
    minimum_coverage: float = 1.0,
    created_at: datetime | None = None,
) -> Path:
    if not _ID_PATTERN.fullmatch(snapshot_id):
        raise SnapshotError("snapshot_id must contain 3-81 safe characters")
    if not 0 < minimum_coverage <= 1:
        raise ValueError("minimum_coverage must be between 0 and 1")

    requested = tuple(dict.fromkeys(ticker.upper() for ticker in tickers))
    if not requested:
        raise SnapshotError("at least one ticker is required")
    root = Path(root)
    final_dir = root / snapshot_id
    if final_dir.exists():
        raise SnapshotError(f"snapshot already exists: {final_dir}")

    temp_dir = root / f".{snapshot_id}.tmp-{uuid.uuid4().hex}"
    price_dir = temp_dir / "prices"
    price_dir.mkdir(parents=True)
    files: dict[str, dict] = {}
    failures: dict[str, str] = {}
    try:
        for ticker in requested:
            try:
                normalized = normalize_prices(collector(ticker, period=period), ticker)
                relative = Path("prices") / f"{ticker}.csv.gz"
                destination = temp_dir / relative
                _write_price_file(normalized, destination)
                files[ticker] = {
                    "path": relative.as_posix(),
                    "rows": len(normalized),
                    "start": normalized["Date"].iloc[0],
                    "end": normalized["Date"].iloc[-1],
                    "bytes": destination.stat().st_size,
                    "sha256": _sha256(destination),
                }
            except Exception as exc:  # 종목별 실패를 manifest 수준에서 판단한다.
                failures[ticker] = f"{type(exc).__name__}: {exc}"

        coverage = len(files) / len(requested)
        if coverage < minimum_coverage:
            raise SnapshotError(
                f"coverage {coverage:.1%} is below {minimum_coverage:.1%}: {failures}"
            )

        timestamp = created_at or datetime.now(timezone.utc)
        body = {
            "format_version": FORMAT_VERSION,
            "snapshot_id": snapshot_id,
            "created_at": timestamp.astimezone(timezone.utc).isoformat(),
            "universe_version": UNIVERSE_VERSION,
            "source": {
                "provider": "yfinance",
                "period": period,
                "interval": "1d",
                "auto_adjust": True,
                "end_semantics": "provider response at collection time",
                "yfinance_version": _package_version("yfinance"),
                "pandas_version": pd.__version__,
            },
            "schema": list(PRICE_COLUMNS),
            "requested_tickers": list(requested),
            "completed_tickers": sorted(files),
            "coverage": coverage,
            "failures": failures,
            "files": dict(sorted(files.items())),
        }
        manifest = {**body, "snapshot_sha256": hashlib.sha256(_canonical_json(body)).hexdigest()}
        (temp_dir / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        root.mkdir(parents=True, exist_ok=True)
        temp_dir.rename(final_dir)
        return final_dir
    except Exception:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise


def verify_snapshot(snapshot_dir: Path) -> dict:
    directory = Path(snapshot_dir)
    manifest_path = directory / "manifest.json"
    if not manifest_path.is_file():
        raise SnapshotError(f"missing manifest: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("format_version") != FORMAT_VERSION:
        raise SnapshotError("unsupported snapshot format")
    expected_manifest_hash = manifest.get("snapshot_sha256")
    body = {key: value for key, value in manifest.items() if key != "snapshot_sha256"}
    actual_manifest_hash = hashlib.sha256(_canonical_json(body)).hexdigest()
    if expected_manifest_hash != actual_manifest_hash:
        raise SnapshotError("manifest checksum mismatch")
    if manifest.get("schema") != list(PRICE_COLUMNS):
        raise SnapshotError("price schema mismatch")

    expected_paths = set()
    for ticker, metadata in manifest.get("files", {}).items():
        relative = Path(metadata["path"])
        if relative.is_absolute() or ".." in relative.parts:
            raise SnapshotError(f"{ticker}: unsafe file path")
        path = directory / relative
        expected_paths.add(relative.as_posix())
        if not path.is_file():
            raise SnapshotError(f"{ticker}: missing price file")
        if path.stat().st_size != metadata["bytes"] or _sha256(path) != metadata["sha256"]:
            raise SnapshotError(f"{ticker}: price checksum mismatch")
        frame = normalize_prices(pd.read_csv(path), ticker)
        if len(frame) != metadata["rows"]:
            raise SnapshotError(f"{ticker}: row count mismatch")
        if frame["Date"].iloc[[0, -1]].tolist() != [metadata["start"], metadata["end"]]:
            raise SnapshotError(f"{ticker}: date range mismatch")

    actual_paths = {
        path.relative_to(directory).as_posix()
        for path in (directory / "prices").glob("*.csv.gz")
    }
    if actual_paths != expected_paths:
        raise SnapshotError("unexpected or untracked price files")
    return manifest


def load_snapshot(
    snapshot_dir: Path,
    *,
    tickers: Iterable[str] | None = None,
) -> tuple[dict[str, pd.DataFrame], dict]:
    manifest = verify_snapshot(snapshot_dir)
    selected = list(tickers) if tickers is not None else manifest["completed_tickers"]
    frames: dict[str, pd.DataFrame] = {}
    for ticker in selected:
        symbol = ticker.upper()
        metadata = manifest["files"].get(symbol)
        if metadata is None:
            raise SnapshotError(f"ticker is not in snapshot: {symbol}")
        frame = pd.read_csv(Path(snapshot_dir) / metadata["path"])
        frame["Date"] = pd.to_datetime(frame["Date"])
        frames[symbol] = frame
    return frames, manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    create_parser = subparsers.add_parser("create")
    create_parser.add_argument("snapshot_id")
    create_parser.add_argument("--period", default="10y")
    create_parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    verify_parser = subparsers.add_parser("verify")
    verify_parser.add_argument("snapshot_dir", type=Path)
    args = parser.parse_args()
    if args.command == "create":
        path = create_snapshot(args.snapshot_id, period=args.period, root=args.root)
        print(path)
    else:
        manifest = verify_snapshot(args.snapshot_dir)
        print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
