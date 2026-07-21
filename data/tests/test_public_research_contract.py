import copy

import pytest

from herd.public_research_contract import (
    PublicResearchContractError,
    load_public_research_contract,
    validate_public_research_contract,
)


def test_public_research_contract_blocks_unlicensed_promotion():
    _, audit = load_public_research_contract()
    assert audit["survivorship_safe"] is False
    assert audit["blind_holdout_allowed"] is False
    assert audit["operational_action_ratio"] == 0.0


def test_contract_rejects_survivorship_promotion():
    contract, _ = load_public_research_contract()
    changed = copy.deepcopy(contract)
    changed["promotion_policy"]["survivorship_safe"] = True
    with pytest.raises(PublicResearchContractError, match="unsafe"):
        validate_public_research_contract(changed)
