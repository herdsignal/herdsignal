"""검증된 가격 스냅샷에서 시간축 Walk-forward 산출물을 생성한다."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

_DATA_DIR = Path(__file__).resolve().parent.parent
if str(_DATA_DIR) not in sys.path:
    sys.path.insert(0, str(_DATA_DIR))

from herd.benchmark_engine import (
    BenchmarkConfig,
    SimulationResult,
    buy_and_hold,
    performance_metrics,
    simulate,
)
from herd.candidate_model_evaluation import CANDIDATES, build_candidate_targets
from herd.data_snapshot import load_snapshot
from herd.evidence_family_validation import build_evidence_scores
from herd.indicator_inventory import build_v4_indicator_frame
from herd.legacy_model_evaluation import v4_base_score

FORMAT_VERSION = "herd-walk-forward-v1"
DEFAULT_ROOT = Path(__file__).resolve().parent.parent / "walk_forward"
_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{2,80}$")


class WalkForwardError(RuntimeError):
    """Walk-forward 실행 계약 위반."""


@dataclass(frozen=True)
class WalkForwardConfig:
    min_train_years: int = 4
    test_years: int = 1
    step_years: int = 1
    purge_days: int = 1
    embargo_days: int = 20
    research_end: str | None = None

    def __post_init__(self) -> None:
        if min(self.min_train_years, self.test_years, self.step_years) < 1:
            raise ValueError("year lengths must be positive")
        if min(self.purge_days, self.embargo_days) < 0:
            raise ValueError("purge and embargo days cannot be negative")


@dataclass(frozen=True)
class Fold:
    fold_id: str
    train_start: str
    train_end: str
    gap_start: str | None
    gap_end: str | None
    test_start: str
    test_end: str
    train_observations: int
    gap_observations: int
    test_observations: int


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_json(value: object) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def build_anchored_folds(
    calendar: pd.DatetimeIndex,
    config: WalkForwardConfig = WalkForwardConfig(),
) -> list[Fold]:
    index = pd.DatetimeIndex(pd.to_datetime(calendar)).sort_values().unique()
    if config.research_end:
        index = index[index <= pd.Timestamp(config.research_end)]
    if index.empty:
        raise WalkForwardError("empty research calendar")

    gap_size = config.purge_days + config.embargo_days
    minimum_train_boundary = index[0] + pd.DateOffset(years=config.min_train_years)
    minimum_train_observations = int(index.searchsorted(minimum_train_boundary, side="left"))
    test_start_position = minimum_train_observations + gap_size
    folds: list[Fold] = []
    fold_number = 1
    while test_start_position < len(index):
        test_start = index[test_start_position]
        test_end_boundary = test_start + pd.DateOffset(years=config.test_years)
        if test_end_boundary > index[-1] + pd.Timedelta(days=7):
            break
        test_end_position = int(index.searchsorted(test_end_boundary, side="left")) - 1
        test_end_position = min(test_end_position, len(index) - 1)
        if test_end_position < test_start_position:
            break

        train_end_position = test_start_position - gap_size - 1
        if train_end_position < 0:
            raise WalkForwardError("insufficient observations for purge/embargo gap")
        gap_start_position = train_end_position + 1
        gap_end_position = test_start_position - 1
        folds.append(
            Fold(
                fold_id=f"F{fold_number:02d}",
                train_start=index[0].date().isoformat(),
                train_end=index[train_end_position].date().isoformat(),
                gap_start=(
                    index[gap_start_position].date().isoformat()
                    if gap_start_position <= gap_end_position
                    else None
                ),
                gap_end=(
                    index[gap_end_position].date().isoformat()
                    if gap_start_position <= gap_end_position
                    else None
                ),
                test_start=test_start.date().isoformat(),
                test_end=index[test_end_position].date().isoformat(),
                train_observations=train_end_position + 1,
                gap_observations=max(0, gap_end_position - gap_start_position + 1),
                test_observations=test_end_position - test_start_position + 1,
            )
        )
        fold_number += 1
        next_boundary = test_start + pd.DateOffset(years=config.step_years)
        next_position = int(index.searchsorted(next_boundary, side="left"))
        if next_position <= test_start_position:
            raise WalkForwardError("fold step did not advance")
        test_start_position = next_position
    if not folds:
        raise WalkForwardError("calendar is too short for one complete fold")
    return folds


def _json_value(value: object) -> object:
    if value is None:
        return None
    if isinstance(value, (np.integer, int)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        numeric = float(value)
        return numeric if np.isfinite(numeric) else None
    return value


def _path_rows(
    fold: Fold,
    ticker: str,
    candidate: str,
    result: SimulationResult,
    benchmark: SimulationResult,
) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "fold_id": fold.fold_id,
            "ticker": ticker,
            "candidate": candidate,
            "date": result.daily_returns.index.strftime("%Y-%m-%d"),
            "strategy_return": result.daily_returns.to_numpy(),
            "benchmark_return": benchmark.daily_returns.reindex(result.daily_returns.index).to_numpy(),
            "equity": result.equity.to_numpy(),
            "exposure": result.exposure.to_numpy(),
        }
    )


def evaluate_walk_forward(
    price_frames: dict[str, pd.DataFrame],
    *,
    config: WalkForwardConfig = WalkForwardConfig(),
    benchmark_config: BenchmarkConfig = BenchmarkConfig(),
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    if "SPY" not in price_frames:
        raise WalkForwardError("SPY is required as the common research calendar")
    calendar = pd.DatetimeIndex(pd.to_datetime(price_frames["SPY"]["Date"]))
    folds = build_anchored_folds(calendar, config)
    closes = pd.concat(
        {
            ticker: frame.assign(Date=pd.to_datetime(frame["Date"])).set_index("Date")["Close"]
            for ticker, frame in price_frames.items()
        },
        axis=1,
    ).sort_index()
    volumes = pd.concat(
        {
            ticker: frame.assign(Date=pd.to_datetime(frame["Date"])).set_index("Date")["Volume"]
            for ticker, frame in price_frames.items()
        },
        axis=1,
    ).sort_index()
    evidence = build_evidence_scores(closes, volumes)

    metrics_rows: list[dict] = []
    daily_frames: list[pd.DataFrame] = []
    for ticker, raw in sorted(price_frames.items()):
        raw = raw.copy()
        raw["Date"] = pd.to_datetime(raw["Date"])
        raw = raw.sort_values("Date")
        indicator_frame = build_v4_indicator_frame(raw)
        v4 = v4_base_score(indicator_frame).resample("ME").last()
        scores = {name: frame[ticker].dropna() for name, frame in evidence.items()}
        prices = raw.set_index("Date")[["Open", "Close"]]
        targets = build_candidate_targets(scores, prices.index, v4_score=v4)

        for fold in folds:
            test_prices = prices.loc[fold.test_start : fold.test_end]
            if len(test_prices) < 2:
                continue
            benchmark = buy_and_hold(test_prices, config=benchmark_config)
            bh_metrics = performance_metrics(benchmark)
            metrics_rows.append(
                {
                    "fold_id": fold.fold_id,
                    "ticker": ticker,
                    "candidate": "BUY_HOLD",
                    **{key: _json_value(value) for key, value in bh_metrics.items()},
                }
            )
            for candidate in CANDIDATES:
                test_targets = targets[candidate].reindex(test_prices.index)
                result = simulate(candidate, test_prices, test_targets, config=benchmark_config)
                metrics = performance_metrics(result, benchmark)
                metrics_rows.append(
                    {
                        "fold_id": fold.fold_id,
                        "ticker": ticker,
                        "candidate": candidate,
                        **{key: _json_value(value) for key, value in metrics.items()},
                    }
                )
                daily_frames.append(_path_rows(fold, ticker, candidate, result, benchmark))

    if not metrics_rows or not daily_frames:
        raise WalkForwardError("no evaluable fold results")
    fold_frame = pd.DataFrame([asdict(fold) for fold in folds])
    return fold_frame, pd.DataFrame(metrics_rows), pd.concat(daily_frames, ignore_index=True)


def create_walk_forward_run(
    run_id: str,
    snapshot_dir: Path,
    *,
    root: Path = DEFAULT_ROOT,
    config: WalkForwardConfig = WalkForwardConfig(),
    benchmark_config: BenchmarkConfig = BenchmarkConfig(),
    created_at: datetime | None = None,
) -> Path:
    if not _ID_PATTERN.fullmatch(run_id):
        raise WalkForwardError("run_id must contain 3-81 safe characters")
    root = Path(root)
    final_dir = root / run_id
    if final_dir.exists():
        raise WalkForwardError(f"run already exists: {final_dir}")

    frames, snapshot_manifest = load_snapshot(snapshot_dir)
    fold_frame, metrics_frame, daily_frame = evaluate_walk_forward(
        frames, config=config, benchmark_config=benchmark_config
    )
    temp_dir = root / f".{run_id}.tmp-{uuid.uuid4().hex}"
    temp_dir.mkdir(parents=True)
    try:
        outputs = {
            "folds": temp_dir / "folds.csv",
            "fold_metrics": temp_dir / "fold_metrics.csv",
            "daily_returns": temp_dir / "daily_returns.csv.gz",
        }
        fold_frame.to_csv(outputs["folds"], index=False, lineterminator="\n")
        metrics_frame.to_csv(
            outputs["fold_metrics"], index=False, float_format="%.12g", lineterminator="\n"
        )
        daily_frame.to_csv(
            outputs["daily_returns"],
            index=False,
            float_format="%.12g",
            compression={"method": "gzip", "compresslevel": 9, "mtime": 0},
            lineterminator="\n",
        )
        artifacts = {
            name: {
                "path": path.name,
                "rows": len(
                    fold_frame if name == "folds" else metrics_frame if name == "fold_metrics" else daily_frame
                ),
                "bytes": path.stat().st_size,
                "sha256": _sha256(path),
            }
            for name, path in outputs.items()
        }
        timestamp = created_at or datetime.now(timezone.utc)
        body = {
            "format_version": FORMAT_VERSION,
            "run_id": run_id,
            "created_at": timestamp.astimezone(timezone.utc).isoformat(),
            "snapshot": {
                "path": str(Path(snapshot_dir).resolve()),
                "snapshot_id": snapshot_manifest["snapshot_id"],
                "snapshot_sha256": snapshot_manifest["snapshot_sha256"],
            },
            "walk_forward_config": asdict(config),
            "benchmark_config": asdict(benchmark_config),
            "candidates": list(CANDIDATES),
            "parameter_fit": "fixed candidates; no fold-level optimization",
            "blind_holdout_status": "NOT_ASSIGNED_BY_THIS_RUN",
            "artifacts": artifacts,
        }
        manifest = {**body, "run_sha256": hashlib.sha256(_canonical_json(body)).hexdigest()}
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


def verify_walk_forward_run(run_dir: Path) -> dict:
    directory = Path(run_dir)
    manifest_path = directory / "manifest.json"
    if not manifest_path.is_file():
        raise WalkForwardError("missing run manifest")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("format_version") != FORMAT_VERSION:
        raise WalkForwardError("unsupported run format")
    expected = manifest.get("run_sha256")
    body = {key: value for key, value in manifest.items() if key != "run_sha256"}
    if hashlib.sha256(_canonical_json(body)).hexdigest() != expected:
        raise WalkForwardError("run manifest checksum mismatch")
    for name, metadata in manifest["artifacts"].items():
        path = directory / metadata["path"]
        if (
            not path.is_file()
            or path.stat().st_size != metadata["bytes"]
            or _sha256(path) != metadata["sha256"]
        ):
            raise WalkForwardError(f"{name}: artifact checksum mismatch")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    create_parser = subparsers.add_parser("create")
    create_parser.add_argument("run_id")
    create_parser.add_argument("snapshot_dir", type=Path)
    create_parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    create_parser.add_argument("--research-end")
    create_parser.add_argument("--purge-days", type=int, default=1)
    create_parser.add_argument("--embargo-days", type=int, default=20)
    verify_parser = subparsers.add_parser("verify")
    verify_parser.add_argument("run_dir", type=Path)
    args = parser.parse_args()
    if args.command == "create":
        config = WalkForwardConfig(
            purge_days=args.purge_days,
            embargo_days=args.embargo_days,
            research_end=args.research_end,
        )
        print(create_walk_forward_run(args.run_id, args.snapshot_dir, root=args.root, config=config))
    else:
        print(json.dumps(verify_walk_forward_run(args.run_dir), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
