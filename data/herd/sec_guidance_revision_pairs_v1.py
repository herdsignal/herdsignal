"""원문 정확도 게이트를 통과한 동일 의미 가이던스만 연속 수정쌍으로 연결한다."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd


PROTOCOL = Path(__file__).with_suffix(".json")
PAIR_COLUMNS = [
    "ticker", "cik", "metric", "fiscal_period", "accounting_basis", "metric_subtype", "unit",
    "prior_accession", "prior_accepted_at", "prior_lower_bound", "prior_upper_bound", "prior_midpoint",
    "current_accession", "current_accepted_at", "current_lower_bound", "current_upper_bound", "current_midpoint",
    "midpoint_delta", "midpoint_delta_ratio",
]


def build_pairs(protocol: dict) -> tuple[pd.DataFrame, dict]:
    review_report_path = Path(protocol["source_review_report"])
    review_path = Path(protocol["source_review_ledger"])
    source_review = json.loads(review_report_path.read_text(encoding="utf-8"))
    blocked = not bool(source_review["review_gate_passed"])
    pairs: list[dict] = []
    if not blocked:
        reviewed = pd.read_csv(review_path, dtype={"cik": str})
        valid = reviewed.loc[reviewed["review_decision"].eq("VALID")].copy()
        identity = protocol["pair_identity"]
        for _, group in valid.sort_values([*identity, "accepted_at"]).groupby(identity, dropna=False):
            records = list(group.itertuples(index=False))
            for prior, current in zip(records, records[1:]):
                if prior.accession_number == current.accession_number:
                    continue
                prior_midpoint = (float(prior.lower_bound) + float(prior.upper_bound)) / 2
                current_midpoint = (float(current.lower_bound) + float(current.upper_bound)) / 2
                delta = current_midpoint - prior_midpoint
                pairs.append({
                    "ticker": current.ticker, "cik": current.cik, "metric": current.metric,
                    "fiscal_period": current.fiscal_period, "accounting_basis": current.accounting_basis,
                    "metric_subtype": current.metric_subtype, "unit": current.unit,
                    "prior_accession": prior.accession_number, "prior_accepted_at": prior.accepted_at,
                    "prior_lower_bound": prior.lower_bound, "prior_upper_bound": prior.upper_bound,
                    "prior_midpoint": prior_midpoint, "current_accession": current.accession_number,
                    "current_accepted_at": current.accepted_at, "current_lower_bound": current.lower_bound,
                    "current_upper_bound": current.upper_bound, "current_midpoint": current_midpoint,
                    "midpoint_delta": delta,
                    "midpoint_delta_ratio": delta / abs(prior_midpoint) if prior_midpoint else None,
                })
    frame = pd.DataFrame(pairs, columns=PAIR_COLUMNS)
    coverage = len(frame) >= protocol["minimum_pairs"] and frame["ticker"].nunique() >= protocol["minimum_distinct_tickers"] if not frame.empty else False
    report = {
        "report_version": "herd-sec-guidance-revision-pairs-v1",
        "source_precision_gate_passed": not blocked,
        "pair_build_blocked": blocked,
        "source_qualified_pairs": len(frame),
        "distinct_tickers": int(frame["ticker"].nunique()) if not frame.empty else 0,
        "pair_coverage_gate_passed": coverage,
        "direction_labels_created": False,
        "price_outcomes_observed": False,
        "next_decision": "PREREGISTER_DIRECTION_LABELS" if coverage else "PAIR_BUILD_BLOCKED_BY_SOURCE_PRECISION" if blocked else "PAIR_COVERAGE_BLOCKED",
        "source_review_report_sha256": hashlib.sha256(review_report_path.read_bytes()).hexdigest(),
        "source_review_ledger_sha256": hashlib.sha256(review_path.read_bytes()).hexdigest(),
        "operational_action_ratio": 0.0,
    }
    return frame, report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pairs", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    pairs, report = build_pairs(protocol)
    pairs.to_csv(args.pairs, index=False, float_format="%.12g", lineterminator="\n")
    report["protocol_sha256"] = hashlib.sha256(PROTOCOL.read_bytes()).hexdigest()
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
