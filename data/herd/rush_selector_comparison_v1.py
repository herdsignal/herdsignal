"""v6.1 Rush, 가격 Rush, 교집합을 동일한 126거래일 경로로 비교한다."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from herd.long_price_snapshot import verify_snapshot
from herd.rush_episode_study_v2 import classify_path, load_protocol as load_path_protocol
from herd.validation_universe import SECTOR_UNIVERSE


DEFAULT_PROTOCOL = Path(__file__).with_name("rush_selector_protocol_v1.json")


def load_protocol(path: Path = DEFAULT_PROTOCOL) -> dict:
    protocol = json.loads(path.read_text(encoding="utf-8"))
    if protocol.get("status") != "LOCKED_BEFORE_SELECTOR_COMPARISON":
        raise ValueError("selector protocol must be locked before comparison")
    if protocol["policy"].get("operational_action_authority") is not False:
        raise ValueError("selector comparison cannot authorize operational actions")
    return protocol


def collapse_v61_rush_events(events: pd.DataFrame, protocol: dict) -> pd.DataFrame:
    candidates = events[
        events["action"].eq("SELL") & events["regime"].str.endswith("RUSH")
    ].copy()
    candidates["signal_date"] = pd.to_datetime(candidates["signal_date"])
    candidates = candidates.sort_values(["ticker", "signal_date"])
    maximum_gap = pd.Timedelta(days=protocol["selectors"]["V61_RUSH"]["episode_collapse_calendar_days"])
    rows = []
    for ticker, group in candidates.groupby("ticker"):
        previous = None
        episode = 0
        for row in group.itertuples(index=False):
            signal = pd.Timestamp(row.signal_date)
            if previous is None or signal - previous > maximum_gap:
                episode += 1
                rows.append({
                    "ticker": ticker,
                    "episode_id": f"{ticker}-V61-{episode:03d}",
                    "signal_date": signal,
                    "last_observed_session": signal,
                    "source_regime": row.regime,
                })
            previous = signal
    return pd.DataFrame(rows)


def price_rush_events(paths: pd.DataFrame) -> pd.DataFrame:
    result = paths[["ticker", "episode_id", "signal_date", "last_observed_session"]].copy()
    result["signal_date"] = pd.to_datetime(result["signal_date"])
    result["last_observed_session"] = pd.to_datetime(result["last_observed_session"])
    return result


def intersect_events(v61: pd.DataFrame, price: pd.DataFrame, protocol: dict) -> pd.DataFrame:
    tolerance = pd.Timedelta(days=protocol["selectors"]["INTERSECTION"]["maximum_calendar_distance_days"])
    rows = []
    for ticker in sorted(set(v61["ticker"]).intersection(price["ticker"])):
        left = v61[v61["ticker"].eq(ticker)].sort_values("last_observed_session")
        right = price[price["ticker"].eq(ticker)].sort_values("last_observed_session")
        used: set[str] = set()
        episode = 0
        for vrow in left.itertuples(index=False):
            choices = right[~right["episode_id"].isin(used)].copy()
            if choices.empty:
                continue
            choices["distance"] = (choices["last_observed_session"] - vrow.last_observed_session).abs()
            match = choices.sort_values(["distance", "last_observed_session"]).iloc[0]
            if match["distance"] > tolerance:
                continue
            used.add(str(match["episode_id"]))
            episode += 1
            observed = max(pd.Timestamp(vrow.last_observed_session), pd.Timestamp(match["last_observed_session"]))
            rows.append({
                "ticker": ticker,
                "episode_id": f"{ticker}-I-{episode:03d}",
                "signal_date": observed,
                "last_observed_session": observed,
                "v61_episode_id": vrow.episode_id,
                "price_episode_id": match["episode_id"],
            })
    return pd.DataFrame(rows)


def apply_window(events: pd.DataFrame, protocol: dict) -> pd.DataFrame:
    start = pd.Timestamp(protocol["analysis_window"]["start_inclusive"])
    end = pd.Timestamp(protocol["analysis_window"]["signal_end_inclusive"])
    return events[events["last_observed_session"].between(start, end)].copy()


def classify_events(events: pd.DataFrame, frames: dict[str, pd.DataFrame]) -> pd.DataFrame:
    path_protocol = load_path_protocol()
    rows = []
    for event in events.to_dict("records"):
        frame = frames[event["ticker"]].sort_values("Date")
        close = frame.set_index("Date")["Adj Close"].astype(float)
        outcome = classify_path(close, pd.Series(event), path_protocol)
        if outcome is not None:
            rows.append(event | outcome)
    return pd.DataFrame(rows)


def _era(date: pd.Timestamp) -> str:
    year = pd.Timestamp(date).year
    return "2016-2019" if year <= 2019 else "2020-2022" if year <= 2022 else "2023-2026"


def summarize_selector(name: str, paths: pd.DataFrame, protocol: dict) -> dict:
    resolved = paths[paths["path_label"].ne("UNRESOLVED")].copy()
    opportunity = set(protocol["outcome"]["correction_opportunity_labels"])
    years = (
        pd.Timestamp(protocol["analysis_window"]["signal_end_inclusive"])
        - pd.Timestamp(protocol["analysis_window"]["start_inclusive"])
    ).days / 365.2425
    ticker_frequency = paths.groupby("ticker").size() / years if not paths.empty else pd.Series(dtype=float)
    correction_rate = float(resolved["path_label"].isin(opportunity).mean()) if not resolved.empty else None
    continuation_rate = float(resolved["path_label"].eq("CONTINUATION").mean()) if not resolved.empty else None
    median_frequency = float(ticker_frequency.median()) if not ticker_frequency.empty else 0.0
    gate = protocol["selection_gate"]
    eligible = len(resolved) >= gate["minimum_resolved_episodes"] and median_frequency <= gate["maximum_median_annual_episodes_per_ticker"]
    return {
        "selector": name,
        "episodes": int(len(paths)),
        "resolved_episodes": int(len(resolved)),
        "ticker_count": int(paths["ticker"].nunique()) if not paths.empty else 0,
        "median_annual_episodes_per_ticker": median_frequency,
        "correction_opportunity_rate": correction_rate,
        "continuation_rate": continuation_rate,
        "selection_utility": correction_rate - continuation_rate if correction_rate is not None else None,
        "label_counts": paths["path_label"].value_counts().to_dict() if not paths.empty else {},
        "eligible_for_discovery_selection": eligible,
    }


def choose_selector(summaries: list[dict], protocol: dict) -> dict:
    eligible = [row for row in summaries if row["eligible_for_discovery_selection"]]
    if not eligible:
        return {"status": "NO_SELECTOR_PASSED_GATE", "selected": None}
    ranked = sorted(
        eligible,
        key=lambda row: (-row["selection_utility"], row["median_annual_episodes_per_ticker"], row["selector"]),
    )
    return {
        "status": "LOCK_FOR_INDEPENDENT_OOS",
        "selected": ranked[0]["selector"],
        "selection_scope": protocol["selection_gate"]["selection_scope"],
    }


def run(snapshot: Path, v61_events_path: Path, price_paths_path: Path, protocol_path: Path = DEFAULT_PROTOCOL) -> tuple[pd.DataFrame, dict]:
    protocol = load_protocol(protocol_path)
    manifest = verify_snapshot(snapshot)
    v61_raw = pd.read_csv(v61_events_path)
    price_raw = pd.read_csv(price_paths_path)
    v61 = collapse_v61_rush_events(v61_raw, protocol)
    price = price_rush_events(price_raw)
    selectors = {
        "V61_RUSH": apply_window(v61, protocol),
        "PRICE_RUSH_V2": apply_window(price, protocol),
        "INTERSECTION": apply_window(intersect_events(v61, price, protocol), protocol),
    }
    tickers = sorted(set().union(*(set(frame["ticker"]) for frame in selectors.values())))
    frames = {
        ticker: pd.read_csv(snapshot / manifest["files"][ticker]["path"], parse_dates=["Date"])
        for ticker in tickers
    }
    parts, summaries = [], []
    sectors = {ticker: group for group, values in SECTOR_UNIVERSE.items() for ticker in values}
    for name, events in selectors.items():
        paths = classify_events(events, frames)
        if not paths.empty:
            paths["selector"] = name
            paths["sector"] = paths["ticker"].map(sectors)
            paths["era"] = paths["last_observed_session"].map(_era)
            parts.append(paths)
        summaries.append(summarize_selector(name, paths, protocol))
    all_paths = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()
    report = {
        "report_version": "HERD_RUSH_SELECTOR_COMPARISON_V1",
        "status": "DISCOVERY_SELECTOR_COMPARISON_NO_ACTION_AUTHORITY",
        "protocol": protocol,
        "snapshot_id": manifest["snapshot_id"],
        "snapshot_sha256": manifest["snapshot_sha256"],
        "summaries": summaries,
        "decision": choose_selector(summaries, protocol),
        "diagnostics": {
            "by_selector_and_era": all_paths.groupby(["selector", "era", "path_label"]).size().rename("episodes").reset_index().to_dict("records"),
            "by_selector_and_sector": all_paths.groupby(["selector", "sector", "path_label"]).size().rename("episodes").reset_index().to_dict("records"),
        },
    }
    return all_paths, report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--v61-events", type=Path, required=True)
    parser.add_argument("--price-paths", type=Path, required=True)
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--events-output", type=Path, required=True)
    parser.add_argument("--report-output", type=Path, required=True)
    args = parser.parse_args()
    paths, report = run(args.snapshot, args.v61_events, args.price_paths, args.protocol)
    args.events_output.parent.mkdir(parents=True, exist_ok=True)
    paths.to_csv(args.events_output, index=False)
    args.report_output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
