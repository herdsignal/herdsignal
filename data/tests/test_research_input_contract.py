import copy

import pytest

from herd.research_input_contract import (
    ResearchInputContractError,
    load_contract,
    validate_contract,
)


def test_committed_research_inputs_are_pinned_and_fail_closed():
    _, audit = load_contract()

    assert audit["price_tickers"] == 55
    assert audit["sec_ciks"] == 51
    assert audit["survivorship_safe"] is False
    assert audit["promotion_allowed"] is False


def test_contract_rejects_survivorship_safe_claim():
    contract, _ = load_contract()
    changed = copy.deepcopy(contract)
    changed["constituent_snapshot"]["survivorship_safe"] = True

    with pytest.raises(ResearchInputContractError, match="fail-closed"):
        validate_contract(changed)


def test_contract_rejects_filing_date_instead_of_acceptance_time():
    contract, _ = load_contract()
    changed = copy.deepcopy(contract)
    changed["availability_rules"]["sec_fact_available_from"] = "FILING_DATE"

    with pytest.raises(ResearchInputContractError, match="availability rules"):
        validate_contract(changed)
