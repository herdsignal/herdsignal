"""공개 비가격 선행정보의 실제 로컬 PIT 준비 상태를 fail-closed로 판정한다."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

from herd.sec_company_cik_linker import iter_master_rows


ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = Path(__file__).with_suffix(".json")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _resolve(path: str, *, directory: bool = False) -> Path:
    resolved = (ROOT / path).resolve()
    valid = resolved.is_dir() if directory else resolved.is_file()
    if not resolved.is_relative_to(ROOT) or not valid:
        raise ValueError(f"missing or unsafe source: {path}")
    return resolved


def load_protocol(path: Path = PROTOCOL) -> dict:
    protocol = json.loads(path.read_text(encoding="utf-8"))
    if protocol.get("status") != "LOCKED_BEFORE_LOCAL_COVERAGE_AUDIT":
        raise ValueError("readiness protocol must be locked before coverage audit")
    forbidden = set(protocol.get("forbidden", []))
    required = {
        "JOIN_FORM4_REPORTING_OWNER_CIK_TO_ISSUER_CIK",
        "TREAT_ALL_INSIDER_SALES_AS_BEARISH",
        "CHANGE_HERD_WEIGHTS",
    }
    if required - forbidden:
        raise ValueError("leading-information authority firewall is incomplete")
    return protocol


def _source(protocol: dict, source_id: str) -> dict:
    return next(item for item in protocol["sources"] if item["id"] == source_id)


def master_form_inventory(master: Path, selected_forms: set[str]) -> dict:
    counts = Counter()
    yearly = defaultdict(Counter)
    first_date, last_date = None, None
    files = sorted((master / "raw").glob("*-master.idx"))
    for path in files:
        for _, _, form, filed, _ in iter_master_rows(path):
            if form not in selected_forms:
                continue
            counts[form] += 1
            yearly[filed[:4]][form] += 1
            first_date = filed if first_date is None else min(first_date, filed)
            last_date = filed if last_date is None else max(last_date, filed)
    return {
        "master_files": len(files),
        "forms": dict(sorted(counts.items())),
        "yearly": {
            year: dict(sorted(values.items())) for year, values in sorted(yearly.items())
        },
        "first_filed_date": first_date,
        "last_filed_date": last_date,
    }


def _local_corpora(pattern: str) -> list[dict]:
    result = []
    for path in sorted(ROOT.glob(pattern)):
        if not path.is_dir():
            continue
        manifest = path / "manifest.json"
        result.append({
            "path": path.relative_to(ROOT).as_posix(),
            "manifest_present": manifest.is_file(),
            "manifest_sha256": _sha256(manifest) if manifest.is_file() else None,
        })
    return result


def audit(protocol_path: Path = PROTOCOL) -> dict:
    protocol = load_protocol(protocol_path)
    master = _resolve(protocol["master_index"]["path"], directory=True)
    guidance = _source(protocol, "SEC_8K_GUIDANCE_REVISION")
    atomic_path = _resolve(guidance["local_atomic_report"])
    pair_path = _resolve(guidance["local_pair_report"])
    atomic = json.loads(atomic_path.read_text(encoding="utf-8"))
    pairs = json.loads(pair_path.read_text(encoding="utf-8"))
    guidance_ready = bool(
        pairs["atomic_revision_pairs"] >= guidance["minimum_revision_pairs"]
        and pairs["distinct_tickers"] >= guidance["minimum_tickers"]
        and pairs.get("pair_coverage_gate_passed") is True
    )

    form4 = _source(protocol, "SEC_FORM4_INSIDER_TRANSACTIONS")
    form13 = _source(protocol, "SEC_13F_INSTITUTIONAL_HOLDINGS")
    inventory = master_form_inventory(
        master, set(form4["master_forms"]) | set(form13["master_forms"])
    )
    form4_corpora = _local_corpora(form4["local_corpus_glob"])
    form13_corpora = _local_corpora(form13["local_corpus_glob"])
    finra = _source(protocol, "FINRA_EQUITY_SHORT_INTEREST")
    finra_corpora = _local_corpora(finra["local_corpus_glob"])

    source_decisions = [
        {
            "source": guidance["id"],
            "status": "READY_FOR_HYPOTHESIS_PREREGISTRATION"
            if guidance_ready else "BLOCKED_ATOMIC_REVISION_PAIR_COVERAGE",
            "atomic_bindings": atomic["valid_rows_promoted"],
            "atomic_revision_pairs": pairs["atomic_revision_pairs"],
            "distinct_tickers": pairs["distinct_tickers"],
            "minimum_revision_pairs": guidance["minimum_revision_pairs"],
            "minimum_tickers": guidance["minimum_tickers"],
            "coverage_passed": guidance_ready,
            "next_action": "NONE" if guidance_ready
            else "Do not resume parser versioning; add only human-reviewed atomic bindings from naturally arriving filings.",
        },
        {
            "source": form4["id"],
            "status": "COLLECTION_FEASIBLE_NOT_LOCALLY_READY",
            "master_index_filings": sum(inventory["forms"].get(form, 0) for form in form4["master_forms"]),
            "issuer_linked_xml_corpora": len(form4_corpora),
            "master_cik_join_allowed": False,
            "sell_direction_allowed": False,
            "reason": (
                "Master index proves source abundance but identifies reporting owners, not issuers. "
                "Issuer-linked XML, acceptance time, transaction semantics and footnotes are not collected locally."
            ),
            "next_action": "BUILD_HASHED_FORM4_ISSUER_XML_CORPUS_WITHOUT_PRICE_OUTCOMES",
        },
        {
            "source": form13["id"],
            "status": "CONTEXT_ONLY_NOT_DIRECTION_READY",
            "master_index_filings": sum(inventory["forms"].get(form, 0) for form in form13["master_forms"]),
            "manager_corpora": len(form13_corpora),
            "manager_cik_join_allowed": False,
            "publication_lag_days": form13["maximum_publication_lag_days"],
            "sell_direction_allowed": False,
            "next_action": "DEFER_UNTIL_A_DIRECTION_SOURCE_PASSES",
        },
        {
            "source": finra["id"],
            "status": "RECENT_EXPLORATORY_DATA_NOT_LOCALLY_ARCHIVED",
            "local_corpora": len(finra_corpora),
            "public_history_years": finra["public_history_years"],
            "minimum_primary_history_years": protocol["minimum_primary_history_years"],
            "primary_oos_ready": False,
            "sell_direction_allowed": False,
            "next_action": "DO_NOT_USE_FOR_PRIMARY_LONG_HORIZON_OOS",
        },
    ]
    for source_id in (
        "HISTORICAL_ANALYST_ESTIMATE_REVISIONS",
        "HISTORICAL_EQUITY_OPTION_SURFACE",
    ):
        source = _source(protocol, source_id)
        source_decisions.append({
            "source": source_id,
            "status": "DATA_BLOCKED",
            "reason": source["reason"],
            "sell_direction_allowed": False,
            "next_action": "REQUIRE_LICENSED_DATA_OR_KEEP_BLOCKED",
        })

    ready = [
        item["source"] for item in source_decisions
        if item["status"] == "READY_FOR_HYPOTHESIS_PREREGISTRATION"
    ]
    return {
        "report_version": "HERD_LEADING_INFORMATION_READINESS_V2",
        "status": "NO_NON_PRICE_DIRECTION_SOURCE_READY" if not ready
        else "NON_PRICE_SOURCE_READY_FOR_PREREGISTRATION",
        "protocol_sha256": _sha256(protocol_path),
        "master_manifest_sha256": _sha256(master / "manifest.json"),
        "master_form_inventory": inventory,
        "source_decisions": source_decisions,
        "ready_sources": ready,
        "ready_source_count": len(ready),
        "price_outcomes_opened": False,
        "new_hypothesis_preregistered": False,
        "herd_formula_change_allowed": False,
        "operational_action_authority": False,
        "blind_holdout_access": False,
        "next_priority": "BUILD_FORM4_SOURCE_CORPUS_ONLY"
        if not ready else "PREREGISTER_ONE_READY_NON_PRICE_HYPOTHESIS",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, default=PROTOCOL)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = audit(args.protocol)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
