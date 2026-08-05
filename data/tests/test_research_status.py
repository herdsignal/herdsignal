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
            "next_pending_batch": "B005",
        },
        "research_boundary": {
            "pending_sec_identity_reviews": 70,
            "next_stage": "COMPLETE_SEC_8K_HUMAN_REVIEW_BATCH_B005",
        },
        "contradictions": [],
    }


def test_research_status_keeps_action_boundary_and_review_progress_visible():
    summary = build_summary(_state())

    assert summary["operational_action"] == "HOLD"
    assert summary["operational_action_ratio"] == 0.0
    assert summary["sec_review"] == {
        "reviewed": 40,
        "total": 110,
        "pending": 70,
        "next_batch": "B005",
    }


def test_research_status_text_is_short_and_action_safe():
    text = format_text(build_summary(_state()))

    assert "운영 행동: HOLD (0%)" in text
    assert "SEC 원문 검수: 40/110 완료" in text
    assert "다음 배치: B005" in text
