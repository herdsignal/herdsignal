import json

import pytest

from tools.refresh_sec_review_state import SecReviewRefreshError, replace_locked_hash


def test_replace_locked_hash_changes_exactly_one_allowlisted_input(tmp_path) -> None:
    protocol = tmp_path / "protocol.json"
    protocol.write_text(
        json.dumps({"inputs": [{"path": "report.json", "sha256": "a" * 64}]}),
        encoding="utf-8",
    )

    replace_locked_hash(protocol, "report.json", "b" * 64)

    result = json.loads(protocol.read_text(encoding="utf-8"))
    assert result["inputs"][0]["sha256"] == "b" * 64


def test_replace_locked_hash_rejects_missing_or_duplicate_links(tmp_path) -> None:
    missing = tmp_path / "missing.json"
    missing.write_text(json.dumps({"inputs": []}), encoding="utf-8")
    with pytest.raises(SecReviewRefreshError, match="found 0"):
        replace_locked_hash(missing, "report.json", "new")

    duplicate = tmp_path / "duplicate.json"
    duplicate.write_text(
        json.dumps(
            {
                "inputs": [
                    {"path": "report.json", "sha256": "a" * 64},
                    {"path": "report.json", "sha256": "a" * 64},
                ]
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(SecReviewRefreshError, match="found 2"):
        replace_locked_hash(duplicate, "report.json", "b" * 64)
