"""원문 검수 atomic fact 중 같은 의미·기간의 연속 공시만 수정쌍으로 연결한다."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd


PROTOCOL = Path(__file__).with_suffix(".json")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(protocol: dict) -> tuple[pd.DataFrame, dict]:
    bindings_path = Path(protocol["atomic_bindings"])
    report_path = Path(protocol["atomic_report"])
    source_report = json.loads(report_path.read_text())
    bindings = pd.read_csv(bindings_path, dtype={"cik": str})
    eligible = bindings.loc[bindings["pair_eligible"].eq(True)].copy()
    pairs = []
    identity = protocol["pair_identity"]
    for _, group in eligible.sort_values([*identity, "accepted_at", "binding_id"]).groupby(
        identity, dropna=False,
    ):
        filings = group.drop_duplicates("accession_number", keep="last")
        records = list(filings.itertuples(index=False))
        for prior, current in zip(records, records[1:]):
            pairs.append({
                "ticker": current.ticker,
                "cik": current.cik,
                "metric": current.metric,
                "fiscal_period": current.fiscal_period,
                "accounting_basis": current.accounting_basis,
                "metric_subtype": current.metric_subtype,
                "unit": current.unit,
                "prior_binding_id": prior.binding_id,
                "prior_accession": prior.accession_number,
                "prior_accepted_at": prior.accepted_at,
                "prior_midpoint": prior.midpoint,
                "current_binding_id": current.binding_id,
                "current_accession": current.accession_number,
                "current_accepted_at": current.accepted_at,
                "current_midpoint": current.midpoint,
                "midpoint_delta": float(current.midpoint) - float(prior.midpoint),
                "midpoint_delta_ratio": (
                    (float(current.midpoint) - float(prior.midpoint)) / abs(float(prior.midpoint))
                    if float(prior.midpoint) else None
                ),
            })
    frame = pd.DataFrame(pairs)
    ticker_counts = (
        frame["ticker"].value_counts().sort_index().to_dict() if not frame.empty else {}
    )
    accepted_years = (
        pd.to_datetime(frame["current_accepted_at"], utc=True).dt.year.nunique()
        if not frame.empty else 0
    )
    maximum_ticker_share = (
        max(ticker_counts.values()) / len(frame) if ticker_counts else 0.0
    )
    coverage = bool(
        len(frame) >= protocol["minimum_pairs"]
        and frame["ticker"].nunique() >= protocol["minimum_distinct_tickers"]
        and accepted_years >= protocol.get("minimum_distinct_accepted_years", 0)
    ) if not frame.empty else False
    concentration_warning = (
        maximum_ticker_share > protocol.get("ticker_concentration_warning_threshold", 1.0)
    )
    report = {
        "report_version": protocol.get(
            "report_version", "herd-sec-guidance-atomic-pairs-v1"
        ),
        "atomic_source_fact_authority_only": source_report["source_fact_authority_only"],
        "pair_eligible_bindings": len(eligible),
        "atomic_revision_pairs": len(frame),
        "distinct_tickers": int(frame["ticker"].nunique()) if not frame.empty else 0,
        "minimum_pairs": protocol["minimum_pairs"],
        "minimum_distinct_tickers": protocol["minimum_distinct_tickers"],
        "distinct_accepted_years": int(accepted_years),
        "minimum_distinct_accepted_years": protocol.get(
            "minimum_distinct_accepted_years", 0
        ),
        "pairs_by_ticker": ticker_counts,
        "maximum_ticker_pair_share": maximum_ticker_share,
        "ticker_concentration_warning_threshold": protocol.get(
            "ticker_concentration_warning_threshold", 1.0
        ),
        "ticker_concentration_warning": concentration_warning,
        "pair_coverage_gate_passed": coverage,
        "direction_labels_created": False,
        "guidance_veto_authorized": False,
        "sell_authority": False,
        "herd_weight_authority": False,
        "next_decision": (
            "PREREGISTER_TICKER_BALANCED_GUIDANCE_OOS"
            if coverage else "ATOMIC_PAIR_COVERAGE_BLOCKED"
        ),
        "atomic_bindings_sha256": _sha256(bindings_path),
        "atomic_report_sha256": _sha256(report_path),
        "price_outcomes_observed": False,
        "operational_action_ratio": 0.0,
    }
    return frame, report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pairs", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    protocol = json.loads(PROTOCOL.read_text())
    pairs, report = build(protocol)
    pairs.to_csv(args.pairs, index=False, float_format="%.12g", lineterminator="\n")
    report["protocol_sha256"] = _sha256(PROTOCOL)
    report["pairs_sha256"] = _sha256(args.pairs)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
