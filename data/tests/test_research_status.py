from tools.research_status import build_summary, format_text


def _state():
    return {
        "status": "PASS",
        "product": {"state_model": "HERD_STATE_S1"},
        "action_research": {
            "default_action": "HOLD",
            "operational_action_ratio": 0.0,
            "adoptable_candidates": 0,
        },
        "sec_8k_review_batches": {
            "rows": 110,
            "next_pending_batch": None,
        },
        "research_boundary": {
            "pending_sec_identity_reviews": 0,
            "next_stage": "COLLECT_SEC_8K_STRUCTURAL_EVALUATION_PRIMARY_DOCUMENTS_V1",
        },
        "contradictions": [],
    }


def test_research_status_keeps_action_boundary_and_review_progress_visible():
    summary = build_summary(_state())

    assert summary["operational_action"] == "HOLD"
    assert summary["operational_action_ratio"] == 0.0
    assert summary["sec_review"] == {
        "reviewed": 110,
        "total": 110,
        "pending": 0,
        "next_batch": None,
    }


def test_research_status_text_is_short_and_action_safe():
    text = format_text(build_summary(_state()))

    assert "운영 행동: HOLD (0%)" in text
    assert "SEC 원문 검수: 110/110 완료" in text
    assert "다음 배치: COMPLETE" in text
