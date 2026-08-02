"""Evaluate the locked Rush margin-versus-cash hypothesis without retuning."""

from __future__ import annotations

import gzip
import hashlib
import io
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from herd.fixed_policy_economic_baselines_v1 import load_contract as load_baseline_contract
from herd.instrument_class_ledger_v1 import (
    latest_pit_feature,
    load_contract as load_instrument_contract,
)
from herd.rush_margin_cash_divergence_preregistration_v1 import (
    load_contract as load_preregistration,
)


ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = Path(__file__).with_suffix(".json")
ROWS_PATH = ROOT / "data/reports/rush_margin_cash_divergence_oos_v1.csv.gz"
REPORT_PATH = ROOT / "data/reports/rush_margin_cash_divergence_oos_v1.json"
CONTRACT_VERSION = "HERD_RUSH_MARGIN_CASH_DIVERGENCE_OOS_V1"
FEATURES = ("net_margin_yoy_change", "operating_cash_flow_yoy")
KEYS = ["ticker", "universe_role", "fold_id", "signal_date"]


class MarginCashOosError(RuntimeError):
    """Raised when an OOS boundary or a locked input changes."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _rooted(relative: str) -> Path:
    path = (ROOT / relative).resolve()
    if not path.is_relative_to(ROOT) or not path.is_file():
        raise MarginCashOosError(f"missing OOS input: {relative}")
    return path


def _input(contract: dict[str, Any], suffix: str) -> Path:
    matches = [item for item in contract["inputs"] if item["path"].endswith(suffix)]
    if len(matches) != 1:
        raise MarginCashOosError(f"ambiguous OOS input: {suffix}")
    return _rooted(matches[0]["path"])


def load_contract(path: Path = CONTRACT_PATH) -> dict[str, Any]:
    contract = json.loads(path.read_text(encoding="utf-8"))
    if (
        contract.get("contract_version") != CONTRACT_VERSION
        or contract.get("status") != "LOCKED_BEFORE_OOS_TARGET_ACCESS"
        or contract.get("hypothesis_id")
        != "RUSH_MARGIN_CASH_DIVERGENCE_RELATIVE_REBALANCE_V1"
    ):
        raise MarginCashOosError("OOS execution contract is not locked")
    if len(contract.get("inputs", [])) != 8:
        raise MarginCashOosError("OOS input set is incomplete")
    for item in contract["inputs"]:
        if _sha256(_rooted(item["path"])) != item.get("sha256"):
            raise MarginCashOosError(f"pinned OOS input changed: {item['path']}")

    training = contract.get("training_boundary", {})
    if (
        training.get("method") != "EXPANDING_WINDOW_LEAVE_ONE_TEST_TICKER_OUT"
        or training.get("same_ticker_history_excluded") is not True
        or training.get("training_target_must_mature_before_embargo") is not True
        or training.get("embargo_sessions") != 20
        or training.get("purge_is_locked_target_horizon_sessions") != 126
        or training.get("minimum_training_events") != 15
        or training.get("minimum_training_tickers") != 8
        or training.get("first_fold_without_prior_mature_events")
        != "FAIL_FOLD_CLOSED"
    ):
        raise MarginCashOosError("training boundary changed")

    score = contract.get("score_execution", {})
    if (
        score.get("features") != list(FEATURES)
        or score.get("winsorization_quantiles") != [0.01, 0.99]
        or score.get("scaler") != "MEDIAN_AND_IQR"
        or score.get("zero_iqr") != "FAIL_EVENT_CLOSED"
        or score.get("score")
        != "Z_NET_MARGIN_YOY_CHANGE_MINUS_Z_OPERATING_CASH_FLOW_YOY"
        or score.get("candidate_quantile") != 0.9
        or score.get("quantile_method") != "LINEAR"
        or score.get("test_values_clipped_to_training_WINSOR_BOUNDS") is not True
        or score.get("missing_values") != "NOT_ELIGIBLE_NO_IMPUTATION"
    ):
        raise MarginCashOosError("score execution changed")

    budget = contract.get("candidate_budget", {})
    if (
        budget.get("maximum_per_ticker_calendar_year") != 2
        or budget.get("cooldown_market_sessions") != 63
        or budget.get("selection_order")
        != "TICKER_THEN_OBSERVATION_SESSION_ASCENDING"
        or budget.get("later_conflict") != "REJECT"
    ):
        raise MarginCashOosError("candidate budget changed")

    evaluation = contract.get("evaluation", {})
    bootstrap = evaluation.get("ticker_block_bootstrap", {})
    if (
        evaluation.get("candidate_policy") != "TRIM_TO_SPY_HORIZON"
        or evaluation.get("costs_bps") != [10, 25, 50]
        or evaluation.get("same_candidate_keys_for_all_locked_baselines") is not True
        or evaluation.get("directional_fold")
        != "FOLD_HAS_CANDIDATE_AND_MEDIAN_10BPS_DELTA_ABOVE_ZERO"
        or bootstrap.get("statistic")
        != "EVENT_MEDIAN_NORMALIZED_NET_TERMINAL_WEALTH_DELTA"
        or bootstrap.get("one_sided_p_value")
        != "ADD_ONE_FRACTION_OF_BOOTSTRAP_STATISTICS_LESS_THAN_OR_EQUAL_TO_ZERO"
        or bootstrap.get("samples") != 10_000
        or bootstrap.get("seed") != 20_260_802
        or evaluation.get("gate_source")
        != "data/herd/rush_margin_cash_divergence_preregistration_v1.json"
        or evaluation.get("all_gates_required") is not True
    ):
        raise MarginCashOosError("economic evaluation changed")
    firewall = contract.get("firewall", {})
    if (
        firewall.get("preholdout_only") is not True
        or firewall.get("prospective_confirmation_required") is not True
        or firewall.get("operational_action") != "HOLD"
        or firewall.get("operational_action_ratio") != 0.0
        or firewall.get("survivorship_safe") is not False
        or firewall.get("blind_holdout_access") is not False
    ):
        raise MarginCashOosError("OOS firewall weakened")

    # Validate the indirect immutable lineage before reading any target values.
    load_preregistration(_input(contract, "rush_margin_cash_divergence_preregistration_v1.json"))
    load_instrument_contract(_input(contract, "instrument_class_ledger_v1.json"))
    load_baseline_contract()
    return contract


def _market_sessions(contract: dict[str, Any]) -> pd.DatetimeIndex:
    manifest_path = _input(contract, "manifest.json")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    receipt = manifest.get("files", {}).get("SPY")
    if receipt is None:
        raise MarginCashOosError("primary snapshot has no SPY receipt")
    price_path = (manifest_path.parent / receipt["path"]).resolve()
    if (
        not price_path.is_relative_to(manifest_path.parent.resolve())
        or not price_path.is_file()
        or _sha256(price_path) != receipt.get("sha256")
    ):
        raise MarginCashOosError("SPY session snapshot changed")
    opener = gzip.open if price_path.suffix == ".gz" else open
    with opener(price_path, "rt", encoding="utf-8") as stream:
        dates = pd.read_csv(stream, usecols=["Date"], parse_dates=["Date"])["Date"]
    sessions = pd.DatetimeIndex(dates).tz_localize(None).normalize().sort_values()
    if sessions.has_duplicates:
        raise MarginCashOosError("SPY session calendar contains duplicates")
    return sessions


def _eligible_events(contract: dict[str, Any]) -> pd.DataFrame:
    events = pd.read_csv(
        _input(contract, "instrument_class_event_ledger_v1.csv.gz"),
        parse_dates=["signal_date", "observation_session"],
    )
    events = events.loc[
        (events["universe_role"] == "PRIMARY")
        & (events["security_structure_class"] == "OPERATING_COMPANY_EQUITY")
    ].copy()
    features = pd.read_csv(
        _input(contract, "business_state_features_v2.csv"),
        parse_dates=["month_end", "latest_fact_accepted_at"],
    )
    features["ticker"] = features["ticker"].astype(str).str.upper()
    feature_rows: list[dict[str, Any]] = []
    for event in events.itertuples(index=False):
        feature = latest_pit_feature(features, event.ticker, event.observation_session)
        if feature is None or any(pd.isna(feature[name]) for name in FEATURES):
            continue
        feature_rows.append(
            {
                **{key: getattr(event, key) for key in KEYS},
                "observation_session": event.observation_session,
                "feature_month_end": feature["month_end"],
                "feature_accepted_at": feature["latest_fact_accepted_at"],
                **{name: float(feature[name]) for name in FEATURES},
            }
        )
    eligible = pd.DataFrame(feature_rows)
    if eligible.empty or eligible.duplicated(KEYS).any():
        raise MarginCashOosError("eligible event population is empty or duplicated")

    baseline = pd.read_csv(
        _input(contract, "fixed_policy_economic_baselines_v1.csv.gz"),
        parse_dates=["signal_date", "terminal_date"],
    )
    maturity = baseline.loc[
        (baseline["policy_id"] == "MATCHED_HOLD")
        & (baseline["one_way_cost_bps"] == 10),
        KEYS + ["terminal_date"],
    ]
    if maturity.duplicated(KEYS).any():
        raise MarginCashOosError("matched HOLD maturity rows are duplicated")
    eligible = eligible.merge(maturity, on=KEYS, how="left", validate="one_to_one")
    if eligible["terminal_date"].isna().any():
        raise MarginCashOosError("eligible events are missing locked terminal dates")
    return eligible.sort_values(["observation_session", "ticker"]).reset_index(drop=True)


def _embargo_start(
    sessions: pd.DatetimeIndex, test_start: pd.Timestamp, embargo_sessions: int
) -> pd.Timestamp:
    prior = sessions[sessions < test_start]
    if len(prior) < embargo_sessions:
        raise MarginCashOosError("insufficient market sessions for embargo")
    return pd.Timestamp(prior[-embargo_sessions])


def _score_one(
    train: pd.DataFrame, test: pd.Series, contract: dict[str, Any]
) -> tuple[float, float, dict[str, float]]:
    score_contract = contract["score_execution"]
    q_low, q_high = score_contract["winsorization_quantiles"]
    transformed: dict[str, pd.Series] = {}
    test_z: dict[str, float] = {}
    parameters: dict[str, float] = {}
    for name in FEATURES:
        low = float(train[name].quantile(q_low, interpolation="linear"))
        high = float(train[name].quantile(q_high, interpolation="linear"))
        clipped = train[name].clip(lower=low, upper=high)
        median = float(clipped.median())
        iqr = float(clipped.quantile(0.75) - clipped.quantile(0.25))
        if not np.isfinite(iqr) or iqr <= 0:
            raise MarginCashOosError(f"zero training IQR for {name}")
        transformed[name] = (clipped - median) / iqr
        test_value = float(np.clip(float(test[name]), low, high))
        test_z[name] = (test_value - median) / iqr
        parameters.update(
            {
                f"{name}_winsor_low": low,
                f"{name}_winsor_high": high,
                f"{name}_median": median,
                f"{name}_iqr": iqr,
            }
        )
    train_score = transformed[FEATURES[0]] - transformed[FEATURES[1]]
    cutoff = float(
        train_score.quantile(
            score_contract["candidate_quantile"], interpolation="linear"
        )
    )
    return test_z[FEATURES[0]] - test_z[FEATURES[1]], cutoff, parameters


def build_oos_scores(
    contract: dict[str, Any], events: pd.DataFrame, sessions: pd.DatetimeIndex
) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    folds = pd.read_csv(
        _input(contract, "price_timing_6m.csv"), parse_dates=["test_start", "test_end"]
    )
    training_contract = contract["training_boundary"]
    rows: list[dict[str, Any]] = []
    fold_audit: list[dict[str, Any]] = []
    for fold in folds.itertuples(index=False):
        test = events.loc[events["fold_id"] == fold.fold_id]
        embargo_start = _embargo_start(
            sessions, fold.test_start, training_contract["embargo_sessions"]
        )
        base_train = events.loc[events["terminal_date"] < embargo_start]
        fold_failures = 0
        for _, event in test.iterrows():
            train = base_train.loc[base_train["ticker"] != event["ticker"]]
            if (
                len(train) < training_contract["minimum_training_events"]
                or train["ticker"].nunique()
                < training_contract["minimum_training_tickers"]
            ):
                fold_failures += 1
                continue
            try:
                score, cutoff, parameters = _score_one(train, event, contract)
            except MarginCashOosError:
                fold_failures += 1
                continue
            rows.append(
                {
                    **{key: event[key] for key in KEYS},
                    "observation_session": event["observation_session"],
                    "terminal_date": event["terminal_date"],
                    "feature_month_end": event["feature_month_end"],
                    "feature_accepted_at": event["feature_accepted_at"],
                    **{name: event[name] for name in FEATURES},
                    "training_events": int(len(train)),
                    "training_tickers": int(train["ticker"].nunique()),
                    "embargo_start": embargo_start,
                    "score": score,
                    "candidate_cutoff": cutoff,
                    "raw_candidate": bool(score >= cutoff),
                    **parameters,
                }
            )
        fold_audit.append(
            {
                "fold_id": fold.fold_id,
                "feature_ready_events": int(len(test)),
                "base_training_events": int(len(base_train)),
                "scored_events": int(len(test) - fold_failures),
                "failed_closed_events": int(fold_failures),
                "embargo_start": embargo_start.date().isoformat(),
            }
        )
    return pd.DataFrame(rows), fold_audit


def _apply_candidate_budget(
    scores: pd.DataFrame, sessions: pd.DatetimeIndex, contract: dict[str, Any]
) -> pd.DataFrame:
    result = scores.copy()
    result["candidate"] = False
    result["budget_rejection_reason"] = ""
    session_positions = {date: position for position, date in enumerate(sessions)}
    budget = contract["candidate_budget"]
    for ticker, frame in result.loc[result["raw_candidate"]].groupby("ticker"):
        accepted_positions: list[int] = []
        year_counts: dict[int, int] = {}
        for index, event in frame.sort_values("observation_session").iterrows():
            session = pd.Timestamp(event["observation_session"])
            position = session_positions.get(session)
            if position is None:
                raise MarginCashOosError(f"event is not a market session: {ticker} {session}")
            year = session.year
            if year_counts.get(year, 0) >= budget["maximum_per_ticker_calendar_year"]:
                result.at[index, "budget_rejection_reason"] = "ANNUAL_BUDGET"
                continue
            if accepted_positions and position - accepted_positions[-1] < budget["cooldown_market_sessions"]:
                result.at[index, "budget_rejection_reason"] = "COOLDOWN"
                continue
            result.at[index, "candidate"] = True
            accepted_positions.append(position)
            year_counts[year] = year_counts.get(year, 0) + 1
    return result


def _candidate_outcomes(
    contract: dict[str, Any], scores: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame]:
    baseline = pd.read_csv(
        _input(contract, "fixed_policy_economic_baselines_v1.csv.gz"),
        parse_dates=["signal_date"],
    )
    candidates = scores.loc[scores["candidate"], KEYS].copy()
    outcomes = baseline.merge(candidates, on=KEYS, how="inner", validate="many_to_one")
    expected = len(candidates) * 5 * 3
    if len(outcomes) != expected:
        raise MarginCashOosError(
            f"candidate baseline comparison is incomplete: {len(outcomes)} != {expected}"
        )
    target = outcomes.loc[
        outcomes["policy_id"] == contract["evaluation"]["candidate_policy"],
        KEYS
        + [
            "one_way_cost_bps",
            "normalized_net_terminal_wealth_delta",
            "missed_upside_cost",
            "downside_avoided",
            "average_equity_exposure",
        ],
    ]
    wide = target.pivot(index=KEYS, columns="one_way_cost_bps")
    wide.columns = [f"{name}_{int(cost)}bps" for name, cost in wide.columns]
    wide = wide.reset_index()
    scored = scores.merge(wide, on=KEYS, how="left", validate="one_to_one")
    return scored, outcomes


def _baseline_summaries(outcomes: pd.DataFrame) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for (policy, cost), frame in outcomes.groupby(["policy_id", "one_way_cost_bps"]):
        delta = frame["normalized_net_terminal_wealth_delta"].astype(float)
        rows.append(
            {
                "policy_id": str(policy),
                "one_way_cost_bps": int(cost),
                "candidates": int(len(frame)),
                "median_net_terminal_wealth_delta": float(delta.median()),
                "mean_net_terminal_wealth_delta": float(delta.mean()),
                "positive_net_value_rate": float((delta > 0).mean()),
                "missed_upside_cost_p95": float(
                    np.quantile(frame["missed_upside_cost"].astype(float), 0.95)
                ),
            }
        )
    return rows


def _ticker_block_bootstrap(
    candidates: pd.DataFrame, contract: dict[str, Any]
) -> dict[str, Any]:
    values = {
        ticker: frame["normalized_net_terminal_wealth_delta_10bps"].to_numpy(float)
        for ticker, frame in candidates.groupby("ticker")
    }
    tickers = sorted(values)
    bootstrap = contract["evaluation"]["ticker_block_bootstrap"]
    rng = np.random.default_rng(bootstrap["seed"])
    statistics = np.empty(bootstrap["samples"], dtype=float)
    for index in range(bootstrap["samples"]):
        sampled = rng.choice(tickers, size=len(tickers), replace=True)
        statistics[index] = float(
            np.median(np.concatenate([values[ticker] for ticker in sampled]))
        )
    nonpositive = int((statistics <= 0).sum())
    return {
        "unit": "TICKER",
        "samples": int(bootstrap["samples"]),
        "seed": int(bootstrap["seed"]),
        "one_sided_p_value": float((nonpositive + 1) / (len(statistics) + 1)),
        "median_interval_95": [
            float(np.quantile(statistics, 0.025)),
            float(np.quantile(statistics, 0.975)),
        ],
    }


def _write_reproducible_gzip(frame: pd.DataFrame, path: Path) -> None:
    buffer = io.BytesIO()
    with gzip.GzipFile(filename="", mode="wb", fileobj=buffer, mtime=0) as stream:
        stream.write(frame.to_csv(index=False, lineterminator="\n").encode("utf-8"))
    path.write_bytes(buffer.getvalue())


def run(
    contract_path: Path = CONTRACT_PATH,
    rows_path: Path = ROWS_PATH,
    report_path: Path = REPORT_PATH,
) -> dict[str, Any]:
    contract = load_contract(contract_path)
    preregistration = load_preregistration()
    events = _eligible_events(contract)
    sessions = _market_sessions(contract)
    scores, fold_audit = build_oos_scores(contract, events, sessions)
    scores = _apply_candidate_budget(scores, sessions, contract)
    scored, all_baseline_outcomes = _candidate_outcomes(contract, scores)
    candidates = scored.loc[scored["candidate"]].copy()
    if candidates.empty:
        raise MarginCashOosError("locked score selected no candidates")

    bootstrap = _ticker_block_bootstrap(candidates, contract)
    base_delta = candidates["normalized_net_terminal_wealth_delta_10bps"].astype(float)
    stress_delta = candidates["normalized_net_terminal_wealth_delta_50bps"].astype(float)
    fold_medians = (
        candidates.groupby("fold_id")["normalized_net_terminal_wealth_delta_10bps"]
        .median()
        .sort_index()
    )
    gates = preregistration["target_and_gates"]
    gate_results = {
        "minimum_candidates": len(candidates) >= gates["minimum_candidates"],
        "minimum_candidate_tickers": candidates["ticker"].nunique()
        >= gates["minimum_candidate_tickers"],
        "minimum_directional_folds": int((fold_medians > 0).sum())
        >= gates["minimum_directional_folds"],
        "median_net_terminal_wealth_delta": float(base_delta.median())
        > gates["median_net_terminal_wealth_delta_must_exceed"],
        "minimum_positive_net_value_rate": float((base_delta > 0).mean())
        >= gates["minimum_positive_net_value_rate"],
        "maximum_one_sided_ticker_block_bootstrap_p_value": bootstrap[
            "one_sided_p_value"
        ]
        <= gates["maximum_one_sided_ticker_block_bootstrap_p_value"],
        "stress_50bps_median": float(stress_delta.median())
        >= gates["stress_50bps_median_must_not_be_below"],
        "maximum_95pct_missed_upside_cost": float(
            np.quantile(candidates["missed_upside_cost_10bps"].astype(float), 0.95)
        )
        <= gates["maximum_95pct_missed_upside_cost"],
        "all_locked_fixed_baselines_compared": len(all_baseline_outcomes)
        == len(candidates) * 5 * 3,
    }
    passed = all(gate_results.values())

    rows_path.parent.mkdir(parents=True, exist_ok=True)
    _write_reproducible_gzip(scored, rows_path)
    report = {
        "report_version": CONTRACT_VERSION,
        "contract_sha256": _sha256(contract_path),
        "hypothesis_id": contract["hypothesis_id"],
        "status": (
            "PREHOLDOUT_PASSED_PROSPECTIVE_CONFIRMATION_REQUIRED"
            if passed
            else "PREHOLDOUT_REJECTED_NO_ACTION_AUTHORITY"
        ),
        "feature_ready_events": int(len(events)),
        "scored_events": int(len(scored)),
        "raw_candidates": int(scored["raw_candidate"].sum()),
        "candidates": int(len(candidates)),
        "candidate_tickers": int(candidates["ticker"].nunique()),
        "candidate_folds": int(candidates["fold_id"].nunique()),
        "directional_folds": int((fold_medians > 0).sum()),
        "fold_median_10bps_delta": {
            key: float(value) for key, value in fold_medians.items()
        },
        "median_10bps_net_terminal_wealth_delta": float(base_delta.median()),
        "mean_10bps_net_terminal_wealth_delta": float(base_delta.mean()),
        "positive_10bps_net_value_rate": float((base_delta > 0).mean()),
        "median_50bps_net_terminal_wealth_delta": float(stress_delta.median()),
        "missed_upside_cost_10bps_p95": float(
            np.quantile(candidates["missed_upside_cost_10bps"].astype(float), 0.95)
        ),
        "ticker_block_bootstrap": bootstrap,
        "fold_audit": fold_audit,
        "gate_results": gate_results,
        "all_adoption_gates_passed": passed,
        "locked_baseline_summaries": _baseline_summaries(all_baseline_outcomes),
        "rows": {
            "path": str(rows_path.relative_to(ROOT)),
            "sha256": _sha256(rows_path),
        },
        "oos_target_accessed": True,
        "same_oos_retuned": False,
        "direction_evidence_admitted": False,
        "policy_promoted": False,
        "prospective_confirmation_required": True,
        "operational_action": "HOLD",
        "operational_action_ratio": 0.0,
        "survivorship_safe": False,
        "blind_holdout_access": False,
        "next_stage": (
            "START_PROSPECTIVE_SHADOW_CONFIRMATION_WITHOUT_USER_ACTION"
            if passed
            else "REJECT_HYPOTHESIS_AND_RETURN_TO_DISTINCT_ECONOMIC_INFORMATION"
        ),
    }
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return report


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False, indent=2))
