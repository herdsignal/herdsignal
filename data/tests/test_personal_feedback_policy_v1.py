import json
from pathlib import Path


def test_personal_journal_feedback_cannot_train_or_promote_model() -> None:
    policy = json.loads(
        Path("data/config/personal_feedback_policy_v1.json").read_text(
            encoding="utf-8"
        )
    )
    boundaries = policy["boundaries"]

    assert policy["source"] == "signal_journal"
    assert boundaries["user_decision_is_model_label"] is False
    assert boundaries["automatic_training_allowed"] is False
    assert boundaries["automatic_threshold_tuning_allowed"] is False
    assert boundaries["promotion_evidence_allowed"] is False
    assert boundaries["action_authority_allowed"] is False
    assert all(policy["research_use"].values())
