import json
from pathlib import Path

import pandas as pd

from herd.sec_guidance_atomic_bindings_v1 import build as build_bindings
from herd.sec_guidance_atomic_pairs_v1 import build as build_pairs


ROOT = Path(__file__).resolve().parents[2]


def _load(relative: str) -> dict:
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


def test_v2_bindings_promote_only_reviewed_valid_rows(monkeypatch):
    monkeypatch.chdir(ROOT)
    bindings, report = build_bindings(
        _load("data/herd/sec_guidance_atomic_bindings_v2.json")
    )
    v2_review = pd.read_csv(
        ROOT / "data/reports/sec_guidance_atomic_census_v2_reviewed.csv"
    )
    expected = set(v2_review.loc[v2_review["review_decision"].eq("VALID"), "review_id"])
    promoted = set(bindings["review_id"]) & set(v2_review["review_id"])
    assert promoted == expected
    assert not bindings["direction_authority"].any()
    assert report["source_fact_authority_only"] is True


def test_v2_pairs_pass_coverage_without_direction_or_price(monkeypatch):
    monkeypatch.chdir(ROOT)
    pairs, report = build_pairs(_load("data/herd/sec_guidance_atomic_pairs_v2.json"))
    assert len(pairs) >= 150
    assert pairs["ticker"].nunique() >= 20
    assert report["pair_coverage_gate_passed"] is True
    assert report["direction_labels_created"] is False
    assert report["price_outcomes_observed"] is False
    assert report["sell_authority"] is False


def test_v2_pair_identity_is_exact(monkeypatch):
    monkeypatch.chdir(ROOT)
    pairs, _ = build_pairs(_load("data/herd/sec_guidance_atomic_pairs_v2.json"))
    assert not pairs.empty
    assert (pairs["prior_accession"] != pairs["current_accession"]).all()
    assert pairs["prior_binding_id"].notna().all()
    assert pairs["current_binding_id"].notna().all()
