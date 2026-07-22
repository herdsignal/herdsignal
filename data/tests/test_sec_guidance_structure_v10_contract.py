import json
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]


def test_v10_contract_has_a_hard_stop_rule_and_no_issuer_exceptions() -> None:
    contract = json.loads((ROOT / "data/herd/sec_guidance_structure_v10_contract.json").read_text())
    audit = pd.read_csv(ROOT / contract["development_error_audit"])
    assert contract["status"] == "LOCKED_BEFORE_V10_IMPLEMENTATION"
    assert len(audit) == 7
    assert set(audit["error_family"]).issubset(set(contract["allowed_grammar_families"]))
    assert contract["minimum_v9_errors_corrected_or_rejected"] == 5
    assert contract["maximum_v9_valid_semantic_changes"] == 0
    assert contract["stop_rule"]["if_independent_wilson_gate_fails"] == "STOP_ITERATIVE_PARSER_VERSIONING"
    assert "ISSUER_SPECIFIC_EXCEPTION" in contract["forbidden"]
