"""HERD 연구가 사용할 가격·구성·CIK·SEC PIT 입력 경계를 검증한다."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from datetime import date
from pathlib import Path

from herd.data_snapshot import load_snapshot


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = Path(__file__).with_name("research_input_contract.json")
CONTRACT_VERSION = "HERD_RESEARCH_INPUT_V1"


class ResearchInputContractError(RuntimeError):
    """입력 스냅샷 또는 fail-closed 정책이 계약과 다를 때 발생한다."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _repository_file(relative_path: str) -> Path:
    candidate = (REPOSITORY_ROOT / relative_path).resolve()
    if not candidate.is_relative_to(REPOSITORY_ROOT):
        raise ResearchInputContractError(f"path escapes repository: {relative_path}")
    if not candidate.is_file():
        raise ResearchInputContractError(f"missing input artifact: {relative_path}")
    return candidate


def _pinned_file(specification: dict, path_key: str = "path") -> Path:
    path = _repository_file(specification[path_key])
    if _sha256(path) != specification["sha256" if path_key == "path" else "manifest_sha256"]:
        raise ResearchInputContractError(f"input hash mismatch: {specification[path_key]}")
    return path


def _validate_cik_periods(path: Path) -> int:
    with path.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    by_ticker: dict[str, list[tuple[date, date | None]]] = {}
    for row in rows:
        start = date.fromisoformat(row["valid_from"])
        end = date.fromisoformat(row["valid_to"]) if row["valid_to"] else None
        if end is not None and end < start:
            raise ResearchInputContractError("CIK period ends before it starts")
        by_ticker.setdefault(row["ticker"], []).append((start, end))
    for ticker, periods in by_ticker.items():
        ordered = sorted(periods)
        for previous, current in zip(ordered, ordered[1:]):
            if previous[1] is None or current[0] <= previous[1]:
                raise ResearchInputContractError(f"overlapping CIK periods: {ticker}")
    return len(rows)


def _validate_sec_corpus(specification: dict, research_start: str, research_end: str, deep: bool) -> int:
    manifest_path = _pinned_file(specification, "manifest_path")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if (
        manifest.get("start_date") != research_start
        or manifest.get("end_date") != research_end
        or manifest.get("unavailable_documents")
        or manifest.get("companyfacts_unavailable") != 0
        or manifest.get("user_agent_configured") is not True
    ):
        raise ResearchInputContractError(f"SEC corpus is incomplete: {manifest_path}")
    if deep:
        root = manifest_path.parent
        for artifact in manifest.get("artifacts", []):
            path = root / artifact["path"]
            if not path.is_file() or _sha256(path) != artifact["sha256"]:
                raise ResearchInputContractError(f"SEC artifact mismatch: {path}")
    return int(manifest.get("ciks", 0))


def validate_contract(contract: dict, *, deep: bool = False) -> dict:
    if (
        contract.get("contract_version") != CONTRACT_VERSION
        or contract.get("status") != "RESEARCH_ONLY_FAIL_CLOSED"
    ):
        raise ResearchInputContractError("research input contract is not locked")

    period = contract["research_period"]
    if date.fromisoformat(period["end"]) <= date.fromisoformat(period["start"]):
        raise ResearchInputContractError("invalid research period")

    price_spec = contract["price_snapshot"]
    price_manifest_path = _pinned_file(price_spec, "manifest_path")
    price_manifest = json.loads(price_manifest_path.read_text(encoding="utf-8"))
    price_files = list(price_manifest.get("files", {}).values())
    price_starts = {item.get("start") for item in price_files}
    price_ends = {item.get("end") for item in price_files}
    if (
        price_manifest.get("snapshot_id") != price_spec["required_snapshot_id"]
        or price_manifest.get("coverage") != price_spec["required_coverage"]
        or price_manifest.get("source", {}).get("auto_adjust") is not True
        or price_spec.get("price_semantics")
        != "YFINANCE_AUTO_ADJUSTED_OHLC_PROVIDER_SEMANTICS"
        or price_starts != {period["start"]}
        or price_ends != {period["end"]}
    ):
        raise ResearchInputContractError("price snapshot coverage does not match contract")
    if deep:
        load_snapshot(price_manifest_path.parent)

    constituent_spec = contract["constituent_snapshot"]
    constituent_path = _pinned_file(constituent_spec, "manifest_path")
    constituent = json.loads(constituent_path.read_text(encoding="utf-8"))
    quality = constituent.get("quality", {})
    if (
        constituent.get("status") != constituent_spec["required_status"]
        or quality.get("survivorship_safe") is not constituent_spec["survivorship_safe"]
        or quality.get("replay_errors") > constituent_spec["maximum_replay_errors"]
        or quality.get("blocked_events") != constituent_spec["blocked_events"]
        or constituent_spec["allowed_use"] not in constituent.get("policy", {}).get("allowed_uses", [])
    ):
        raise ResearchInputContractError("constituent snapshot violates fail-closed policy")

    forbidden = set(contract.get("forbidden_uses", []))
    if not {"FINAL_MODEL_ADOPTION", "PRODUCTION_SIGNAL", "SURVIVORSHIP_SAFE_CLAIM"}.issubset(forbidden):
        raise ResearchInputContractError("critical forbidden uses are missing")
    rules = contract.get("availability_rules", {})
    if (
        rules.get("sec_fact_available_from") != "SEC_ACCEPTANCE_DATETIME"
        or rules.get("missing_acceptance") != "EXCLUDE"
        or rules.get("missing_cik_mapping") != "EXCLUDE"
        or rules.get("future_restatement_backfill") is not False
    ):
        raise ResearchInputContractError("PIT availability rules are unsafe")

    cik_rows = _validate_cik_periods(_pinned_file(contract["cik_periods"]))
    _pinned_file(contract["fold_link_audit"])
    sec_ciks = sum(
        _validate_sec_corpus(specification, period["start"], period["end"], deep)
        for specification in contract["sec_corpora"]
    )
    return {
        "contract_version": CONTRACT_VERSION,
        "research_period": period,
        "price_tickers": len(price_manifest["completed_tickers"]),
        "sec_ciks": sec_ciks,
        "cik_period_rows": cik_rows,
        "survivorship_safe": False,
        "promotion_allowed": False,
        "deep_verified": deep,
    }


def load_contract(path: Path = CONTRACT_PATH, *, deep: bool = False) -> tuple[dict, dict]:
    contract = json.loads(path.read_text(encoding="utf-8"))
    return contract, validate_contract(contract, deep=deep)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract", type=Path, default=CONTRACT_PATH)
    parser.add_argument("--deep", action="store_true")
    args = parser.parse_args()
    _, audit = load_contract(args.contract, deep=args.deep)
    print(json.dumps(audit, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
