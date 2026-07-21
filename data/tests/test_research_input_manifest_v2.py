import copy

import pytest

from herd.research_input_manifest_v2 import (
    ResearchInputManifestV2Error,
    load_research_input_manifest_v2,
    validate_research_input_manifest_v2,
)


def test_long_public_research_inputs_are_pinned():
    _, audit = load_research_input_manifest_v2()
    assert audit["price_tickers"] == 65
    assert audit["benchmark_etfs"] == 14
    assert audit["sec_fold_rows_ready"] == 200
    assert audit["survivorship_safe"] is False


def test_manifest_rejects_weaker_fold_requirement():
    manifest, _ = load_research_input_manifest_v2()
    changed = copy.deepcopy(manifest)
    changed["oos_folds"]["price_lane_minimum_folds"] = 10
    with pytest.raises(ResearchInputManifestV2Error, match="insufficient"):
        validate_research_input_manifest_v2(changed)
