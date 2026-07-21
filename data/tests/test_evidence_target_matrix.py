from herd.evidence_target_matrix import load_and_validate


def test_every_research_candidate_has_every_target_cell():
    _, report = load_and_validate()
    assert report["coverage_complete"] is True
    assert report["research_candidates"] == 15
    assert report["targets"] == 7
    assert report["cells"] == 105


def test_target_authority_cannot_transfer_silently():
    matrix, report = load_and_validate()
    assert report["cross_target_transfer_allowed"] is False
    assert report["direction_evidence_admitted"] == []
    assert all(matrix["transfer_rules"].values())
