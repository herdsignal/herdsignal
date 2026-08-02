import copy
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from herd.fixed_policy_economic_baselines_v1 import (
    REPORT_PATH,
    ROWS_PATH,
    FixedPolicyBaselinesError,
    load_contract,
)


def test_baseline_contract_locks_all_non_predictive_comparators():
    contract = load_contract()

    assert {item["id"] for item in contract["policies"]} == {
        "MATCHED_HOLD",
        "TRIM_KEEP_CASH",
        "TRIM_REENTER_21",
        "TRIM_REENTER_63",
        "TRIM_TO_SPY_HORIZON",
    }
    assert contract["reporting"]["baseline_selection"] == "NONE"
    assert contract["firewall"]["operational_action"] == "HOLD"
    assert contract["firewall"]["operational_action_ratio"] == 0.0


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (
            lambda c: c["execution"].update({"trim_fraction": 0.15}),
            "execution contract",
        ),
        (
            lambda c: c["execution"].update(
                {"observation_session": "REQUIRE_EXACT_SIGNAL_DATE"}
            ),
            "execution contract",
        ),
        (
            lambda c: c["policies"][2].update(
                {"reentry_sessions_after_sale": 10}
            ),
            "fixed baseline rule",
        ),
        (
            lambda c: c["reporting"].update(
                {"baseline_selection": "BEST_AFTER_RESULTS"}
            ),
            "reporting boundary",
        ),
        (
            lambda c: c["firewall"].update(
                {"baseline_results_authorize_action": True}
            ),
            "firewall",
        ),
    ],
)
def test_baseline_contract_fails_closed(tmp_path, mutation, message):
    contract = copy.deepcopy(load_contract())
    mutation(contract)
    path = tmp_path / "mutated.json"
    path.write_text(json.dumps(contract), encoding="utf-8")

    with pytest.raises(FixedPolicyBaselinesError, match=message):
        load_contract(path)


def test_success_label_cannot_enter_policy_input_columns(tmp_path):
    contract = copy.deepcopy(load_contract())
    contract["event_population"]["allowed_input_columns"].append(
        "success_label"
    )
    path = tmp_path / "mutated.json"
    path.write_text(json.dumps(contract), encoding="utf-8")

    with pytest.raises(FixedPolicyBaselinesError, match="event population"):
        load_contract(path)


def test_future_low_prohibition_cannot_be_removed(tmp_path):
    contract = copy.deepcopy(load_contract())
    contract["forbidden"].remove("USE_FUTURE_LOW_OR_OUTCOME_PATH_FOR_EXECUTION")
    path = tmp_path / "mutated.json"
    path.write_text(json.dumps(contract), encoding="utf-8")

    with pytest.raises(FixedPolicyBaselinesError, match="forbidden"):
        load_contract(path)


def test_committed_baseline_is_complete_and_reports_each_fold():
    report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))

    assert report["complete"] is True
    assert report["generated_rows"] == report["expected_rows"] == 32_415
    assert report["excluded_event_count"] == 0
    assert report["baseline_selected"] is None
    assert report["direction_evidence_admitted"] is False
    assert len(report["fold_summaries"]) > len(report["summaries"])


def test_committed_rows_use_reproducible_gzip_header():
    header = ROWS_PATH.read_bytes()[:10]

    assert header[:2] == b"\x1f\x8b"
    assert int.from_bytes(header[4:8], "little") == 0
