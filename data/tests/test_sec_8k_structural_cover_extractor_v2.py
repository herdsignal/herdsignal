import copy
import json

import pytest

from herd.sec_8k_structural_cover_extractor_v2 import (
    PROTOCOL,
    Sec8KStructuralCoverExtractorError,
    build,
    extract_structural_symbols,
)


def test_structural_extractor_reads_symbol_column_not_markup_names() -> None:
    content = b"""
    <table><tr><th>Title of each class</th><th>Trading Symbol(s)</th><th>Exchange</th></tr>
    <tr><td>Common Stock</td><td>TEST</td><td>NYSE</td></tr></table>
    <div>DIV</div><td>TD</td>
    """

    assert extract_structural_symbols(content) == ["TEST"]


def test_v2_is_regression_only_and_creates_unseen_review_queue() -> None:
    _, report = build()

    assert report["documents"] == 275
    assert report["development_regression_rows"] == 110
    assert report["development_regression_passed"] == 110
    assert report["unseen_rows"] == 165
    assert report["unseen_candidate_rows"] == 5
    assert report["independent_precision_claim_allowed"] is False
    assert report["identity_promotion_allowed"] is False


def test_v2_rejects_action_authority(tmp_path) -> None:
    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    changed = copy.deepcopy(protocol)
    changed["authority"]["operational_action_ratio"] = 0.05
    path = tmp_path / "protocol.json"
    path.write_text(json.dumps(changed), encoding="utf-8")

    with pytest.raises(Sec8KStructuralCoverExtractorError, match="fail-closed"):
        build(path)
