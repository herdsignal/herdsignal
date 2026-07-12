"""v6.1 대비 Risk Cap 후보의 train-only/Rolling OOS 실험."""

from __future__ import annotations

import argparse, json, sys
from pathlib import Path
import pandas as pd

_DATA_DIR = Path(__file__).resolve().parent.parent
if str(_DATA_DIR) not in sys.path: sys.path.insert(0, str(_DATA_DIR))

from collectors.stock_collector import collect
from herd.backtest_action_layer import _stored_herd_series, _trend_frame
from herd.backtest_validation_v2 import make_v61_decision, select_on_train
from herd.risk_cap_experiment import PROFILES, capped_decision, summarize_risk_cap
from herd.validation_universe import TICKERS
from herd.validation_v2 import ExecutionConfig, build_folds, normalize_price_frame, run_realistic_strategy


def run_pair(ticker, frame, herd, config, scale, profile):
    trend = _trend_frame(frame["Close"])
    base = make_v61_decision(scale)
    baseline = run_realistic_strategy(ticker, frame, herd, trend, base, config)
    candidate = run_realistic_strategy(ticker, frame, herd, trend, capped_decision(base, profile), config)
    return {"ticker": ticker, "baseline_return": baseline.return_pct, "candidate_return": candidate.return_pct,
            "baseline_mdd": baseline.mdd, "candidate_mdd": candidate.mdd,
            "baseline_actions": len(baseline.trades), "candidate_actions": len(candidate.trades),
            "risk_profile": profile, "ratio_scale": scale, "cooldown_days": config.cooldown_days}


def select_profile(ticker, frame, herd, config, scale):
    best, best_score = "off", float("-inf")
    for profile in PROFILES:
        row = run_pair(ticker, frame, herd, config, scale, profile)
        score = row["candidate_return"] + row["candidate_mdd"] * 0.75
        if score > best_score: best, best_score = profile, score
    return best


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--full", action="store_true"); parser.add_argument("--tickers", nargs="+")
    parser.add_argument("--output", default="reports/validation_v2/risk_cap_experiment.json")
    args = parser.parse_args(); tickers = args.tickers or (TICKERS if args.full else ["SPY", "NVDA", "MSFT", "JPM", "AAPL"])
    base_config = ExecutionConfig(); rows = []
    for ticker in tickers:
        try:
            frame = normalize_price_frame(collect(ticker, period="10y")); herd = _stored_herd_series(ticker, frame.index)
            valid = herd.notna(); frame, herd = frame.loc[valid], herd.loc[valid]
            research_end = frame.index.max() - pd.DateOffset(years=1); frame, herd = frame.loc[frame.index < research_end], herd.loc[herd.index < research_end]
            for fold in build_folds(frame.index, "rolling"):
                train = (frame.index.year >= fold["train_start"]) & (frame.index.year <= fold["train_end"])
                test = (frame.index.year >= fold["test_start"]) & (frame.index.year <= fold["test_end"])
                if train.sum() < 200 or test.sum() < 50: continue
                scale, cooldown = select_on_train(ticker, frame.loc[train], herd.loc[train], base_config)
                config = ExecutionConfig(cooldown_days=cooldown); profile = select_profile(ticker, frame.loc[train], herd.loc[train], config, scale)
                rows.append({**fold, **run_pair(ticker, frame.loc[test], herd.loc[test], config, scale, profile)})
            print(f"[{ticker}] 완료")
        except Exception as exc: print(f"[{ticker}] 실패: {exc}")
    payload = {"experiment": "risk_cap", "selection_scope": "train_only", "summary": summarize_risk_cap(rows), "rows": rows}
    path = Path(args.output); path.parent.mkdir(parents=True, exist_ok=True); path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(payload["summary"]); print(path)


if __name__ == "__main__": main()
