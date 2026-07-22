"""V5의 결과 비관측 섹터 순환 순서를 120개에서 150개로 확장해 다음 30개 기업을 고정한다."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd

from herd.sec_guidance_v5_broad_expansion import select_metadata_universe


BASE_PROTOCOL = Path("data/herd/sec_guidance_v5_broad_expansion.json")


def select_third_wave() -> tuple[pd.DataFrame, dict]:
    protocol = json.loads(BASE_PROTOCOL.read_text())
    protocol["metadata_target_tickers"] = 150
    expanded, base_report = select_metadata_universe(protocol)
    locked = pd.read_csv("data/reports/sec_guidance_v5_broad_metadata_universe.csv")
    locked_tickers = set(locked["ticker"].astype(str))
    if len(set(expanded["ticker"].astype(str)) & locked_tickers) != len(locked_tickers):
        raise ValueError("the deterministic 150-issuer extension does not preserve the locked first 120")
    output = expanded.loc[~expanded["ticker"].astype(str).isin(locked_tickers)].copy()
    return output.reset_index(drop=True), {
        "report_version": "herd-sec-guidance-v6-third-wave-metadata-v1",
        "selection_parent": str(BASE_PROTOCOL),
        "locked_first_wave_tickers": len(locked_tickers),
        "third_wave_tickers": len(output),
        "third_wave_sectors": int(output["gics_sector"].nunique()),
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
    universe, report = select_third_wave()
    universe.to_csv(args.universe, index=False, lineterminator="\n")
    report["base_protocol_sha256"] = hashlib.sha256(BASE_PROTOCOL.read_bytes()).hexdigest()
    report["universe_sha256"] = hashlib.sha256(args.universe.read_bytes()).hexdigest()
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
