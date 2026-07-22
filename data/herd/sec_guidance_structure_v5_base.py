"""새 corpus를 변경 없는 V4 원자 결합기로 재생성해 V5 입력 원장을 만든다."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd

from herd.sec_guidance_block_extraction_v1 import load_aliases
from herd.sec_guidance_structure_parser_v4 import build


PROTOCOL = Path(__file__).with_suffix(".json")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidates", type=Path, required=True)
    parser.add_argument("--review", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    cached_path = Path(protocol["cached_v4_candidate_ledger"])
    cached_hash = hashlib.sha256(cached_path.read_bytes()).hexdigest()
    parser_path = Path("data/herd/sec_guidance_structure_parser_v4.py")
    parser_hash = hashlib.sha256(parser_path.read_bytes()).hexdigest()
    if cached_hash != protocol["cached_v4_candidate_ledger_sha256"]:
        raise ValueError("cached V4 candidate ledger hash mismatch")
    if parser_hash != protocol["v4_parser_sha256"]:
        raise ValueError("V4 parser changed; full replay is required")
    # 기존 세 corpus는 해시 고정 원장을 캐시로 사용하고 새 corpus만 같은 V4로 파싱한다.
    incremental, review, incremental_report = build(
        [Path(protocol["input_corpora"][-1])],
        load_aliases(Path(protocol["alias_registry"])),
        protocol,
    )
    cached = pd.read_csv(cached_path, dtype={"cik": str})
    candidates = pd.concat([cached, incremental], ignore_index=True)
    identity = [
        "ticker", "accession_number", "metric", "fiscal_period", "accounting_basis", "metric_subtype",
        "unit", "lower_bound", "upper_bound", "source_structure", "range_offset",
    ]
    candidates = candidates.drop_duplicates(identity).sort_values(
        ["accepted_at", "ticker", "accession_number", "metric", "range_offset"]
    ).reset_index(drop=True)
    report = {
        "report_version": "herd-sec-guidance-structure-v5-base-v1",
        "replay_mode": "HASH_VERIFIED_INCREMENTAL_V4",
        "cached_v4_candidates": len(cached),
        "incremental_v4_candidates": len(incremental),
        "merged_v4_candidates": len(candidates),
        "merged_v4_candidate_tickers": int(candidates["ticker"].nunique()),
        "incremental_report": incremental_report,
        "cached_v4_candidate_ledger_sha256": cached_hash,
        "v4_parser_sha256": parser_hash,
    }
    candidates.to_csv(args.candidates, index=False, float_format="%.12g", lineterminator="\n")
    review.to_csv(args.review, index=False, float_format="%.12g", lineterminator="\n")
    report["protocol_sha256"] = hashlib.sha256(PROTOCOL.read_bytes()).hexdigest()
    report["price_outcomes_observed"] = False
    report["operational_action_ratio"] = 0.0
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
