import hashlib
import json

from herd.sec_form4_nonroutine_sale_feasibility_v1 import REPORT_PATH, ROOT


def test_sale_feasibility_does_not_open_outcomes():
    report = json.loads(REPORT_PATH.read_text())
    assert report["status"] == "SALE_FEASIBILITY_COMPLETE"
    assert report["price_or_return_outcomes_opened"] is False
    assert report["direction_hypothesis_executed"] is False
    assert report["operational_action_ratio"] == 0.0


def test_sale_event_ledger_hash_is_pinned():
    report = json.loads(REPORT_PATH.read_text())
    path = ROOT / report["events_path"]
    assert hashlib.sha256(path.read_bytes()).hexdigest() == report["events_sha256"]
