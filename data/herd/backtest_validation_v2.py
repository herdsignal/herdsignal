"""Phase A 통합 실행기: 현실 체결, 견고한 지표, 점수 감사, Walk-forward."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

_DATA_DIR = Path(__file__).resolve().parent.parent
if str(_DATA_DIR) not in sys.path:
    sys.path.insert(0, str(_DATA_DIR))

from collectors.stock_collector import collect
from config.database import create_db_engine, get_session_factory
from herd.backtest_action_layer import _action_decision, _stored_herd_series, _trend_frame
from herd.calculator import calc_herd_scores
from herd.validation_universe import TICKERS, TICKER_SECTOR_ETF, UNIVERSE_VERSION
from herd.validation_v2 import ExecutionConfig, apply_point_in_time_sector, build_folds, normalize_price_frame, point_in_time_sector_multiplier, run_realistic_strategy, summarize, write_report
from init_db import HerdIndicator, HerdScore

_SessionFactory = get_session_factory(create_db_engine())
BOUNDARIES = (15.0, 40.0, 60.0, 75.0)


def make_v61_decision(ratio_scale: float = 1.0):
    def decide(score: float, trend: pd.Series, previous: float | None, action_days: int) -> tuple[str, float]:
        stable = score
        if previous is not None:
            for boundary in BOUNDARIES:
                if abs(score - boundary) <= 2 and (score - boundary) * (previous - boundary) < 0:
                    stable = boundary - 0.01 if previous < boundary else boundary + 0.01
                    break
        _regime, action, ratio = _action_decision(stable, trend, "v61")
        if ratio > 0:
            days = action_days + 1
            factor = 0.65 if days <= 5 else 1.0 if days <= 20 else 0.82 if days <= 45 else 0.55
            ratio = round(min(0.5, ratio * factor * ratio_scale), 2)
        return action, ratio
    return decide


def fixed_decision(score: float, _trend: pd.Series, _previous: float | None, _days: int) -> tuple[str, float]:
    if score >= 75: return "SELL", 0.30
    if score >= 60: return "SELL", 0.05
    if score <= 15: return "BUY", 0.30
    return "HOLD", 0.0


def buyhold_return(frame: pd.DataFrame, config: ExecutionConfig) -> tuple[float, float]:
    prices = normalize_price_frame(frame)
    start = float(prices.iloc[0]["Open"]) * (1 + config.slippage_bps / 10_000)
    shares = config.initial_cash * (1 - config.fee_rate) / start
    values = [shares * float(price) for price in prices["Close"]]
    peak, mdd = values[0], 0.0
    for value in values:
        peak = max(peak, value)
        mdd = min(mdd, (value - peak) / peak * 100)
    return (values[-1] / config.initial_cash - 1) * 100, mdd


def run_period(ticker: str, frame: pd.DataFrame, herd: pd.Series, config: ExecutionConfig, ratio_scale: float = 1.0) -> dict:
    prices = normalize_price_frame(frame)
    trend = _trend_frame(prices["Close"])
    fixed = run_realistic_strategy(ticker, prices, herd, trend, fixed_decision, config)
    v61 = run_realistic_strategy(ticker, prices, herd, trend, make_v61_decision(ratio_scale), config)
    bh_return, bh_mdd = buyhold_return(prices, config)
    capture = v61.return_pct / bh_return * 100 if bh_return else None
    return {
        "ticker": ticker,
        "start": v61.start,
        "end": v61.end,
        "buyhold_return": bh_return,
        "buyhold_mdd": bh_mdd,
        "fixed_return": fixed.return_pct,
        "fixed_mdd": fixed.mdd,
        "v61_return": v61.return_pct,
        "v61_mdd": v61.mdd,
        "v61_capture": capture,
        "v61_mdd_improvement": v61.mdd - bh_mdd,
        "v61_actions": len(v61.trades),
        "v61_total_cost": v61.total_cost,
        "ratio_scale": ratio_scale,
        "cooldown_days": config.cooldown_days,
    }


def select_on_train(ticker: str, frame: pd.DataFrame, herd: pd.Series, base_config: ExecutionConfig) -> tuple[float, int]:
    """제한된 후보 중 학습구간 위험조정 결과가 가장 안정적인 하나를 고른다."""
    candidates = ((scale, cooldown) for scale in (0.8, 1.0, 1.2) for cooldown in (15, 20, 30))
    best, best_score = (1.0, 20), float("-inf")
    for scale, cooldown in candidates:
        config = ExecutionConfig(base_config.initial_cash, base_config.fee_rate, base_config.slippage_bps, cooldown)
        result = run_period(ticker, frame, herd, config, scale)
        objective = result["v61_return"] + result["v61_mdd"] * 0.5
        if objective > best_score:
            best, best_score = (scale, cooldown), objective
    return best


def score_parity_audit(tickers: list[str], tolerance: float = 0.02) -> dict:
    """저장 지표로 v4 점수를 재계산해 DB 점수와 비교한다."""
    checked = mismatches = 0
    max_diff = 0.0
    with _SessionFactory() as session:
        for ticker in tickers:
            pair = (session.query(HerdScore, HerdIndicator)
                    .join(HerdIndicator, (HerdIndicator.ticker == HerdScore.ticker) & (HerdIndicator.score_date == HerdScore.score_date))
                    .filter(HerdScore.ticker == ticker)
                    .order_by(HerdScore.score_date.desc()).first())
            if pair is None: continue
            score, ind = pair
            values = {name: float(getattr(ind, name)) for name in ("weekly_rsi", "monthly_rsi", "position_52w", "ma200_deviation", "volume_strength", "ma200_weekly")}
            rebuilt = calc_herd_scores(values, float(ind.eps_multiplier or 1), float(ind.sector_multiplier or 1))["herd_v4"]
            diff = abs(rebuilt - float(score.herd_score))
            checked += 1
            max_diff = max(max_diff, diff)
            mismatches += diff > tolerance
    return {"checked": checked, "mismatches": mismatches, "max_difference": max_diff, "tolerance": tolerance, "passed": checked > 0 and mismatches == 0}


def main() -> None:
    parser = argparse.ArgumentParser(description="HERD Phase A Validation v2")
    parser.add_argument("--full", action="store_true")
    parser.add_argument("--tickers", nargs="+")
    parser.add_argument("--slippage-bps", type=float, default=10.0)
    parser.add_argument("--output", default="reports/validation_v2")
    parser.add_argument("--unlock-blind", action="store_true", help="잠긴 최근 12개월 결과를 의도적으로 다시 생성")
    args = parser.parse_args()
    tickers = args.tickers or (TICKERS if args.full else ["SPY", "NVDA", "MSFT", "JPM", "AAPL"])
    config = ExecutionConfig(slippage_bps=args.slippage_bps)
    rows, fold_rows, blind_rows = [], [], []
    output_dir = Path(args.output)
    blind_path = output_dir / "blind_holdout.json"
    blind_locked = blind_path.exists() and not args.unlock_blind
    etf_cache: dict[str, pd.DataFrame] = {}

    for ticker in tickers:
        try:
            frame = normalize_price_frame(collect(ticker, period="10y"))
            herd = _stored_herd_series(ticker, frame.index)
            sector_etf = TICKER_SECTOR_ETF.get(ticker, "SPY")
            if sector_etf not in etf_cache:
                etf_cache[sector_etf] = normalize_price_frame(collect(sector_etf, period="10y"))
            multiplier = point_in_time_sector_multiplier(frame["Close"], etf_cache[sector_etf]["Close"])
            herd = apply_point_in_time_sector(herd, multiplier)
            valid = herd.notna()
            frame, herd = frame.loc[valid], herd.loc[valid]
            rows.append(run_period(ticker, frame, herd, config))
            blind_start = frame.index.max() - pd.DateOffset(years=1)
            research_frame, research_herd = frame.loc[frame.index < blind_start], herd.loc[herd.index < blind_start]
            for mode in ("anchored", "rolling"):
                for fold in build_folds(research_frame.index, mode):
                    train_mask = (research_frame.index.year >= fold["train_start"]) & (research_frame.index.year <= fold["train_end"])
                    test_mask = (research_frame.index.year >= fold["test_start"]) & (research_frame.index.year <= fold["test_end"])
                    if train_mask.sum() < 200 or test_mask.sum() < 50: continue
                    scale, cooldown = select_on_train(ticker, research_frame.loc[train_mask], research_herd.loc[train_mask], config)
                    fold_config = ExecutionConfig(config.initial_cash, config.fee_rate, config.slippage_bps, cooldown)
                    result = run_period(ticker, research_frame.loc[test_mask], research_herd.loc[test_mask], fold_config, scale)
                    fold_rows.append({**fold, "selection_scope": "train_only", **result})
            if not blind_locked:
                scale, cooldown = select_on_train(ticker, research_frame, research_herd, config)
                blind_mask = frame.index >= blind_start
                blind_config = ExecutionConfig(config.initial_cash, config.fee_rate, config.slippage_bps, cooldown)
                blind_rows.append(run_period(ticker, frame.loc[blind_mask], herd.loc[blind_mask], blind_config, scale))
            print(f"[{ticker}] 완료")
        except Exception as exc:
            print(f"[{ticker}] 실패: {exc}")

    metadata = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "model": "HERD_v6.1",
        "universe": UNIVERSE_VERSION,
        "execution": {"signal": "close", "fill": "next_open", **config.__dict__},
        "score_parity": score_parity_audit(tickers),
        "walk_forward_summary": summarize(fold_rows) if fold_rows else {},
        "point_in_time_sector": True,
        "eps_history": "excluded_until_filing-date-source-is-available",
        "blind_holdout": {"locked": True, "reused": blind_locked, "path": str(blind_path)},
        "survivorship_bias_warning": "현재 생존 대형주 중심 유니버스",
    }
    if not blind_locked:
        output_dir.mkdir(parents=True, exist_ok=True)
        blind_path.write_text(json.dumps({"created_at": metadata["generated_at"], "summary": summarize(blind_rows), "rows": blind_rows}, ensure_ascii=False, indent=2), encoding="utf-8")
    json_path, csv_path = write_report(output_dir, metadata, rows, fold_rows)
    print("요약:", summarize(rows))
    print("점수 일치:", metadata["score_parity"])
    print("리포트:", json_path, csv_path)


if __name__ == "__main__":
    main()
