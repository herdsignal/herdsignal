"""기업 유형별 SEC PIT 상태 V2를 생성하고 독립 OOS로 평가한다."""

from __future__ import annotations

import argparse
import json
from datetime import date, datetime, time, timezone
from pathlib import Path

import pandas as pd

from herd.business_guard_features import (
    classify_as_of,
    prepare_relevant_facts,
)
from herd.business_guard_oos import evaluate_oos
from herd.business_guard_protocol import load_protocol as load_v1_protocol
from herd.sec_price_fold_link import _load_cik_facts


PROTOCOL_PATH = Path(__file__).with_name("business_state_v2_protocol.json")


class BusinessStateV2Error(ValueError):
    pass


def load_protocol(path: Path = PROTOCOL_PATH) -> tuple[dict, dict]:
    protocol = json.loads(path.read_text(encoding="utf-8"))
    if protocol.get("protocol_version") != "HERD_SEC_PIT_BUSINESS_STATE_V2" \
            or protocol.get("status") != "LOCKED_BEFORE_OOS_RESULTS":
        raise BusinessStateV2Error("business V2 protocol is not locked")
    if set(protocol["entity_types"]) != {"BANK", "REIT", "GENERAL"}:
        raise BusinessStateV2Error("entity types changed")
    if protocol["adoption_gate"]["minimum_test_folds_per_side"] < 4:
        raise BusinessStateV2Error("business OOS gate is too weak")
    forbidden = set(protocol["forbidden"])
    if not {"BUSINESS_STATE_CHANGES_HERD", "BUSINESS_STATE_CREATES_SELL", "UNKNOWN_AUTHORIZES_ADD_BUY"}.issubset(forbidden):
        raise BusinessStateV2Error("unsafe business-state role")
    return protocol, {"protocol_version": protocol["protocol_version"], "locked": True}


def entity_type(ticker: str, protocol: dict) -> str:
    if ticker in protocol["entity_types"]["BANK"]:
        return "BANK"
    if ticker in protocol["entity_types"]["REIT"]:
        return "REIT"
    return "GENERAL"


def classify_v2(prepared: list[dict], as_of: datetime, ticker: str, protocol: dict, v1_protocol: dict) -> dict:
    kind = entity_type(ticker, protocol)
    if kind != "GENERAL":
        return {
            "entity_type": kind,
            "guard_state": "UNKNOWN",
            "deterioration_flags": "",
            "flag_count": 0,
            "reason": f"UNSUPPORTED_{kind}_MEASUREMENT",
        }
    base = classify_as_of(prepared, as_of, v1_protocol)
    if base["guard_state"] == "UNKNOWN":
        return {"entity_type": kind, **base}
    flags = []
    if base["revenue_yoy"] < 0:
        flags.append("REVENUE_DIRECTION")
    if base["net_margin_yoy_change"] < 0:
        flags.append("MARGIN_DIRECTION")
    if base["operating_cash_flow_yoy"] is not None and base["operating_cash_flow_yoy"] < 0:
        flags.append("OPERATING_CASH_FLOW_DIRECTION")
    if base["liabilities_to_assets_yoy_change"] > 0:
        flags.append("LEVERAGE_DIRECTION")
    severe = (
        "MARGIN_DIRECTION" in flags
        and "OPERATING_CASH_FLOW_DIRECTION" in flags
        and base["operating_cash_flow_value"] <= 0
    )
    return {
        **base,
        "entity_type": kind,
        "guard_state": "VETO" if len(flags) >= 3 or severe else "PASS",
        "deterioration_flags": "|".join(flags),
        "flag_count": len(flags),
        "reason": "",
    }


def build_features(links: pd.DataFrame, corpora: list[Path], months: pd.DatetimeIndex, protocol: dict) -> tuple[pd.DataFrame, dict]:
    v1_protocol, _ = load_v1_protocol()
    mapping = links[(links["asset_type"] == "EQUITY") & links["cik"].notna()].drop_duplicates("ticker").set_index("ticker")["cik"]
    rows = []
    for ticker, cik in mapping.items():
        facts, corpus_status = _load_cik_facts(
            corpora, str(cik),
            filed_from=date(months.min().year - 2, 1, 1),
            filed_to=months.max().date(),
        )
        prepared = prepare_relevant_facts(facts, v1_protocol)
        for month in months:
            result = classify_v2(
                prepared,
                datetime.combine(month.date(), time.max, tzinfo=timezone.utc),
                ticker,
                protocol,
                v1_protocol,
            )
            rows.append({
                "ticker": ticker,
                "cik": cik,
                "month_end": month.date().isoformat(),
                "corpus_status": corpus_status,
                **result,
            })
    frame = pd.DataFrame(rows)
    return frame, {
        "format_version": "herd-business-state-features-v2",
        "rows": len(frame),
        "tickers": frame["ticker"].nunique(),
        "entity_type_counts": frame.groupby("entity_type").size().to_dict(),
        "state_counts": frame.groupby("guard_state").size().to_dict(),
        "strict_pit_rule": "SEC_ACCEPTANCE_DATETIME",
    }


def _read_price_frames(snapshot: Path) -> dict[str, pd.DataFrame]:
    import gzip
    manifest = json.loads((snapshot / "manifest.json").read_text(encoding="utf-8"))
    frames = {}
    for ticker, item in manifest["files"].items():
        if item["role"] != "EQUITY":
            continue
        with gzip.open(snapshot / item["path"], "rt", encoding="utf-8") as stream:
            frame = pd.read_csv(stream, parse_dates=["Date"])
        frame["Close"] = frame["Adj Close"]
        frames[ticker] = frame
    return frames


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--links", type=Path, required=True)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--folds", type=Path, required=True)
    parser.add_argument("--corpus", type=Path, action="append", required=True)
    parser.add_argument("--features", type=Path, required=True)
    parser.add_argument("--events", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    protocol, protocol_audit = load_protocol()
    links = pd.read_csv(args.links, dtype=str)
    manifest = json.loads((args.snapshot / "manifest.json").read_text(encoding="utf-8"))
    starts = [pd.Timestamp(item["start"]) for item in manifest["files"].values() if item["role"] == "EQUITY"]
    months = pd.date_range(max(starts), pd.Timestamp(manifest["files"]["SPY"]["end"]), freq="ME")
    features, audit = build_features(links, args.corpus, months, protocol)
    folds = pd.read_csv(args.folds, dtype=str).to_dict("records")
    compatibility = {
        "predictive_test": protocol["predictive_test"],
        "adoption_gate": {
            "minimum_events_per_side": protocol["adoption_gate"]["minimum_events_per_side"],
            "minimum_test_folds_per_side": protocol["adoption_gate"]["minimum_test_folds_per_side"],
            "minimum_directional_folds": protocol["adoption_gate"]["minimum_directional_folds"],
            "maximum_holm_p_value": protocol["adoption_gate"]["maximum_holm_p_value"],
            "required_primary_outcomes": protocol["adoption_gate"]["required_primary_outcomes"],
        },
    }
    events, summaries, report = evaluate_oos(features, _read_price_frames(args.snapshot), folds, compatibility)
    primary_events = events[events["horizon_months"] == protocol["predictive_test"]["primary_horizon_months"]]
    side_tickers = primary_events.groupby("guard_state")["ticker"].nunique().to_dict()
    ticker_gate = all(side_tickers.get(side, 0) >= protocol["adoption_gate"]["minimum_tickers_per_side"] for side in ("PASS", "VETO"))
    if not ticker_gate:
        report["decision"] = "REJECT_BUSINESS_STATE_V2_EVIDENCE"
    report.update({
        "report_version": "herd-business-state-oos-v2",
        "protocol": protocol_audit,
        "feature_audit": audit,
        "primary_side_tickers": side_tickers,
        "ticker_gate_passed": ticker_gate,
        "add_buy_veto_authorized": report["decision"] == "PASS_TO_ADD_BUY_VETO_ABLATION" and ticker_gate,
        "operational_action_ratio": 0.0,
        "blind_holdout_access": False,
    })
    report["limitations"] = [
        "The monitored fixed universe remains survivorship-biased.",
        "Banks and REITs fail closed as UNKNOWN until type-specific XBRL measurements are separately preregistered.",
        "Company Facts may contain filer errors; only acceptance-time-visible as-filed facts are used.",
        "A pass could authorize only an add-buy veto ablation, never HERD or a sell signal.",
    ]
    args.features.parent.mkdir(parents=True, exist_ok=True)
    features.to_csv(args.features, index=False)
    events.to_csv(args.events, index=False)
    pd.DataFrame(summaries).to_csv(args.report.with_suffix(".csv"), index=False)
    args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
