"""SEC 접수 시각 기준으로 월별 기업 상태 PASS/VETO/UNKNOWN을 생성한다."""

from __future__ import annotations

import argparse
import csv
import json
from datetime import date, datetime, time, timezone
from pathlib import Path

import pandas as pd

from herd.business_guard_protocol import load_protocol
from herd.sec_price_fold_link import _load_cik_facts
from herd.sec_point_in_time_fundamentals import parse_sec_timestamp

ALIASES = {
    "revenue": (
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "RevenueFromContractWithCustomerIncludingAssessedTax",
        "Revenues",
        "SalesRevenueNet",
        "SalesRevenueServicesNet",
    ),
    "earnings": ("NetIncomeLoss", "ProfitLoss"),
    "operating_cash_flow": (
        "NetCashProvidedByUsedInOperatingActivities",
        "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations",
    ),
    "assets": ("Assets",),
    "liabilities": ("Liabilities",),
    "equity": (
        "StockholdersEquity",
        "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
    ),
}


class BusinessGuardFeatureError(RuntimeError):
    pass


def _read_csv(path: Path) -> list[dict]:
    with Path(path).open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _number(row: dict) -> float | None:
    try:
        value = json.loads(row["value_json"])
        return float(value) if value is not None else None
    except (TypeError, ValueError, json.JSONDecodeError):
        return None


def prepare_relevant_facts(rows: list[dict], protocol: dict) -> list[dict]:
    """허용된 표준 개념만 남기고 기간·접수시각을 타입화한다."""
    allowed_forms = set(protocol["data_contract"]["allowed_forms"])
    alias_group = {
        concept: group for group, aliases in ALIASES.items()
        for concept in aliases
    }
    priority = {
        (group, concept): index for group, aliases in ALIASES.items()
        for index, concept in enumerate(aliases)
    }
    prepared = []
    for row in rows:
        group = alias_group.get(row["concept"])
        value = _number(row)
        if (
            group is None
            or row["taxonomy"] != "us-gaap"
            or row["unit"] != "USD"
            or row["form"] not in allowed_forms
            or not row["accepted_at"]
            or not row["period_end"]
            or value is None
        ):
            continue
        end = date.fromisoformat(row["period_end"])
        start = (
            date.fromisoformat(row["period_start"])
            if row["period_start"] else None
        )
        prepared.append({
            "group": group,
            "concept": row["concept"],
            "concept_priority": priority[(group, row["concept"])],
            "period_start": start,
            "period_end": end,
            "duration_days": (end - start).days if start else 0,
            "accepted_at": parse_sec_timestamp(row["accepted_at"]),
            "accession_number": row["accession_number"],
            "value": value,
        })
    return prepared


def _as_filed_periods(rows: list[dict], as_of: datetime) -> dict[tuple, dict]:
    """같은 그룹·기간은 당시까지 접수된 최신 수정본 한 건으로 축약한다."""
    selected = {}
    for row in rows:
        if row["accepted_at"] > as_of:
            continue
        key = (row["group"], row["period_start"], row["period_end"])
        current = selected.get(key)
        rank = (
            row["accepted_at"],
            -row["concept_priority"],
            row["accession_number"],
        )
        if current is None or rank > current["_rank"]:
            selected[key] = {**row, "_rank": rank}
    return selected


def _nearest_prior_year(latest: dict, candidates: list[dict]) -> dict | None:
    matches = [
        row for row in candidates
        if 330 <= (latest["period_end"] - row["period_end"]).days <= 400
    ]
    return max(matches, key=lambda row: row["period_end"], default=None)


def _latest_with_prior(rows: list[dict]) -> tuple[dict | None, dict | None]:
    if not rows:
        return None, None
    latest = max(rows, key=lambda row: row["period_end"])
    return latest, _nearest_prior_year(latest, rows)


def classify_as_of(
    prepared: list[dict],
    as_of: datetime,
    protocol: dict,
) -> dict:
    periods = list(_as_filed_periods(prepared, as_of).values())
    contract = protocol["data_contract"]
    q_min = contract["duration_days_quarterly_minimum"]
    q_max = contract["duration_days_quarterly_maximum"]
    a_min = contract["duration_days_annual_minimum"]
    a_max = contract["duration_days_annual_maximum"]

    by_group = {
        group: [row for row in periods if row["group"] == group]
        for group in ALIASES
    }
    revenue, prior_revenue = _latest_with_prior([
        row for row in by_group["revenue"]
        if q_min <= row["duration_days"] <= q_max
    ])
    earnings_candidates = [
        row for row in by_group["earnings"]
        if q_min <= row["duration_days"] <= q_max
    ]
    earnings = next((
        row for row in sorted(
            earnings_candidates, key=lambda item: item["accepted_at"], reverse=True
        )
        if revenue and row["period_end"] == revenue["period_end"]
    ), None)
    prior_earnings = next((
        row for row in earnings_candidates
        if prior_revenue and row["period_end"] == prior_revenue["period_end"]
    ), None)
    cash_flow, prior_cash_flow = _latest_with_prior([
        row for row in by_group["operating_cash_flow"]
        if a_min <= row["duration_days"] <= a_max
    ])
    assets, prior_assets = _latest_with_prior(by_group["assets"])
    liabilities = next((
        row for row in by_group["liabilities"]
        if assets and row["period_end"] == assets["period_end"]
    ), None)
    prior_liabilities = next((
        row for row in by_group["liabilities"]
        if prior_assets and row["period_end"] == prior_assets["period_end"]
    ), None)
    equity = next((
        row for row in by_group["equity"]
        if assets and row["period_end"] == assets["period_end"]
    ), None)
    prior_equity = next((
        row for row in by_group["equity"]
        if prior_assets and row["period_end"] == prior_assets["period_end"]
    ), None)
    if liabilities is None and assets and equity:
        liabilities = {
            **assets,
            "value": assets["value"] - equity["value"],
            "accepted_at": max(assets["accepted_at"], equity["accepted_at"]),
        }
    if prior_liabilities is None and prior_assets and prior_equity:
        prior_liabilities = {
            **prior_assets,
            "value": prior_assets["value"] - prior_equity["value"],
            "accepted_at": max(
                prior_assets["accepted_at"], prior_equity["accepted_at"]
            ),
        }

    required = (
        revenue, prior_revenue, earnings, prior_earnings,
        cash_flow, prior_cash_flow, assets, prior_assets,
        liabilities, prior_liabilities,
    )
    newest = max(
        (row["accepted_at"] for row in required if row is not None),
        default=None,
    )
    stale = (
        newest is None
        or (as_of - newest).days > contract["maximum_fact_age_days"]
    )
    if any(row is None for row in required) or stale:
        return {
            "guard_state": "UNKNOWN",
            "deterioration_flags": "",
            "flag_count": 0,
            "latest_fact_accepted_at": newest.isoformat() if newest else "",
            "reason": "MISSING_COMPARABLE_FACTS" if not stale else "STALE_FACTS",
        }

    revenue_growth = revenue["value"] / prior_revenue["value"] - 1
    margin = earnings["value"] / revenue["value"]
    prior_margin = prior_earnings["value"] / prior_revenue["value"]
    cash_flow_growth = (
        cash_flow["value"] / prior_cash_flow["value"] - 1
        if prior_cash_flow["value"] != 0 else None
    )
    debt_ratio = liabilities["value"] / assets["value"]
    prior_debt_ratio = prior_liabilities["value"] / prior_assets["value"]

    flags = []
    if revenue_growth <= -0.10:
        flags.append("REVENUE")
    net_loss = earnings["value"] < 0
    if net_loss or margin - prior_margin <= -0.05:
        flags.append("EARNINGS")
    non_positive_cash = cash_flow["value"] <= 0
    if (
        non_positive_cash
        or cash_flow_growth is not None and cash_flow_growth <= -0.30
    ):
        flags.append("OPERATING_CASH_FLOW")
    if debt_ratio >= 0.60 and debt_ratio - prior_debt_ratio >= 0.10:
        flags.append("DEBT_BURDEN")
    veto = len(flags) >= 2 or (net_loss and non_positive_cash)
    return {
        "guard_state": "VETO" if veto else "PASS",
        "deterioration_flags": "|".join(flags),
        "flag_count": len(flags),
        "latest_fact_accepted_at": newest.isoformat(),
        "reason": "",
        "revenue_yoy": revenue_growth,
        "net_margin": margin,
        "net_margin_yoy_change": margin - prior_margin,
        "operating_cash_flow_yoy": cash_flow_growth,
        "operating_cash_flow_value": cash_flow["value"],
        "liabilities_to_assets": debt_ratio,
        "liabilities_to_assets_yoy_change": debt_ratio - prior_debt_ratio,
    }


def build_monthly_features(
    link_rows: list[dict],
    corpora: list[Path],
    month_ends: pd.DatetimeIndex,
    protocol: dict,
) -> tuple[list[dict], dict]:
    mappings = {}
    for row in link_rows:
        if row["asset_type"] == "EQUITY" and row["cik"]:
            mappings.setdefault(row["ticker"], row["cik"])
    first_month = month_ends.min().date()
    start = date(first_month.year - 2, first_month.month, first_month.day)
    end = month_ends.max().date()
    output = []
    status_counts = {}
    for ticker, cik in sorted(mappings.items()):
        facts, corpus_status = _load_cik_facts(
            corpora, cik, filed_from=start, filed_to=end
        )
        prepared = prepare_relevant_facts(facts, protocol)
        for month_end in month_ends:
            boundary = datetime.combine(
                month_end.date(), time.max, tzinfo=timezone.utc
            )
            result = classify_as_of(prepared, boundary, protocol)
            state = result["guard_state"]
            status_counts[state] = status_counts.get(state, 0) + 1
            output.append({
                "ticker": ticker,
                "cik": cik,
                "month_end": month_end.date().isoformat(),
                "corpus_status": corpus_status,
                **result,
            })
    return output, {
        "format_version": "herd-business-guard-features-v1",
        "tickers": len(mappings),
        "months": len(month_ends),
        "rows": len(output),
        "state_counts": status_counts,
        "strict_pit_rule": "SEC_ACCEPTANCE_DATETIME",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("links", type=Path)
    parser.add_argument("price_manifest", type=Path)
    parser.add_argument("output_csv", type=Path)
    parser.add_argument("output_audit", type=Path)
    parser.add_argument("--corpus", type=Path, action="append", required=True)
    args = parser.parse_args()
    manifest = json.loads(args.price_manifest.read_text(encoding="utf-8"))
    starts = [pd.Timestamp(item["start"]) for item in manifest["files"].values()]
    ends = [pd.Timestamp(item["end"]) for item in manifest["files"].values()]
    month_ends = pd.date_range(max(starts), min(ends), freq="ME")
    protocol, protocol_audit = load_protocol()
    rows, audit = build_monthly_features(
        _read_csv(args.links), args.corpus, month_ends, protocol
    )
    args.output_csv.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(
        args.output_csv, index=False, float_format="%.12g"
    )
    audit["protocol"] = protocol_audit
    args.output_audit.write_text(
        json.dumps(audit, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(audit, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
