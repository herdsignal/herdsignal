import json
from pathlib import Path

from herd.sec_guidance_direction_oos_v1 import evaluate


ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = json.loads((ROOT / "data/herd/sec_guidance_direction_oos_v1.json").read_text())


def test_guidance_oos_does_not_open_prices_without_qualified_pairs() -> None:
    report = evaluate(PROTOCOL)
    assert report["price_manifest_opened"] is False
    assert report["evaluated_pairs"] == 0
    assert report["evaluated_folds"] == 0
    assert report["admitted_direction_evidence"] == 0
    assert report["decision"] == "OOS_BLOCKED_BY_PAIR_COVERAGE"
    assert report["ready_for_herd_combination"] is False
    assert report["operational_action_ratio"] == 0
