"""B0~B3 후보의 횡단면 일반화와 과최적화 위험을 진단한다."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

_DATA_DIR = Path(__file__).resolve().parent.parent
if str(_DATA_DIR) not in sys.path:
    sys.path.insert(0, str(_DATA_DIR))

from herd.overfitting_metrics import cscv_pbo, deflated_sharpe_ratio, sensitivity_table
from herd.validation_universe import SECTOR_UNIVERSE


def analyze(candidate_report: dict) -> dict:
    rows = candidate_report["rows"]
    candidate_ids = sorted(candidate_report["summary"])
    history = [
        {
            "evaluation_id": row["ticker"],
            "candidate_id": candidate,
            "objective": row["candidates"][candidate]["excess_cagr"],
        }
        for row in rows
        for candidate in candidate_ids
    ]
    cscv = cscv_pbo(history)
    dsr = {
        candidate: deflated_sharpe_ratio(
            [
                row["candidates"][candidate]["excess_cagr"] * 100
                for row in rows
                if row["candidates"][candidate]["excess_cagr"] is not None
            ],
            len(candidate_ids),
        )
        for candidate in candidate_ids
    }
    ticker_sector = {
        ticker: sector for sector, tickers in SECTOR_UNIVERSE.items() for ticker in tickers
    }
    sectors = {}
    for sector in SECTOR_UNIVERSE:
        subset = [row for row in rows if ticker_sector.get(row["ticker"]) == sector]
        if not subset:
            continue
        sectors[sector] = {
            candidate: {
                "median_excess_cagr": float(
                    np.median([row["candidates"][candidate]["excess_cagr"] for row in subset])
                ),
                "positive_rate": sum(
                    row["candidates"][candidate]["excess_cagr"] > 0 for row in subset
                )
                / len(subset),
            }
            for candidate in candidate_ids
        }
    return {
        "report_version": "2026.07-v1",
        "candidate_count": len(candidate_ids),
        "candidate_evaluations": len(history),
        "cross_sectional_cscv": cscv,
        "deflated_sharpe_by_candidate": dsr,
        "sensitivity": sensitivity_table(history),
        "sector_results": sectors,
        "parameter_stability": {
            "mode": "FIXED_BY_CONSTRUCTION",
            "automatic_selection": False,
            "selection_stability": "NOT_APPLICABLE_NO_FOLD_SELECTION",
        },
        "walk_forward": {
            "status": "INSUFFICIENT_DATA",
            "reason": "candidate report does not contain chronological train/test fold returns",
        },
        "era_validation": {
            "status": "INSUFFICIENT_DATA",
            "reason": "candidate report does not contain subperiod return series",
        },
        "decision": "FAIL_CLOSED",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = analyze(json.loads(args.input.read_text(encoding="utf-8")))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
