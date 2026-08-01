import copy
import json

import pytest

from herd.sec_earnings_soft_information_feasibility_v1 import (
    PROTOCOL_PATH,
    EarningsSoftInformationFeasibilityError,
    _load_protocol,
    build_feasibility,
)


def _protocol():
    return json.loads(PROTOCOL_PATH.read_text())


def test_protocol_keeps_text_and_price_outcomes_closed():
    protocol = _load_protocol()
    assert protocol["measurementDesign"]["stage"] == "NOT_YET_AUTHORIZED"
    assert protocol["firewall"]["textDirectionScoreComputed"] is False
    assert protocol["firewall"]["priceOrReturnOutcomesOpened"] is False
    assert protocol["firewall"]["operationalActionRatio"] == 0.0


def test_protocol_rejects_remote_model_or_action_enable(tmp_path):
    changed = copy.deepcopy(_protocol())
    changed["measurementDesign"]["licensePolicy"]["remoteLlmApiAllowed"] = True
    with pytest.raises(EarningsSoftInformationFeasibilityError):
        build_feasibility(tmp_path / "pairs.csv", tmp_path / "report.json", protocol=changed)

    changed = copy.deepcopy(_protocol())
    changed["firewall"]["operationalActionAllowed"] = True
    with pytest.raises(EarningsSoftInformationFeasibilityError):
        build_feasibility(tmp_path / "pairs.csv", tmp_path / "report.json", protocol=changed)


def test_existing_sec_corpus_passes_price_blind_coverage(tmp_path):
    report = build_feasibility(tmp_path / "pairs.csv", tmp_path / "report.json")
    assert report["coveragePassed"] is True
    assert report["documents"] >= 2500
    assert report["comparablePairs"] >= 2000
    assert report["issuers"] >= 40
    assert report["textMeasurementAuthorized"] is True
    assert report["independentDirectionOosReady"] is False
    assert report["priceOrReturnOutcomesOpened"] is False
    assert report["operationalAction"] == "HOLD"


def test_feasibility_pairs_are_source_only(tmp_path):
    import pandas as pd

    report = build_feasibility(tmp_path / "pairs.csv", tmp_path / "report.json")
    pairs = pd.read_csv(tmp_path / "pairs.csv")
    forbidden = {"return", "price", "label", "herd", "action"}
    assert not any(
        token in column.casefold() for column in pairs.columns for token in forbidden
    )
    assert pairs["pair_id"].is_unique
    assert set(pairs["source_use"]) == {"FEASIBILITY_DEVELOPMENT_ONLY"}
    assert report["pairsSha256"]
