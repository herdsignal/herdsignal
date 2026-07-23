import hashlib
import json
from pathlib import Path

import pandas as pd

from herd.sec_guidance_atomic_bindings_v1 import build


ROOT = Path(__file__).resolve().parents[2]


def test_atomic_bindings_promote_only_reviewed_valid_facts() -> None:
    protocol = json.loads((ROOT / "data/herd/sec_guidance_atomic_bindings_v1.json").read_text())
    bindings, report = build(protocol)
    expected_valid = sum(
        pd.read_csv(ROOT / path)["review_decision"].eq("VALID").sum()
        for path in protocol["review_ledgers"]
    )
    assert len(bindings) == expected_valid
    assert bindings["binding_id"].is_unique
    assert bindings["reviewer"].notna().all()
    assert bindings["reviewed_at"].notna().all()
    assert not bindings["direction_authority"].any()
    assert not bindings["veto_authority"].any()
    assert report["unreviewed_v10_rows_promoted"] == 0


def test_atomic_pair_eligibility_is_conservative() -> None:
    protocol = json.loads((ROOT / "data/herd/sec_guidance_atomic_bindings_v1.json").read_text())
    bindings, _ = build(protocol)
    eligible = bindings.loc[bindings["pair_eligible"]]
    assert not eligible["semantic_locator_collision"].any()
    assert not eligible["accounting_basis"].isin(protocol["pair_ineligible_accounting_basis"]).any()
    assert not eligible["metric_subtype"].isin(protocol["pair_ineligible_metric_subtype"]).any()


def test_atomic_binding_artifact_is_hash_locked() -> None:
    report = json.loads((ROOT / "data/reports/sec_guidance_atomic_bindings_v1.json").read_text())
    ledger = ROOT / "data/reports/sec_guidance_atomic_bindings_v1.csv"
    assert hashlib.sha256(ledger.read_bytes()).hexdigest() == report["bindings_sha256"]
