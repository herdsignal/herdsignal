import copy
import json

import pandas as pd
import pytest

from herd.sec_earnings_soft_information_measurement_v1 import (
    CANDIDATES_PATH,
    PROTOCOL_PATH,
    REPORT_PATH,
    REVIEW_PATH,
    SoftInformationMeasurementError,
    _load_protocol,
    _validate_firewall,
    extract_sentence_facts,
    soft_text_blocks,
)
from herd.sec_earnings_soft_information_review_workbench_v1 import build_payload
from herd.sec_earnings_soft_information_source_review_v1 import (
    SoftInformationReviewError,
    evaluate,
    merge_decisions,
)


def test_measurement_protocol_keeps_direction_and_price_closed():
    protocol = _load_protocol()
    assert protocol["scope"] == "PRICE_BLIND_ATOMIC_SOURCE_MEASUREMENT_ONLY"
    assert protocol["firewall"]["aggregateDirectionScoreComputed"] is False
    assert protocol["firewall"]["priceOrReturnOutcomesOpened"] is False
    assert protocol["firewall"]["operationalActionRatio"] == 0.0


def test_measurement_firewall_fails_closed():
    protocol = json.loads(PROTOCOL_PATH.read_text())
    changed = copy.deepcopy(protocol)
    changed["firewall"]["automaticValidLabelsAllowed"] = True
    with pytest.raises(SoftInformationMeasurementError):
        _validate_firewall(changed)


def test_atomic_extraction_tracks_topic_cues_negation_and_comparison():
    protocol = _load_protocol()
    sentence = (
        "We do not expect customer demand to improve compared with the prior year "
        "because order activity remains volatile."
    )
    facts = extract_sentence_facts(sentence, protocol)
    demand = next(fact for fact in facts if fact["topic"] == "DEMAND")
    assert {"EXPECTATION", "EXPANSION", "UNCERTAINTY"}.issubset(
        demand["cueFamilies"]
    )
    assert demand["negatedCuePresent"] is True
    assert demand["comparisonPresent"] is True


def test_definitions_tables_and_forward_looking_boilerplate_are_excluded():
    protocol = _load_protocol()
    definition = (
        "Remaining performance obligations represents contracted revenue that has "
        "not yet been recognized in future periods."
    )
    disclaimer = (
        "This release contains forward-looking statements about future demand and "
        "our ability to improve operating margin."
    )
    assert extract_sentence_facts(definition, protocol) == []
    assert extract_sentence_facts(disclaimer, protocol) == []
    content = b"<html><body><table><tr><td>Demand increased 20%</td></tr></table><p>Customer demand increased meaningfully.</p></body></html>"
    blocks = soft_text_blocks(content)
    assert len(blocks) == 1
    assert blocks[0]["block_text"] == "Customer demand increased meaningfully."


def test_committed_measurement_is_pending_and_contains_no_sentence_or_outcome():
    report = json.loads(REPORT_PATH.read_text())
    candidates = pd.read_csv(CANDIDATES_PATH, dtype=str, keep_default_na=False)
    review = pd.read_csv(REVIEW_PATH, dtype=str, keep_default_na=False)
    assert report["status"] == "SOURCE_REVIEW_PENDING"
    assert report["reviewRows"] == 240
    assert report["reviewIssuers"] >= 30
    assert report["reviewTopics"] == 7
    assert set(review["review_decision"]) == {"PENDING"}
    forbidden = {"price", "return", "label", "herd", "action"}
    assert not any(
        token in column.casefold()
        for column in candidates.columns
        for token in forbidden
    )
    assert "sentence" not in candidates.columns
    assert "sentence" not in review.columns


def test_review_gate_requires_provenance_and_strict_identity():
    protocol = _load_protocol()
    queue = pd.read_csv(REVIEW_PATH, dtype=str, keep_default_na=False)
    decisions = queue.copy()
    decisions["review_decision"] = "VALID"
    with pytest.raises(SoftInformationReviewError):
        evaluate(decisions, protocol)

    decisions["reviewer_id"] = "reviewer-1"
    decisions["reviewed_at_utc"] = "2026-08-02T00:00:00Z"
    decisions["review_method"] = "PRIMARY_SOURCE_DIRECT"
    report = evaluate(decisions, protocol)
    assert report["reviewGatePassed"] is True
    changed = decisions.copy()
    changed.loc[0, "sentence_sha256"] = "changed"
    with pytest.raises(SoftInformationReviewError):
        merge_decisions(queue, changed)


def test_local_workbench_reconstructs_source_sentence_without_outcomes(tmp_path):
    queue = pd.read_csv(REVIEW_PATH, dtype=str, keep_default_na=False).head(2)
    path = tmp_path / "review.csv"
    queue.to_csv(path, index=False)
    payload, manifest = build_payload(path)
    assert len(payload) == 2
    assert all(row["sentence"] for row in payload)
    assert manifest["sentenceTextPersistedOnlyInLocalWorkbench"] is True
    assert manifest["priceOrReturnOutcomesOpened"] is False
    assert manifest["automaticValidLabelsCreated"] is False
