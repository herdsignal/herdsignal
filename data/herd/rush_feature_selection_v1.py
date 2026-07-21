"""발견구간 기준을 통과하지 못한 Rush 변수를 제거하고 연구 리드만 분리한다."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd


def build_selection(levels: pd.DataFrame, transitions: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    levels = levels.assign(source_family="LEVEL")
    transitions = transitions.assign(source_family="TRANSITION_4W")
    combined = pd.concat([levels, transitions], ignore_index=True, sort=False)
    combined["selection_status"] = "REMOVED_NO_REPEATABLE_DISCOVERY_EFFECT"
    combined.loc[combined["retained_for_preregistration"].astype(bool), "selection_status"] = "RETAINED"
    near = (
        (~combined["retained_for_preregistration"].astype(bool))
        & (combined["rank_biserial"].abs() >= .20)
        & (combined["same_direction_halves"] >= 2)
    )
    combined.loc[near, "selection_status"] = "RESEARCH_LEAD_NOT_ADMITTED"
    retained = combined[combined["selection_status"] == "RETAINED"]
    leads = combined[combined["selection_status"] == "RESEARCH_LEAD_NOT_ADMITTED"]
    report = {
        "report_version":"herd-rush-feature-selection-v1",
        "status":"NO_FEATURE_ADMITTED" if retained.empty else "FEATURES_ADMITTED",
        "features_reviewed":len(combined),
        "retained_features":retained["feature"].tolist(),
        "retained_count":len(retained),
        "research_leads_not_admitted":sorted(leads["feature"].unique().tolist()),
        "removed_count":int((combined["selection_status"] == "REMOVED_NO_REPEATABLE_DISCOVERY_EFFECT").sum()),
        "confirmation_period_accessed":False,
        "operational_action_ratio":0.0,
        "blind_holdout_access":False,
    }
    return combined, report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--levels", type=Path, required=True)
    parser.add_argument("--transitions", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    table, report = build_selection(pd.read_csv(args.levels), pd.read_csv(args.transitions))
    table.to_csv(args.output, index=False)
    args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
