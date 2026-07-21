from herd.rush_confirmation_oos_v1 import evaluate_gate


def test_confirmation_data_remains_unopened_without_hypothesis():
    report = evaluate_gate()
    assert report["status"] == "BLOCKED_NO_PREREGISTERED_HYPOTHESIS"
    assert report["confirmation_rows_read"] == 0
    assert report["oos_tests_executed"] == 0
    assert report["direction_evidence_ready"] is False
    assert report["blocked_test_is_performance_failure"] is False
