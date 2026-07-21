import json
from pathlib import Path

from herd.expectation_combination_gate_v1 import build_gate


ROOT = Path(__file__).resolve().parents[1]


def test_gate_blocks_empty_evidence_without_creating_formula():
    protocol = json.loads((ROOT / "herd/expectation_combination_gate_v1.json").read_text())
    source = {"families": {"A": {"decision": "REJECTED", "passed_measurements": []}}}
    result = build_gate(protocol, source)
    assert result["decision"] == "BLOCKED_NO_INDEPENDENT_EVIDENCE"
    assert result["combination_formula"] is None
    assert result["research_trim_ratio"] == 0.0


def test_gate_admits_only_explicitly_passed_measurements_but_never_live_authority():
    protocol = json.loads((ROOT / "herd/expectation_combination_gate_v1.json").read_text())
    source = {"families": {
        "A": {"decision": "PASS", "passed_measurements": ["x"]},
        "B": {"decision": "REJECTED", "passed_measurements": ["y"]},
    }}
    result = build_gate(protocol, source)
    assert result["admitted_evidence"] == {"A": ["x"]}
    assert result["eligible"] is True
    assert result["operational_sell_authority"] is False
