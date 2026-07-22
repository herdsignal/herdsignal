import json
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]


def test_v9_contract_is_locked_to_audited_grammar_families() -> None:
    contract = json.loads((ROOT / "data/herd/sec_guidance_structure_v9_contract.json").read_text())
    audit = pd.read_csv(ROOT / contract["development_error_audit"])
    assert contract["status"] == "LOCKED_BEFORE_V9_IMPLEMENTATION"
    assert len(audit) == 9
    assert audit["audit_decision"].eq("INVALID").sum() == 8
    assert audit["audit_decision"].eq("VALID").sum() == 1
    assert set(audit.loc[audit["audit_decision"].eq("INVALID"), "error_family"]).issubset(
        set(contract["allowed_grammar_families"])
    )
    assert contract["minimum_v8_errors_corrected_or_rejected"] == 7
    assert contract["maximum_v8_valid_semantic_changes"] == 0


def test_sg8_0048_is_corrected_as_source_review_label_error() -> None:
    labels = pd.read_csv(ROOT / "data/herd/sec_guidance_structure_v8_review_labels.csv")
    row = labels.loc[labels["review_id"].eq("SG8-0048")].iloc[0]
    assert row["review_decision"] == "VALID"
    assert row["review_reason"] == "CURRENT_GUIDANCE_WITH_NC_CONFIRMED"
