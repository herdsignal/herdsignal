"""비정기 내부자 P 매수 지지가 Rush의 큰 조정 위험을 낮추는지 단일 OOS 검증한다."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import fisher_exact, rankdata

from herd.sec_form4_bulk_v2 import sha256, verify_normalized


ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = Path(__file__).with_name(
    "sec_form4_insider_purchase_support_v1.json"
)


class InsiderPurchaseOosError(RuntimeError):
    pass


def load_protocol(path: Path = PROTOCOL) -> dict:
    protocol = json.loads(path.read_text(encoding="utf-8"))
    expected = "LOCKED_CONDITIONAL_ON_CENSUS_GATE_BEFORE_FEATURE_OUTCOME_JOIN"
    if protocol.get("status") != expected:
        raise InsiderPurchaseOosError("insider hypothesis is not preregistered")
    firewall = protocol.get("research_firewall", {})
    if (
        firewall.get("single_hypothesis_only") is not True
        or firewall.get("no_parameter_search") is not True
        or firewall.get("operational_action_authority") is not False
    ):
        raise InsiderPurchaseOosError("insider hypothesis firewall is incomplete")
    return protocol


def _bool(value: object) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes"}


def _positive_number(value: object) -> bool:
    try:
        return float(str(value).strip()) > 0
    except (TypeError, ValueError):
        return False


def _explicitly_excluded(text: object, phrases: list[str]) -> bool:
    normalized = re.sub(r"\s+", " ", str(text or "")).casefold()
    return any(phrase.casefold() in normalized for phrase in phrases)


def _eligible_owner_relationship(value: object, allowed: list[str]) -> bool:
    normalized = str(value or "").casefold()
    return any(role.casefold() in normalized for role in allowed)


def build_owner_purchase_events(
    snapshot: Path,
    protocol: dict,
) -> pd.DataFrame:
    verify_normalized(snapshot)
    normalized = snapshot / "normalized"
    submissions = pd.read_csv(
        normalized / "submissions.csv", dtype=str, keep_default_na=False
    )
    owners = pd.read_csv(
        normalized / "reporting_owners.csv", dtype=str, keep_default_na=False
    )
    transactions = pd.read_csv(
        normalized / "transactions.csv", dtype=str, keep_default_na=False
    )
    definition = protocol["feature_definition"]
    selected_submissions = submissions[
        submissions["researchSplit"].eq("INDEPENDENT_CURRENT_CONSTITUENT")
        & submissions["documentType"].eq(definition["document_type"])
        & ~submissions["isAmendment"].map(_bool)
        & ~submissions["aff10b5one"].map(_bool)
    ].copy()
    selected_transactions = transactions[
        transactions["accessionNumber"].isin(
            selected_submissions["accessionNumber"]
        )
        & transactions["transactionTable"].eq(
            definition["transaction_table"]
        )
        & transactions["transactionCode"].eq(
            definition["transaction_code"]
        )
        & transactions["directOrIndirectOwnership"].eq("D")
        & transactions["transactionShares"].map(_positive_number)
        & transactions["transactionPricePerShare"].map(_positive_number)
        & ~transactions["referencedFootnoteText"].map(
            lambda text: _explicitly_excluded(
                text, definition["explicit_footnote_exclusions"]
            )
        )
    ].copy()
    selected_transactions = selected_transactions.merge(
        selected_submissions[
            ["accessionNumber", "issuerCik", "filingDate"]
        ],
        on="accessionNumber",
        how="inner",
        validate="many_to_one",
    )
    eligible_owners = owners[
        owners["accessionNumber"].isin(
            selected_transactions["accessionNumber"]
        )
        & owners["relationship"].map(
            lambda value: _eligible_owner_relationship(
                value, definition["eligible_owner_relationships"]
            )
        )
    ].copy()
    events = selected_transactions.merge(
        eligible_owners[
            [
                "accessionNumber",
                "reportingOwnerCik",
                "reportingOwnerName",
                "relationship",
                "officerTitle",
            ]
        ],
        on="accessionNumber",
        how="inner",
        validate="many_to_many",
    )
    if events.empty:
        return pd.DataFrame(columns=[
            "ownerEventId",
            "issuerCik",
            "reportingOwnerCik",
            "filingDate",
            "routineStatus",
        ])
    events["filingDate"] = pd.to_datetime(events["filingDate"])
    events = events.sort_values(
        ["issuerCik", "reportingOwnerCik", "filingDate", "accessionNumber"]
    )
    events = events.drop_duplicates(
        ["issuerCik", "reportingOwnerCik", "accessionNumber"]
    ).copy()
    history: dict[tuple[str, str], set[tuple[int, int]]] = defaultdict(set)
    first_year: dict[tuple[str, str], int] = {}
    statuses = []
    for row in events.itertuples(index=False):
        key = (row.issuerCik, row.reportingOwnerCik)
        year, month = row.filingDate.year, row.filingDate.month
        first_year.setdefault(key, year)
        prior = history[key]
        if year - first_year[key] < 3:
            status = "UNKNOWN_WARMUP"
        elif all((year - offset, month) in prior for offset in (1, 2, 3)):
            status = "ROUTINE"
        else:
            status = "NON_ROUTINE_CANDIDATE"
        statuses.append(status)
        prior.add((year, month))
    events["routineStatus"] = statuses
    events["ownerEventId"] = events.apply(
        lambda row: hashlib.sha256(
            (
                f"{row.issuerCik}|{row.reportingOwnerCik}|"
                f"{row.accessionNumber}"
            ).encode()
        ).hexdigest(),
        axis=1,
    )
    events["filingDate"] = events["filingDate"].dt.date.astype(str)
    return events.reset_index(drop=True)


def _assign_fold(signal_date: pd.Timestamp, protocol: dict) -> str | None:
    for fold in protocol["oos_folds"]:
        if pd.Timestamp(fold["start"]) <= signal_date <= pd.Timestamp(fold["end"]):
            return fold["id"]
    return None


def attach_episode_feature(
    episodes: pd.DataFrame,
    owner_events: pd.DataFrame,
    universe: pd.DataFrame,
    protocol: dict,
) -> pd.DataFrame:
    if "issuer_cik" in universe:
        ticker_to_cik = {
            row.ticker: f"{int(row.issuer_cik):010d}"
            for row in universe.itertuples(index=False)
        }
    else:
        ticker_to_cik = {
            row.ticker: f"{int(row.cik):010d}"
            for row in universe.itertuples(index=False)
            if str(row.eligible).lower() == "true"
        }
    panel = episodes.copy()
    panel = panel[
        panel["path_label"].isin(
            protocol["population"]["adverse_path_labels"]
            + protocol["population"]["non_adverse_path_labels"]
        )
        & panel["ticker"].isin(ticker_to_cik)
    ].copy()
    panel["signal_date"] = pd.to_datetime(panel["signal_date"])
    panel["issuerCik"] = panel["ticker"].map(ticker_to_cik)
    if panel["issuerCik"].isna().any():
        missing = sorted(panel.loc[panel["issuerCik"].isna(), "ticker"].unique())
        raise InsiderPurchaseOosError(
            f"episode tickers missing CIK mapping: {missing[:10]}"
        )
    events_by_issuer = {
        cik: frame.assign(filingDate=pd.to_datetime(frame["filingDate"]))
        for cik, frame in owner_events[
            owner_events["routineStatus"].eq("NON_ROUTINE_CANDIDATE")
        ].groupby("issuerCik", sort=False)
    }
    lookback = int(protocol["feature_definition"]["lookback_calendar_days"])
    features = []
    for row in panel.itertuples(index=False):
        candidates = events_by_issuer.get(row.issuerCik, pd.DataFrame())
        if candidates.empty:
            matched = candidates
        else:
            lower = row.signal_date - pd.Timedelta(days=lookback)
            matched = candidates[
                candidates["filingDate"].ge(lower)
                & candidates["filingDate"].lt(row.signal_date)
            ]
        features.append({
            "purchaseSupport90d": int(not matched.empty),
            "purchaseSupportOwnerCount90d": (
                int(matched["reportingOwnerCik"].nunique())
                if not matched.empty else 0
            ),
            "purchaseSupportEventCount90d": len(matched),
            "latestPurchaseSupportFilingDate": (
                matched["filingDate"].max().date().isoformat()
                if not matched.empty else ""
            ),
        })
    feature_frame = pd.DataFrame(features, index=panel.index)
    for column in feature_frame:
        panel[column] = feature_frame[column]
    panel["adversePath"] = panel["path_label"].isin(
        protocol["population"]["adverse_path_labels"]
    ).astype(int)
    panel["foldId"] = panel["signal_date"].map(
        lambda value: _assign_fold(value, protocol)
    )
    panel = panel[panel["foldId"].notna()].copy()
    panel["signal_date"] = panel["signal_date"].dt.date.astype(str)
    return panel.reset_index(drop=True)


def _rate_difference(frame: pd.DataFrame) -> tuple[float, float, float]:
    positive = frame[frame["purchaseSupport90d"].eq(1)]["adversePath"]
    negative = frame[frame["purchaseSupport90d"].eq(0)]["adversePath"]
    if positive.empty or negative.empty:
        return math.nan, math.nan, math.nan
    positive_rate = float(positive.mean())
    negative_rate = float(negative.mean())
    relative_risk = (
        positive_rate / negative_rate if negative_rate > 0 else math.inf
    )
    return positive_rate - negative_rate, relative_risk, positive_rate


def _binary_auc(target: pd.Series, score: pd.Series) -> float | None:
    labels = target.astype(int).to_numpy()
    values = score.astype(float).to_numpy()
    positives = int(labels.sum())
    negatives = len(labels) - positives
    if not positives or not negatives:
        return None
    ranks = rankdata(values, method="average")
    positive_rank_sum = float(ranks[labels == 1].sum())
    return (
        positive_rank_sum - positives * (positives + 1) / 2
    ) / (positives * negatives)


def _cluster_bootstrap(
    panel: pd.DataFrame,
    *,
    iterations: int = 2000,
    seed: int = 20260723,
) -> dict:
    tickers = sorted(panel["ticker"].unique())
    by_ticker = {
        ticker: panel[panel["ticker"].eq(ticker)]
        for ticker in tickers
    }
    generator = np.random.default_rng(seed)
    differences = []
    for _ in range(iterations):
        sampled = generator.choice(tickers, size=len(tickers), replace=True)
        frame = pd.concat(
            [by_ticker[ticker] for ticker in sampled],
            ignore_index=True,
        )
        difference, _, _ = _rate_difference(frame)
        if not math.isnan(difference):
            differences.append(difference)
    if not differences:
        return {
            "iterations": iterations,
            "valid_iterations": 0,
            "risk_difference_ci_95": [None, None],
        }
    return {
        "iterations": iterations,
        "valid_iterations": len(differences),
        "risk_difference_ci_95": [
            float(np.quantile(differences, 0.025)),
            float(np.quantile(differences, 0.975)),
        ],
    }


def evaluate_panel(panel: pd.DataFrame, protocol: dict) -> tuple[pd.DataFrame, dict]:
    fold_rows = []
    for fold_id, frame in panel.groupby("foldId", sort=False):
        difference, relative_risk, positive_rate = _rate_difference(frame)
        negative = frame[frame["purchaseSupport90d"].eq(0)]
        fold_rows.append({
            "fold_id": fold_id,
            "episodes": len(frame),
            "feature_positive_episodes": int(
                frame["purchaseSupport90d"].sum()
            ),
            "feature_positive_adverse_rate": positive_rate,
            "feature_negative_adverse_rate": (
                float(negative["adversePath"].mean()) if len(negative) else None
            ),
            "adverse_risk_difference": difference,
            "relative_risk": relative_risk,
            "direction_matches_hypothesis": (
                bool(difference < 0) if not math.isnan(difference) else False
            ),
        })
    folds = pd.DataFrame(fold_rows)
    difference, relative_risk, positive_rate = _rate_difference(panel)
    negative_rate = float(
        panel.loc[panel["purchaseSupport90d"].eq(0), "adversePath"].mean()
    )
    table = [
        [
            int(
                (
                    panel["purchaseSupport90d"].eq(1)
                    & panel["adversePath"].eq(1)
                ).sum()
            ),
            int(
                (
                    panel["purchaseSupport90d"].eq(1)
                    & panel["adversePath"].eq(0)
                ).sum()
            ),
        ],
        [
            int(
                (
                    panel["purchaseSupport90d"].eq(0)
                    & panel["adversePath"].eq(1)
                ).sum()
            ),
            int(
                (
                    panel["purchaseSupport90d"].eq(0)
                    & panel["adversePath"].eq(0)
                ).sum()
            ),
        ],
    ]
    odds_ratio, fisher_p = fisher_exact(table, alternative="two-sided")
    auc = _binary_auc(
        panel["adversePath"],
        1 - panel["purchaseSupport90d"],
    )
    bootstrap = _cluster_bootstrap(panel)
    thresholds = protocol["adoption_gate"]
    feature_positive = panel[panel["purchaseSupport90d"].eq(1)]
    folds_with_ten = int(
        folds["feature_positive_episodes"].ge(10).sum()
    )
    direction_folds = int(folds["direction_matches_hypothesis"].sum())
    upper = bootstrap["risk_difference_ci_95"][1]
    checks = {
        "minimum_resolved_episodes": (
            len(panel) >= int(thresholds["minimum_resolved_episodes"])
        ),
        "minimum_feature_positive_episodes": (
            len(feature_positive)
            >= int(thresholds["minimum_feature_positive_episodes"])
        ),
        "minimum_feature_positive_tickers": (
            feature_positive["ticker"].nunique()
            >= int(thresholds["minimum_feature_positive_tickers"])
        ),
        "minimum_folds_with_at_least_10_positive_episodes": (
            folds_with_ten
            >= int(
                thresholds[
                    "minimum_folds_with_at_least_10_positive_episodes"
                ]
            )
        ),
        "minimum_direction_consistent_folds": (
            direction_folds
            >= int(thresholds["minimum_direction_consistent_folds"])
        ),
        "maximum_pooled_adverse_risk_difference": (
            difference
            <= float(thresholds["maximum_pooled_adverse_risk_difference"])
        ),
        "maximum_pooled_relative_risk": (
            relative_risk
            <= float(thresholds["maximum_pooled_relative_risk"])
        ),
        "bootstrap_upper_risk_difference_below_zero": (
            upper is not None
            and upper
            < float(
                thresholds[
                    "maximum_ticker_cluster_bootstrap_95_upper_risk_difference"
                ]
            )
        ),
    }
    return folds, {
        "checks": checks,
        "passed": all(checks.values()),
        "episodes": len(panel),
        "tickers": int(panel["ticker"].nunique()),
        "adverse_episodes": int(panel["adversePath"].sum()),
        "feature_positive_episodes": len(feature_positive),
        "feature_positive_tickers": int(
            feature_positive["ticker"].nunique()
        ),
        "feature_positive_adverse_rate": positive_rate,
        "feature_negative_adverse_rate": negative_rate,
        "pooled_adverse_risk_difference": difference,
        "pooled_relative_risk": relative_risk,
        "odds_ratio": float(odds_ratio),
        "fisher_two_sided_p_value": float(fisher_p),
        "binary_feature_auc": auc,
        "folds_with_at_least_10_positive_episodes": folds_with_ten,
        "direction_consistent_folds": direction_folds,
        "ticker_cluster_bootstrap": bootstrap,
    }


def run(
    snapshot: Path,
    *,
    census_gate: Path,
    episodes_path: Path,
    universe_path: Path,
    output_events: Path,
    output_panel: Path,
    output_folds: Path,
    output_report: Path,
    protocol_path: Path = PROTOCOL,
) -> dict:
    protocol = load_protocol(protocol_path)
    gate = json.loads(census_gate.read_text(encoding="utf-8"))
    if (
        gate.get("passed") is not True
        or gate.get("single_hypothesis_preregistration_allowed") is not True
    ):
        raise InsiderPurchaseOosError(
            "Form 4 census gate must pass before outcome join"
        )
    owner_events = build_owner_purchase_events(snapshot, protocol)
    episodes = pd.read_csv(episodes_path)
    universe = pd.read_csv(
        snapshot / "normalized/independent_universe.csv",
        dtype={"issuer_cik": str},
    )
    panel = attach_episode_feature(episodes, owner_events, universe, protocol)
    folds, metrics = evaluate_panel(panel, protocol)
    output_events.parent.mkdir(parents=True, exist_ok=True)
    owner_events.to_csv(output_events, index=False)
    panel.to_csv(output_panel, index=False)
    folds.to_csv(output_folds, index=False)
    passed = metrics["passed"]
    report = {
        "report_version": "HERD_SEC_FORM4_INSIDER_PURCHASE_OOS_V1",
        "status": (
            "ADMIT_PROTECTIVE_PURCHASE_SUPPORT_EVIDENCE"
            if passed else "REJECT_INSIDER_PURCHASE_SUPPORT_HYPOTHESIS"
        ),
        "hypothesis": (
            "Recent non-routine insider P purchase support lowers adverse "
            "Rush path risk."
        ),
        "result": metrics,
        "routine_status_counts": owner_events[
            "routineStatus"
        ].value_counts().to_dict(),
        "owner_purchase_events": len(owner_events),
        "owner_purchase_event_issuers": int(
            owner_events["issuerCik"].nunique()
        ),
        "hashes": {
            "protocol_sha256": sha256(protocol_path),
            "census_gate_sha256": sha256(census_gate),
            "normalized_manifest_sha256": sha256(
                snapshot / "normalized_manifest.json"
            ),
            "episodes_sha256": sha256(episodes_path),
            "universe_sha256": sha256(universe_path),
            "normalized_independent_universe_sha256": sha256(
                snapshot / "normalized/independent_universe.csv"
            ),
            "events_sha256": sha256(output_events),
            "panel_sha256": sha256(output_panel),
            "folds_sha256": sha256(output_folds),
        },
        "claim_boundary": (
            "hypothesis-specific current-constituent OOS robustness; "
            "not blind and not survivorship safe"
        ),
        "interpretation": (
            "Protective veto evidence only; absence is not a sell signal."
            if passed else
            "No insider evidence may enter HERD or action translation."
        ),
        "price_thresholds_tuned": False,
        "blind_holdout_access": False,
        "survivorship_safe": False,
        "operational_action_authority": False,
        "buy_or_profit_take_recommendations_enabled": False,
        "next_decision": (
            "REPLICATE_PROTECTIVE_EVIDENCE_ON_POINT_IN_TIME_UNIVERSE"
            if passed else
            "KEEP_HERD_AS_STATE_OBSERVATION_AND_SEEK_DIFFERENT_INFORMATION"
        ),
    }
    output_report.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("snapshot", type=Path)
    parser.add_argument(
        "--census-gate",
        type=Path,
        default=ROOT / "data/reports/sec_form4_census_gate_v2.json",
    )
    parser.add_argument(
        "--episodes",
        type=Path,
        default=ROOT / "data/reports/independent_rush_evidence_panel_v1.csv",
    )
    parser.add_argument(
        "--universe",
        type=Path,
        default=ROOT / "data/reports/independent_universe_v1.csv",
    )
    parser.add_argument(
        "--output-events",
        type=Path,
        default=ROOT / "data/reports/sec_form4_owner_purchase_events_v1.csv",
    )
    parser.add_argument(
        "--output-panel",
        type=Path,
        default=ROOT / "data/reports/sec_form4_insider_purchase_oos_panel_v1.csv",
    )
    parser.add_argument(
        "--output-folds",
        type=Path,
        default=ROOT / "data/reports/sec_form4_insider_purchase_oos_folds_v1.csv",
    )
    parser.add_argument(
        "--output-report",
        type=Path,
        default=ROOT / "data/reports/sec_form4_insider_purchase_oos_v1.json",
    )
    args = parser.parse_args()
    print(json.dumps(run(
        args.snapshot,
        census_gate=args.census_gate,
        episodes_path=args.episodes,
        universe_path=args.universe,
        output_events=args.output_events,
        output_panel=args.output_panel,
        output_folds=args.output_folds,
        output_report=args.output_report,
    ), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
