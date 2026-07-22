"""V7 독립 검증을 위해 기존 결과 비관측 순서의 남은 기업 모집단을 고정한다."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd

from herd.sec_guidance_v5_broad_expansion import select_metadata_universe


BASE_PROTOCOL = Path("data/herd/sec_guidance_v5_broad_expansion.json")
LOCKED_120 = Path("data/reports/sec_guidance_v5_broad_metadata_universe.csv")
LOCKED_30 = Path("data/reports/sec_guidance_v6_third_wave_metadata.csv")


def select_v7_universe() -> tuple[pd.DataFrame, dict]:
    protocol = json.loads(BASE_PROTOCOL.read_text())
    protocol["metadata_target_tickers"] = 10_000
    expanded, base_report = select_metadata_universe(protocol)
    locked = pd.concat([pd.read_csv(LOCKED_120), pd.read_csv(LOCKED_30)], ignore_index=True)
    locked_tickers = set(locked["ticker"].astype(str))
    expanded_tickers = set(expanded["ticker"].astype(str))
    if not locked_tickers.issubset(expanded_tickers):
        raise ValueError("locked deterministic prefix is not preserved")
    output = expanded.loc[~expanded["ticker"].astype(str).isin(locked_tickers)].copy()
    return output.reset_index(drop=True), {
        "report_version": "herd-sec-guidance-v7-independent-universe-v1",
        "scope": "PARSER_VALIDATION_ONLY",
        "eligible_outcome_blind_tickers": len(expanded),
        "locked_prior_tickers": len(locked_tickers),
        "v7_independent_tickers": len(output),
        "v7_independent_sectors": int(output["gics_sector"].nunique()),
        "selection_used_guidance_text": False,
        "selection_used_parser_output": False,
        "selection_used_price_outcomes": False,
        "base_selection_report": base_report,
        "operational_action_ratio": 0.0,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--universe", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    universe, report = select_v7_universe()
    universe.to_csv(args.universe, index=False, lineterminator="\n")
    report["base_protocol_sha256"] = hashlib.sha256(BASE_PROTOCOL.read_bytes()).hexdigest()
    report["universe_sha256"] = hashlib.sha256(args.universe.read_bytes()).hexdigest()
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
