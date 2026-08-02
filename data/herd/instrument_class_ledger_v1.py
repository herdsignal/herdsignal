"""Build a fail-closed instrument and event classification ledger."""

from __future__ import annotations

import gzip
import hashlib
import io
import json
from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = Path(__file__).with_suffix(".json")
TICKER_LEDGER_PATH = ROOT / "data/reports/instrument_class_ledger_v1.csv"
EVENT_LEDGER_PATH = ROOT / "data/reports/instrument_class_event_ledger_v1.csv.gz"
SEGMENT_PATH = ROOT / "data/reports/fixed_policy_by_instrument_class_v1.csv"
REPORT_PATH = ROOT / "data/reports/instrument_class_ledger_v1.json"
CONTRACT_VERSION = "HERD_INSTRUMENT_CLASS_LEDGER_V1"
EXPECTED_FORBIDDEN = {
    "TREAT_CURRENT_INDEX_MEMBERSHIP_AS_HISTORICAL_LARGE_CAP_EVIDENCE",
    "TREAT_CURRENT_GICS_AS_POINT_IN_TIME_CLASSIFICATION",
    "POOL_LEVERAGED_OR_INVERSE_ETPS_WITH_OPERATING_COMPANIES",
    "IMPUTE_MISSING_PIT_PROFITABILITY_OR_MARKET_CAP",
    "SELECT_ACTION_POLICY_FROM_DESCRIPTIVE_CLASS_RESULTS",
    "AUTHORIZE_OPERATIONAL_ACTION",
    "OPEN_BLIND_HOLDOUT",
}


class InstrumentClassLedgerError(RuntimeError):
    """Raised when classification inputs or fail-closed boundaries change."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _rooted(relative: str) -> Path:
    path = (ROOT / relative).resolve()
    if not path.is_relative_to(ROOT) or not path.is_file():
        raise InstrumentClassLedgerError(f"missing ledger input: {relative}")
    return path


def load_contract(path: Path = CONTRACT_PATH) -> dict[str, Any]:
    contract = json.loads(path.read_text(encoding="utf-8"))
    if (
        contract.get("contract_version") != CONTRACT_VERSION
        or contract.get("status") != "LOCKED_BEFORE_CLASS_SEGMENT_RESULTS"
        or contract.get("objective")
        != "SEPARATE_SECURITY_STRUCTURE_FROM_POINT_IN_TIME_COMPANY_STYLE_BEFORE_ACTION_EDGE_RESEARCH"
    ):
        raise InstrumentClassLedgerError("instrument class contract is not locked")
    if len(contract.get("inputs", [])) != 9:
        raise InstrumentClassLedgerError("instrument class input set is incomplete")
    for item in contract["inputs"]:
        if _sha256(_rooted(item["path"])) != item.get("sha256"):
            raise InstrumentClassLedgerError(
                f"pinned instrument input changed: {item['path']}"
            )

    structure = contract.get("security_structure", {})
    if (
        set(structure.get("market_etfs", [])) != {"DIA", "IWM", "QQQ", "SPY"}
        or len(structure.get("sector_etfs", [])) != 10
        or not {"BITX", "SOXL", "SQQQ", "TQQQ"}.issubset(
            structure.get("leveraged_or_inverse_etps", [])
        )
    ):
        raise InstrumentClassLedgerError("security structure boundary changed")

    style = contract.get("economic_company_style", {})
    high_growth = style.get("unprofitable_high_growth", {})
    large_growth = style.get("profitable_large_cap_growth", {})
    if (
        set(style.get("semiconductor_gics_sub_industries", []))
        != {"Semiconductors", "Semiconductor Materials & Equipment"}
        or style.get("semiconductor_source_is_point_in_time") is not False
        or high_growth.get("minimum_revenue_yoy") != 0.2
        or high_growth.get("maximum_net_margin") != 0.0
        or high_growth.get("requires_corpus_status") != "PIT_FACTS_READY"
        or large_growth.get("requires_point_in_time_market_cap") is not True
        or large_growth.get("missing_market_cap_result")
        != "UNRESOLVED_MISSING_PIT_MARKET_CAP"
    ):
        raise InstrumentClassLedgerError("economic company style boundary changed")

    reporting = contract.get("reporting", {})
    if (
        reporting.get("reaggregate_existing_fixed_policies_only") is not True
        or reporting.get("select_policy_from_class_results") is not False
        or reporting.get("missing_class_may_not_be_imputed") is not True
    ):
        raise InstrumentClassLedgerError("classification reporting boundary changed")
    if set(contract.get("forbidden", [])) != EXPECTED_FORBIDDEN:
        raise InstrumentClassLedgerError("classification forbidden set changed")
    firewall = contract.get("firewall", {})
    if (
        firewall.get("direction_evidence_admitted") is not False
        or firewall.get("operational_action") != "HOLD"
        or firewall.get("operational_action_ratio") != 0.0
        or firewall.get("survivorship_safe") is not False
        or firewall.get("blind_holdout_access") is not False
    ):
        raise InstrumentClassLedgerError("classification firewall weakened")
    return contract


def classify_security_structure(ticker: str, role: str, contract: dict[str, Any]) -> str:
    ticker = ticker.upper()
    structure = contract["security_structure"]
    if ticker in structure["leveraged_or_inverse_etps"]:
        return "LEVERAGED_OR_INVERSE_ETP"
    if ticker in structure["market_etfs"]:
        return "BROAD_MARKET_ETF"
    if ticker in structure["sector_etfs"]:
        return "SECTOR_ETF"
    if role == "EQUITY":
        return "OPERATING_COMPANY_EQUITY"
    return structure["unknown_etp_default"]


def _input(contract: dict[str, Any], suffix: str) -> Path:
    matches = [item for item in contract["inputs"] if item["path"].endswith(suffix)]
    if len(matches) != 1:
        raise InstrumentClassLedgerError(f"ambiguous contract input: {suffix}")
    return _rooted(matches[0]["path"])


def _manifest_inputs(contract: dict[str, Any]) -> dict[str, tuple[Path, dict[str, Any]]]:
    result = {}
    for item in contract["inputs"]:
        if "universe_role" not in item:
            continue
        path = _rooted(item["path"])
        result[item["universe_role"]] = (
            path,
            json.loads(path.read_text(encoding="utf-8")),
        )
    if set(result) != {"PRIMARY", "INDEPENDENT_CURRENT_CONSTITUENTS"}:
        raise InstrumentClassLedgerError("price universe manifests are incomplete")
    return result


def _current_company_metadata(contract: dict[str, Any]) -> pd.DataFrame:
    constituents = pd.read_csv(_input(contract, "sp500_constituents_20260721.csv"))
    constituents = constituents.rename(
        columns={
            "Symbol": "ticker",
            "Security": "company",
            "GICS Sector": "gics_sector",
            "GICS Sub-Industry": "gics_sub_industry",
            "CIK": "cik",
        }
    )
    constituents["ticker"] = constituents["ticker"].astype(str).str.replace(".", "-", regex=False).str.upper()
    return constituents[["ticker", "company", "cik", "gics_sector", "gics_sub_industry"]]


def build_ticker_ledger(contract: dict[str, Any]) -> pd.DataFrame:
    manifests = _manifest_inputs(contract)
    records: dict[str, dict[str, Any]] = {}
    for universe_role, (_, manifest) in manifests.items():
        for ticker, receipt in manifest["files"].items():
            row = records.setdefault(
                ticker,
                {
                    "ticker": ticker,
                    "price_roles": set(),
                    "universe_roles": set(),
                },
            )
            row["price_roles"].add(str(receipt.get("role", "UNKNOWN")))
            row["universe_roles"].add(universe_role)
    for ticker in contract["security_structure"]["leveraged_or_inverse_etps"]:
        records.setdefault(
            ticker,
            {"ticker": ticker, "price_roles": {"ETP"}, "universe_roles": set()},
        )

    metadata = _current_company_metadata(contract).set_index("ticker").to_dict("index")
    semis = set(contract["economic_company_style"]["semiconductor_gics_sub_industries"])
    output = []
    for ticker in sorted(records):
        source = records[ticker]
        roles = sorted(source["price_roles"])
        role = "EQUITY" if roles == ["EQUITY"] else (roles[0] if len(roles) == 1 else "MIXED")
        structure = classify_security_structure(ticker, role, contract)
        meta = metadata.get(ticker, {})
        is_semi = meta.get("gics_sub_industry") in semis
        eligibility = contract["research_eligibility"].get(
            structure,
            "DIAGNOSTIC_ONLY_UNTIL_PIT_STYLE_RESOLVED",
        )
        if structure == "OPERATING_COMPANY_EQUITY" and is_semi:
            eligibility = contract["research_eligibility"]["CYCLICAL_SEMICONDUCTOR"]
        output.append(
            {
                "ticker": ticker,
                "security_structure_class": structure,
                "price_role": role,
                "universe_roles": "|".join(sorted(source["universe_roles"])),
                "company": meta.get("company"),
                "cik": meta.get("cik"),
                "gics_sector_current": meta.get("gics_sector"),
                "gics_sub_industry_current": meta.get("gics_sub_industry"),
                "current_semiconductor_cohort": bool(is_semi),
                "gics_point_in_time": False if meta else None,
                "research_eligibility": eligibility,
            }
        )
    return pd.DataFrame(output)


def _latest_pit_feature(features: pd.DataFrame, ticker: str, observation: pd.Timestamp) -> pd.Series | None:
    # A filing accepted after the US close must not enter that session's signal.
    # Requiring it before the observation calendar day is conservative across
    # daylight-saving changes and makes same-day filings available next session.
    availability_cutoff = observation.normalize().tz_localize("UTC")
    subset = features.loc[
        (features["ticker"] == ticker)
        & (features["month_end"] <= observation.normalize())
        & (features["latest_fact_accepted_at"] < availability_cutoff)
        & (features["corpus_status"] == "PIT_FACTS_READY")
    ]
    if subset.empty:
        return None
    return subset.sort_values(["month_end", "latest_fact_accepted_at"]).iloc[-1]


def _company_style(feature: pd.Series | None, contract: dict[str, Any]) -> tuple[str, str]:
    if feature is None:
        return "UNRESOLVED", "NO_TIME_VALID_PIT_COMPANY_FEATURE"
    revenue_yoy = feature.get("revenue_yoy")
    net_margin = feature.get("net_margin")
    if pd.isna(revenue_yoy) or pd.isna(net_margin):
        return "UNRESOLVED", "MISSING_PIT_REVENUE_GROWTH_OR_MARGIN"
    high_growth = contract["economic_company_style"]["unprofitable_high_growth"]
    if revenue_yoy >= high_growth["minimum_revenue_yoy"] and net_margin < high_growth["maximum_net_margin"]:
        return "UNPROFITABLE_HIGH_GROWTH", "PIT_REVENUE_GROWTH_AND_NEGATIVE_MARGIN"
    large_growth = contract["economic_company_style"]["profitable_large_cap_growth"]
    if revenue_yoy >= large_growth["minimum_revenue_yoy"] and net_margin >= large_growth["minimum_net_margin"]:
        return "UNRESOLVED", large_growth["missing_market_cap_result"]
    return "OTHER_OPERATING_COMPANY", "PIT_FEATURES_DO_NOT_MATCH_LOCKED_STYLE"


def build_event_ledger(contract: dict[str, Any], ticker_ledger: pd.DataFrame) -> pd.DataFrame:
    baseline = pd.read_csv(
        _input(contract, "fixed_policy_economic_baselines_v1.csv.gz"),
        parse_dates=["signal_date", "observation_session"],
    )
    events = baseline.loc[
        (baseline["policy_id"] == "MATCHED_HOLD")
        & (baseline["one_way_cost_bps"] == 10),
        ["ticker", "universe_role", "fold_id", "signal_date", "observation_session"],
    ].copy()
    if events.duplicated(["ticker", "fold_id", "signal_date"]).any():
        raise InstrumentClassLedgerError("baseline event keys are not unique")
    ticker_map = ticker_ledger.set_index("ticker")
    missing = set(events["ticker"]) - set(ticker_map.index)
    if missing:
        raise InstrumentClassLedgerError(f"event tickers missing from ledger: {sorted(missing)}")

    features = pd.read_csv(
        _input(contract, "business_state_features_v2.csv"),
        parse_dates=["month_end", "latest_fact_accepted_at"],
    )
    features["ticker"] = features["ticker"].astype(str).str.upper()
    records = []
    for event in events.itertuples(index=False):
        ticker_row = ticker_map.loc[event.ticker]
        structure = ticker_row["security_structure_class"]
        feature = None
        style, style_reason = ("NOT_APPLICABLE", "NON_OPERATING_COMPANY")
        if structure == "OPERATING_COMPANY_EQUITY":
            feature = _latest_pit_feature(features, event.ticker, event.observation_session)
            style, style_reason = _company_style(feature, contract)
        if structure == "LEVERAGED_OR_INVERSE_ETP":
            segment = "LEVERAGED_OR_INVERSE_ETP"
        elif structure != "OPERATING_COMPANY_EQUITY":
            segment = structure
        elif bool(ticker_row["current_semiconductor_cohort"]):
            segment = "CYCLICAL_SEMICONDUCTOR_CURRENT_GICS"
        elif style == "UNPROFITABLE_HIGH_GROWTH":
            segment = style
        elif style == "OTHER_OPERATING_COMPANY":
            segment = style
        else:
            segment = "OTHER_OR_UNRESOLVED_OPERATING_COMPANY"
        records.append(
            {
                **event._asdict(),
                "security_structure_class": structure,
                "economic_company_style": style,
                "style_resolution_reason": style_reason,
                "research_segment": segment,
                "current_semiconductor_cohort": bool(ticker_row["current_semiconductor_cohort"]),
                "gics_point_in_time": False if pd.notna(ticker_row["gics_sector_current"]) else None,
                "pit_feature_month_end": feature["month_end"] if feature is not None else pd.NaT,
                "pit_feature_accepted_at": feature["latest_fact_accepted_at"] if feature is not None else pd.NaT,
                "pit_revenue_yoy": feature["revenue_yoy"] if feature is not None else None,
                "pit_net_margin": feature["net_margin"] if feature is not None else None,
            }
        )
    return pd.DataFrame(records).sort_values(["universe_role", "ticker", "signal_date", "fold_id"])


def summarize_by_segment(contract: dict[str, Any], events: pd.DataFrame) -> pd.DataFrame:
    baseline = pd.read_csv(
        _input(contract, "fixed_policy_economic_baselines_v1.csv.gz"),
        parse_dates=["signal_date"],
    )
    joined = baseline.merge(
        events[["ticker", "universe_role", "fold_id", "signal_date", "research_segment"]],
        on=["ticker", "universe_role", "fold_id", "signal_date"],
        how="left",
        validate="many_to_one",
    )
    if joined["research_segment"].isna().any():
        raise InstrumentClassLedgerError("baseline rows were not fully classified")
    grouped = joined.groupby(
        ["universe_role", "research_segment", "policy_id", "one_way_cost_bps"],
        sort=True,
        dropna=False,
    )
    rows = []
    minimum = contract["reporting"]["minimum_events_for_descriptive_summary"]
    for keys, frame in grouped:
        universe, segment, policy, cost = keys
        event_count = len(frame)
        rows.append(
            {
                "universe_role": universe,
                "research_segment": segment,
                "policy_id": policy,
                "one_way_cost_bps": int(cost),
                "event_count": event_count,
                "descriptive_minimum_met": event_count >= minimum,
                "median_net_terminal_wealth_delta": frame["normalized_net_terminal_wealth_delta"].median(),
                "mean_net_terminal_wealth_delta": frame["normalized_net_terminal_wealth_delta"].mean(),
                "positive_net_value_rate": (frame["normalized_net_terminal_wealth_delta"] > 0).mean(),
                "median_terminal_share_delta": frame["terminal_share_delta"].median(),
                "completed_policy_rate": frame["completed_policy"].mean(),
            }
        )
    return pd.DataFrame(rows)


def _write_reproducible_gzip(frame: pd.DataFrame, path: Path) -> None:
    buffer = io.BytesIO()
    with gzip.GzipFile(filename="", mode="wb", fileobj=buffer, mtime=0) as stream:
        stream.write(frame.to_csv(index=False, lineterminator="\n").encode("utf-8"))
    path.write_bytes(buffer.getvalue())


def run() -> dict[str, Any]:
    contract = load_contract()
    ticker_ledger = build_ticker_ledger(contract)
    events = build_event_ledger(contract, ticker_ledger)
    segments = summarize_by_segment(contract, events)

    TICKER_LEDGER_PATH.parent.mkdir(parents=True, exist_ok=True)
    ticker_ledger.to_csv(TICKER_LEDGER_PATH, index=False, lineterminator="\n")
    _write_reproducible_gzip(events, EVENT_LEDGER_PATH)
    segments.to_csv(SEGMENT_PATH, index=False, lineterminator="\n")

    structure_counts = ticker_ledger["security_structure_class"].value_counts().sort_index().to_dict()
    event_segment_counts = events["research_segment"].value_counts().sort_index().to_dict()
    style_reason_counts = events["style_resolution_reason"].value_counts().sort_index().to_dict()
    report = {
        "report_version": CONTRACT_VERSION,
        "contract_sha256": _sha256(CONTRACT_PATH),
        "complete": True,
        "ticker_count": len(ticker_ledger),
        "event_count": len(events),
        "classified_event_count": int(events["research_segment"].notna().sum()),
        "security_structure_counts": structure_counts,
        "event_segment_counts": event_segment_counts,
        "style_resolution_reason_counts": style_reason_counts,
        "pit_style_resolved_events": int((events["economic_company_style"] != "UNRESOLVED").sum()),
        "profitable_large_cap_growth_events": int((events["economic_company_style"] == "PROFITABLE_LARGE_CAP_GROWTH").sum()),
        "leveraged_events_in_fixed_baseline": int((events["security_structure_class"] == "LEVERAGED_OR_INVERSE_ETP").sum()),
        "class_segment_summary_rows": len(segments),
        "class_results_selected_policy": None,
        "direction_evidence_admitted": False,
        "operational_action": "HOLD",
        "operational_action_ratio": 0.0,
        "survivorship_safe": False,
        "blind_holdout_access": False,
        "limitations": [
            "CURRENT_GICS_IS_NOT_POINT_IN_TIME_AND_IS_DIAGNOSTIC_ONLY",
            "POINT_IN_TIME_MARKET_CAP_IS_UNAVAILABLE",
            "SEC_PIT_STYLE_COVERAGE_IS_CONCENTRATED_IN_PRIMARY_UNIVERSE",
            "CURRENT_CONSTITUENT_UNIVERSE_IS_NOT_SURVIVORSHIP_SAFE",
        ],
        "artifacts": {
            "ticker_ledger": {"path": str(TICKER_LEDGER_PATH.relative_to(ROOT)), "sha256": _sha256(TICKER_LEDGER_PATH)},
            "event_ledger": {"path": str(EVENT_LEDGER_PATH.relative_to(ROOT)), "sha256": _sha256(EVENT_LEDGER_PATH)},
            "class_segment_summary": {"path": str(SEGMENT_PATH.relative_to(ROOT)), "sha256": _sha256(SEGMENT_PATH)},
        },
    }
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False, indent=2))
