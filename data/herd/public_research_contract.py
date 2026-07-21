"""유료 권위 데이터가 없는 HERD 연구의 주장·승격 경계를 검증한다."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


CONTRACT_PATH = Path(__file__).with_name("public_research_contract.json")
CONTRACT_VERSION = "HERD_PUBLIC_RESEARCH_ONLY_V1"


class PublicResearchContractError(ValueError):
    """공개 데이터 연구 경계가 완화됐을 때 발생한다."""


def validate_public_research_contract(contract: dict[str, Any]) -> dict[str, Any]:
    if (
        contract.get("contract_version") != CONTRACT_VERSION
        or contract.get("status") != "LOCKED_BEFORE_V2_MEASUREMENT_RESULTS"
        or contract.get("data_tier") != "PUBLIC_RESEARCH_ONLY"
    ):
        raise PublicResearchContractError("public research contract is not locked")

    licensed = contract.get("licensed_sources", {})
    if any(licensed.get(source) is not False for source in (
        "wrds", "crsp", "official_sp_constituent_history"
    )):
        raise PublicResearchContractError("unavailable licensed source was enabled")

    forbidden = set(contract.get("forbidden_claims", []))
    required_forbidden = {
        "GENERAL_US_EQUITY_MODEL",
        "SURVIVORSHIP_SAFE_BACKTEST",
        "PRODUCTION_TRADING_SIGNAL",
        "HIGH_HERD_ALONE_AUTHORIZES_PROFIT_TAKE",
    }
    if not required_forbidden.issubset(forbidden):
        raise PublicResearchContractError("critical forbidden claim is missing")

    promotion = contract.get("promotion_policy", {})
    if (
        promotion.get("survivorship_safe") is not False
        or promotion.get("blind_holdout_allowed") is not False
        or promotion.get("production_signal_allowed") is not False
        or promotion.get("operational_action_ratio") != 0.0
        or promotion.get("independent_oos_evidence_required_before_cycle") is not True
    ):
        raise PublicResearchContractError("promotion policy is unsafe")

    if contract.get("missing_data_policy", {}).get("missing_business_comparables") \
            != "UNKNOWN_DOES_NOT_AUTHORIZE_ADD_BUY":
        raise PublicResearchContractError("unknown business state must fail closed")

    return {
        "contract_version": CONTRACT_VERSION,
        "data_tier": "PUBLIC_RESEARCH_ONLY",
        "survivorship_safe": False,
        "blind_holdout_allowed": False,
        "production_signal_allowed": False,
        "operational_action_ratio": 0.0,
    }


def load_public_research_contract(path: Path = CONTRACT_PATH) -> tuple[dict, dict]:
    contract = json.loads(path.read_text(encoding="utf-8"))
    return contract, validate_public_research_contract(contract)
