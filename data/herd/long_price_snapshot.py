"""14년 이상 가격·배당·분할을 보존하는 불변 연구 스냅샷 V2."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import re
import shutil
import uuid
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Callable, Iterable

import numpy as np
import pandas as pd
import yfinance as yf

from herd.validation_universe import TICKERS


FORMAT_VERSION = "herd-price-snapshot-v2"
DEFAULT_ROOT = Path(__file__).resolve().parent.parent / "snapshots"
SECTOR_ETFS = ("XLB", "XLC", "XLE", "XLF", "XLI", "XLK", "XLP", "XLU", "XLV", "XLY")
MARKET_ETFS = ("DIA", "IWM", "QQQ", "SPY")
PRICE_COLUMNS = (
    "Date", "Open", "High", "Low", "Close", "Adj Close", "Volume",
    "Dividends", "Stock Splits",
)
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{2,80}$")


class LongPriceSnapshotError(RuntimeError):
    pass


def _canonical(value: object) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _version(package: str) -> str:
    try:
        return importlib.metadata.version(package)
    except importlib.metadata.PackageNotFoundError:
        return "unknown"


def collect_history(ticker: str, *, start: date, end: date) -> pd.DataFrame:
    """Yahoo 응답을 수정하지 않고 원시 가격과 기업행동을 함께 요청한다."""
    return yf.Ticker(ticker).history(
        start=start.isoformat(),
        end=end.isoformat(),
        interval="1d",
        auto_adjust=False,
        actions=True,
        repair=False,
        keepna=False,
        raise_errors=True,
    ).reset_index()


def normalize_history(raw: pd.DataFrame, ticker: str) -> pd.DataFrame:
    frame = raw.copy()
    if "Datetime" in frame:
        frame = frame.rename(columns={"Datetime": "Date"})
    missing = set(PRICE_COLUMNS) - set(frame)
    if missing:
        raise LongPriceSnapshotError(f"{ticker}: missing columns {sorted(missing)}")
    frame = frame.loc[:, PRICE_COLUMNS]
    frame["Date"] = (
        pd.to_datetime(frame["Date"], errors="raise", utc=True)
        .dt.tz_localize(None).dt.normalize()
    )
    for column in PRICE_COLUMNS[1:]:
        frame[column] = pd.to_numeric(frame[column], errors="raise")
    frame = frame.sort_values("Date", kind="stable").reset_index(drop=True)
    if frame.empty or frame["Date"].duplicated().any():
        raise LongPriceSnapshotError(f"{ticker}: empty or duplicate dates")
    values = frame.loc[:, PRICE_COLUMNS[1:]].to_numpy(dtype=float)
    if not np.isfinite(values).all():
        raise LongPriceSnapshotError(f"{ticker}: non-finite values")
    if (frame[["Open", "High", "Low", "Close", "Adj Close"]] <= 0).any().any():
        raise LongPriceSnapshotError(f"{ticker}: non-positive price")
    if (frame[["Volume", "Dividends", "Stock Splits"]] < 0).any().any():
        raise LongPriceSnapshotError(f"{ticker}: negative volume or corporate action")
    if (frame["High"] < frame[["Open", "Low", "Close"]].max(axis=1)).any():
        raise LongPriceSnapshotError(f"{ticker}: invalid high")
    if (frame["Low"] > frame[["Open", "High", "Close"]].min(axis=1)).any():
        raise LongPriceSnapshotError(f"{ticker}: invalid low")
    frame["Date"] = frame["Date"].dt.strftime("%Y-%m-%d")
    return frame


def _role(ticker: str) -> str:
    if ticker in SECTOR_ETFS:
        return "SECTOR_ETF"
    if ticker in MARKET_ETFS:
        return "MARKET_ETF"
    return "EQUITY"


def create_snapshot(
    snapshot_id: str,
    *,
    start: date,
    end: date,
    equities: Iterable[str] = TICKERS,
    sector_etfs: Iterable[str] = SECTOR_ETFS,
    root: Path = DEFAULT_ROOT,
    collector: Callable[..., pd.DataFrame] = collect_history,
    created_at: datetime | None = None,
) -> Path:
    if not _ID.fullmatch(snapshot_id):
        raise LongPriceSnapshotError("invalid snapshot id")
    if end <= start or (end - start).days < 14 * 365:
        raise LongPriceSnapshotError("snapshot requires at least 14 calendar years")
    requested = tuple(dict.fromkeys(
        ticker.upper() for ticker in [*equities, *MARKET_ETFS, *sector_etfs]
    ))
    destination = Path(root) / snapshot_id
    if destination.exists():
        raise LongPriceSnapshotError(f"snapshot already exists: {destination}")
    temporary = Path(root) / f".{snapshot_id}.tmp-{uuid.uuid4().hex}"
    (temporary / "prices").mkdir(parents=True)
    files, failures = {}, {}
    try:
        for ticker in requested:
            try:
                frame = normalize_history(
                    collector(ticker, start=start, end=end), ticker
                )
                path = temporary / "prices" / f"{ticker}.csv.gz"
                frame.to_csv(
                    path, index=False, float_format="%.10g", lineterminator="\n",
                    compression={"method": "gzip", "compresslevel": 9, "mtime": 0},
                )
                files[ticker] = {
                    "path": path.relative_to(temporary).as_posix(),
                    "role": _role(ticker),
                    "rows": len(frame),
                    "start": frame["Date"].iloc[0],
                    "end": frame["Date"].iloc[-1],
                    "dividend_events": int(frame["Dividends"].ne(0).sum()),
                    "split_events": int(frame["Stock Splits"].ne(0).sum()),
                    "bytes": path.stat().st_size,
                    "sha256": _sha256(path),
                }
            except Exception as error:
                failures[ticker] = f"{type(error).__name__}: {error}"
        required = {ticker for ticker in requested if _role(ticker) != "SECTOR_ETF"}
        missing_required = sorted(required - files.keys())
        missing_sector = sorted(set(sector_etfs) - files.keys())
        if missing_required or missing_sector:
            raise LongPriceSnapshotError(
                f"incomplete snapshot: required={missing_required}, sector={missing_sector}"
            )
        body = {
            "format_version": FORMAT_VERSION,
            "snapshot_id": snapshot_id,
            "created_at": (created_at or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat(),
            "research_period": {"start_inclusive": start.isoformat(), "end_exclusive": end.isoformat()},
            "source": {
                "provider": "Yahoo Finance via yfinance",
                "usage": "PERSONAL_RESEARCH_ONLY",
                "interval": "1d",
                "auto_adjust": False,
                "actions": True,
                "repair": False,
                "yfinance_version": _version("yfinance"),
                "pandas_version": pd.__version__,
            },
            "policy": {
                "immutable_after_creation": True,
                "survivorship_safe": False,
                "sector_etf_pre_inception_backfill": False,
                "production_signal_allowed": False,
                "blind_holdout_allowed": False,
            },
            "schema": list(PRICE_COLUMNS),
            "requested_tickers": list(requested),
            "completed_tickers": sorted(files),
            "failures": failures,
            "files": dict(sorted(files.items())),
        }
        manifest = {
            **body,
            "snapshot_sha256": hashlib.sha256(_canonical(body)).hexdigest(),
        }
        (temporary / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        Path(root).mkdir(parents=True, exist_ok=True)
        temporary.rename(destination)
        return destination
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise


def verify_snapshot(path: Path) -> dict:
    root = Path(path)
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("format_version") != FORMAT_VERSION:
        raise LongPriceSnapshotError("unsupported format")
    expected = manifest.get("snapshot_sha256")
    body = {key: value for key, value in manifest.items() if key != "snapshot_sha256"}
    if expected != hashlib.sha256(_canonical(body)).hexdigest():
        raise LongPriceSnapshotError("manifest checksum mismatch")
    if manifest.get("policy", {}).get("survivorship_safe") is not False:
        raise LongPriceSnapshotError("snapshot cannot claim survivorship safety")
    for ticker, metadata in manifest.get("files", {}).items():
        file = root / metadata["path"]
        if not file.is_file() or file.stat().st_size != metadata["bytes"] or _sha256(file) != metadata["sha256"]:
            raise LongPriceSnapshotError(f"{ticker}: price checksum mismatch")
        normalized = normalize_history(pd.read_csv(file), ticker)
        if len(normalized) != metadata["rows"]:
            raise LongPriceSnapshotError(f"{ticker}: row count mismatch")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    create = subparsers.add_parser("create")
    create.add_argument("snapshot_id")
    create.add_argument("--start", type=date.fromisoformat, required=True)
    create.add_argument("--end", type=date.fromisoformat, required=True)
    create.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    verify = subparsers.add_parser("verify")
    verify.add_argument("snapshot", type=Path)
    args = parser.parse_args()
    if args.command == "create":
        print(create_snapshot(args.snapshot_id, start=args.start, end=args.end, root=args.root))
    else:
        print(json.dumps(verify_snapshot(args.snapshot), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
