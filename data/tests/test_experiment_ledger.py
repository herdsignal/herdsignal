import copy
import json

import pytest

from herd.experiment_ledger import (
    ExperimentLedgerError,
    LEDGER_PATH,
    load_ledger,
    validate_ledger,
)


def test_committed_experiment_ledger_is_complete_and_reproducible():
    _, audit = load_ledger()

    assert audit["record_count"] == 3
    assert audit["declared_test_count"] == 18
    assert audit["promotion_allowed"] is False
    assert len(audit["head_sha256"]) == 64


def test_hash_chain_rejects_a_changed_historical_decision():
    ledger = json.loads(LEDGER_PATH.read_text(encoding="utf-8"))
    changed = copy.deepcopy(ledger)
    changed["records"][0]["decision"] = "PASS"

    with pytest.raises(ExperimentLedgerError, match="record hash mismatch"):
        validate_ledger(changed)


def test_research_record_cannot_promote_itself():
    ledger = json.loads(LEDGER_PATH.read_text(encoding="utf-8"))
    changed = copy.deepcopy(ledger)
    changed["records"][-1]["promotion_allowed"] = True

    with pytest.raises(ExperimentLedgerError, match="cannot promote itself"):
        validate_ledger(changed)
