"""SEC PIT 기업 기대 변화 feature를 생성한다."""

from __future__ import annotations

import argparse
import gzip
import json
from datetime import date, datetime, time, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from herd.sec_point_in_time_fundamentals import parse_sec_timestamp
from herd.sec_price_fold_link import _load_cik_facts


ROOT = Path(__file__).resolve().parents[2]
PROTOCOL_PATH = Path(__file__).with_suffix(".json")


def load_protocol(path: Path = PROTOCOL_PATH) -> dict:
    protocol = json.loads(path.read_text(encoding="utf-8"))
    if protocol.get("status") != "LOCKED_BEFORE_FEATURE_OUTPUT":
        raise ValueError("business expectation feature protocol must be locked")
    required = {"USE_FACT_BEFORE_SEC_ACCEPTANCE", "FILL_MISSING_DILUTION_WITH_ZERO", "CREATE_SELL_SIGNAL"}
    if not required.issubset(protocol.get("forbidden", [])):
        raise ValueError("SEC PIT or action boundary weakened")
    return protocol


def _disclosure_changes(group: pd.DataFrame, column: str) -> pd.Series:
    output = pd.Series(np.nan, index=group.index, dtype=float)
    usable = group[group[column].notna()].copy()
    if usable.empty:
        return output
    disclosures = usable.drop_duplicates("latest_fact_accepted_at", keep="first")
    changes = disclosures[column].astype(float).diff()
    output.loc[disclosures.index] = changes
    return output.ffill()


def _share_facts(rows: list[dict], protocol: dict) -> list[dict]:
    priority = {concept: rank for rank, concept in enumerate(protocol["share_concepts_priority"])}
    output = []
    for row in rows:
        if row.get("taxonomy") not in {"dei", "us-gaap"} or row.get("concept") not in priority or row.get("unit") != "shares":
            continue
        try:
            value = float(json.loads(row["value_json"]))
            accepted = parse_sec_timestamp(row["accepted_at"])
            period_end = date.fromisoformat(row["period_end"])
        except (TypeError, ValueError, json.JSONDecodeError):
            continue
        if value <= 0 or not row.get("accepted_at"):
            continue
        output.append({"value": value, "accepted_at": accepted, "period_end": period_end, "priority": priority[row["concept"]], "concept": row["concept"]})
    return output


def dilution_as_of(facts: list[dict], as_of: datetime, splits: pd.Series | None = None) -> float | None:
    visible = [row for row in facts if row["accepted_at"] <= as_of and row["period_end"] <= as_of.date()]
    if not visible:
        return None
    latest = max(visible, key=lambda row: (row["period_end"], -row["priority"], row["accepted_at"]))
    prior = [row for row in visible if row["concept"] == latest["concept"] and 330 <= (latest["period_end"] - row["period_end"]).days <= 400]
    if not prior:
        return None
    previous = max(prior, key=lambda row: (row["period_end"], -row["priority"], row["accepted_at"]))
    split_factor = 1.0
    if splits is not None and not splits.empty:
        relevant = splits[(splits.index.date > previous["period_end"]) & (splits.index.date <= latest["period_end"])]
        if not relevant.empty:
            split_factor = float(relevant.prod())
    adjusted_previous = previous["value"] * split_factor
    if not adjusted_previous:
        return None
    change = latest["value"] / adjusted_previous - 1
    return None if abs(change) > 1.0 else change


def _split_ledgers(snapshot: Path, tickers: set[str]) -> dict[str, pd.Series]:
    manifest = json.loads((snapshot / "manifest.json").read_text(encoding="utf-8"))
    ledgers = {}
    for ticker in tickers:
        item = manifest["files"].get(ticker)
        if not item:
            ledgers[ticker] = pd.Series(dtype=float)
            continue
        with gzip.open(snapshot / item["path"], "rt", encoding="utf-8") as stream:
            frame = pd.read_csv(stream, parse_dates=["Date"])
        splits = frame.loc[frame["Stock Splits"].astype(float).ne(0), ["Date", "Stock Splits"]]
        ledgers[ticker] = splits.set_index("Date")["Stock Splits"].astype(float)
    return ledgers


def build(base: pd.DataFrame, protocol: dict) -> tuple[pd.DataFrame, dict]:
    frame = base.copy()
    frame["month_end"] = pd.to_datetime(frame["month_end"])
    frame["latest_fact_accepted_at"] = frame["latest_fact_accepted_at"].fillna("")
    frame = frame.sort_values(["ticker", "month_end"]).reset_index(drop=True)
    mappings = {
        "revenue_yoy": "revenue_growth_acceleration",
        "net_margin_yoy_change": "margin_change_acceleration",
        "operating_cash_flow_yoy": "operating_cash_flow_growth_change",
    }
    for source, target in mappings.items():
        frame[target] = frame.groupby("ticker", group_keys=False).apply(
            lambda group: _disclosure_changes(group, source), include_groups=False
        ).reset_index(level=0, drop=True)

    corpora = [ROOT / path for path in protocol["sec_corpora"]]
    split_ledgers = _split_ledgers(ROOT / protocol["price_snapshot"], set(frame["ticker"]))
    dilution = pd.Series(np.nan, index=frame.index, dtype=float)
    for (ticker, cik), group in frame.groupby(["ticker", "cik"], dropna=True):
        rows, _ = _load_cik_facts(
            corpora, f"{int(cik):010d}",
            filed_from=date(group["month_end"].min().year - 2, 1, 1),
            filed_to=group["month_end"].max().date(),
        )
        facts = _share_facts(rows, protocol)
        for index, month in group["month_end"].items():
            dilution.loc[index] = dilution_as_of(
                facts, datetime.combine(month.date(), time.max, tzinfo=timezone.utc), split_ledgers[ticker]
            )
    frame["share_dilution_yoy"] = dilution
    feature_columns = [*mappings.values(), "share_dilution_yoy"]
    eligible = frame[frame["entity_type"].eq("GENERAL")]
    audit = {
        "report_version": "HERD_EXPECTATION_BUSINESS_FEATURES_V1",
        "status": "FEATURES_READY",
        "rows": len(frame), "tickers": int(frame["ticker"].nunique()),
        "general_company_rows": len(eligible),
        "coverage": {column: float(eligible[column].notna().mean()) for column in feature_columns},
        "feature_columns": feature_columns,
        "strict_pit_rule": "SEC_ACCEPTANCE_DATETIME",
        "sell_authority": False, "operational_action_ratio": 0.0,
        "survivorship_safe": False, "claim_boundary": protocol["claim_boundary"],
    }
    return frame, audit


def run(protocol_path: Path = PROTOCOL_PATH) -> tuple[pd.DataFrame, dict]:
    protocol = load_protocol(protocol_path)
    return build(pd.read_csv(ROOT / protocol["base_features"]), protocol)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--features", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    features, report = run()
    features.to_csv(args.features, index=False)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
