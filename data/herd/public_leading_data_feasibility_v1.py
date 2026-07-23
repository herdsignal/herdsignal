"""공개 선행정보의 PIT 기간·지연·비용·로컬 준비 상태를 fail-closed로 판정한다."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

import pandas as pd

from herd.sec_company_cik_linker import iter_master_rows


ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = Path(__file__).with_suffix(".json")
ALLOWED_PRIMARY_LAG_CLASSES = {
    "IMMEDIATE",
    "NEXT_SESSION_OR_VENDOR_DELIVERY",
    "WITHIN_10_BUSINESS_DAYS",
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _root_path(relative: str) -> Path:
    path = (ROOT / relative).resolve()
    if not path.is_relative_to(ROOT):
        raise ValueError(f"path escapes research root: {relative}")
    return path


def _history_years(start: str, end: str) -> float:
    return (pd.Timestamp(end) - pd.Timestamp(start)).days / 365.2425


def _verify_prerequisites(protocol: dict) -> list[dict]:
    results = []
    artifacts = [
        *protocol["prior_research"],
        protocol["public_research_contract"],
    ]
    for artifact in artifacts:
        path = _root_path(artifact["path"])
        digest = _sha256(path)
        if digest != artifact["sha256"]:
            raise ValueError(f"locked prerequisite changed: {artifact['path']}")
        row = {
            "id": artifact.get("id", "PUBLIC_RESEARCH_CONTRACT"),
            "path": artifact["path"],
            "sha256": digest,
            "verified": True,
        }
        if "required_decision" in artifact:
            report = json.loads(path.read_text(encoding="utf-8"))
            actual = report.get("decision") or report.get("status")
            if actual != artifact["required_decision"]:
                raise ValueError(
                    f"prior research decision changed: {artifact['id']}={actual}"
                )
            row["decision"] = actual
        results.append(row)
    return results


def _local_corpora(pattern: str) -> list[dict]:
    corpora = []
    for path in sorted(ROOT.glob(pattern)):
        if not path.exists():
            continue
        manifest = path / "manifest.json" if path.is_dir() else None
        corpora.append({
            "path": path.relative_to(ROOT).as_posix(),
            "kind": "DIRECTORY" if path.is_dir() else "FILE",
            "manifest_present": bool(manifest and manifest.is_file()),
            "manifest_sha256": _sha256(manifest)
            if manifest and manifest.is_file() else None,
        })
    return corpora


def _master_13f_inventory() -> dict:
    master = ROOT / "data/reference/sec/sec-master-2016q3-2026q3-20260719"
    master_digest = _sha256(master / "manifest.json")
    cached_path = ROOT / "data/reports/leading_information_readiness_v2.json"
    if cached_path.is_file():
        cached = json.loads(cached_path.read_text(encoding="utf-8"))
        if cached.get("master_manifest_sha256") == master_digest:
            inventory = cached["master_form_inventory"]
            forms = {
                form: inventory["forms"].get(form, 0)
                for form in ("13F-HR", "13F-HR/A")
            }
            return {
                "master_manifest_sha256": master_digest,
                "inventory_cache": cached_path.relative_to(ROOT).as_posix(),
                "inventory_cache_sha256": _sha256(cached_path),
                "forms": forms,
                "filings": sum(forms.values()),
                "first_filed_date": inventory["first_filed_date"],
                "last_filed_date": inventory["last_filed_date"],
                "warning": (
                    "This proves filing abundance only. Manager CIK and raw master rows are "
                    "not an issuer-linked point-in-time holdings corpus."
                ),
            }
    counts = Counter()
    first_date, last_date = None, None
    for path in sorted((master / "raw").glob("*-master.idx")):
        for _, _, form, filed, _ in iter_master_rows(path):
            if form not in {"13F-HR", "13F-HR/A"}:
                continue
            counts[form] += 1
            first_date = filed if first_date is None else min(first_date, filed)
            last_date = filed if last_date is None else max(last_date, filed)
    return {
        "master_manifest_sha256": master_digest,
        "inventory_cache": None,
        "inventory_cache_sha256": None,
        "forms": dict(sorted(counts.items())),
        "filings": sum(counts.values()),
        "first_filed_date": first_date,
        "last_filed_date": last_date,
        "warning": (
            "This proves filing abundance only. Manager CIK and raw master rows are "
            "not an issuer-linked point-in-time holdings corpus."
        ),
    }


def _source_decision(source: dict, gate: dict) -> dict:
    years = _history_years(source["pit_start"], source["pit_end"])
    era_years = (
        gate["minimum_point_in_time_history_years"]
        / gate["minimum_non_overlapping_eras"]
    )
    potential_eras = int(years // era_years)
    corpora = _local_corpora(source["local_corpus_glob"])
    semantic_proxy = source["allowed_role_if_not_primary"].startswith("REJECT_")
    checks = {
        "minimum_point_in_time_history_years": (
            years >= gate["minimum_point_in_time_history_years"]
        ),
        "minimum_non_overlapping_eras": (
            potential_eras >= gate["minimum_non_overlapping_eras"]
        ),
        "free_public_research_use": (
            source["public_research_tier_compatible"]
            if gate["requires_free_public_research_use"] else True
        ),
        "security_level_observations": (
            source["security_level_observations"]
            if gate["requires_security_level_observations"] else True
        ),
        "publication_or_acceptance_timestamp": (
            source["publication_timestamp_available"]
            if gate["requires_publication_or_acceptance_timestamp"] else True
        ),
        "information_lag": (
            source["publication_lag_class"] in ALLOWED_PRIMARY_LAG_CLASSES
        ),
        "historical_revision_preservation": (
            source["historical_revision_preservation"]
            if gate["requires_historical_revision_preservation"] else True
        ),
        "point_in_time_identifier_mapping": (
            source["point_in_time_identifier_mapping"]
            if gate["requires_point_in_time_identifier_mapping"] else True
        ),
        "local_immutable_corpus": (
            any(corpus["manifest_present"] for corpus in corpora)
            if gate["requires_local_immutable_corpus_before_hypothesis"] else True
        ),
        "semantic_fit_for_intended_hypothesis": not semantic_proxy,
    }
    primary_ready = all(checks.values())
    if semantic_proxy:
        status = "REJECTED_AS_INCOMPLETE_OPTION_SURFACE_PROXY"
    elif not source["public_research_tier_compatible"]:
        status = "BLOCKED_BY_PUBLIC_RESEARCH_TIER"
    elif not checks["minimum_point_in_time_history_years"]:
        status = "PROSPECTIVE_SHADOW_AND_RECENT_SENSITIVITY_ONLY"
    elif not checks["information_lag"]:
        status = "SLOW_CONTEXT_ONLY"
    elif not checks["local_immutable_corpus"]:
        status = "COLLECTION_FEASIBLE_NOT_LOCALLY_READY"
    elif not checks["point_in_time_identifier_mapping"]:
        status = "BLOCKED_BY_IDENTIFIER_LEDGER"
    elif not checks["historical_revision_preservation"]:
        status = "BLOCKED_BY_REVISION_HISTORY"
    else:
        status = "READY_FOR_HYPOTHESIS_PREREGISTRATION" if primary_ready else "BLOCKED"
    return {
        "source": source["id"],
        "status": status,
        "history_years": years,
        "potential_non_overlapping_eras": potential_eras,
        "era_length_years": era_years,
        "pit_start": source["pit_start"],
        "pit_end": source["pit_end"],
        "cost_class": source["cost_class"],
        "publication_lag_class": source["publication_lag_class"],
        "sampling_frequency": source["sampling_frequency"],
        "local_corpora": corpora,
        "gate_checks": checks,
        "primary_oos_ready": primary_ready,
        "allowed_role": source["allowed_role_if_not_primary"],
        "direction_hypothesis_allowed": primary_ready,
        "operational_action_authority": False,
    }


def audit(protocol_path: Path = PROTOCOL) -> dict:
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    if protocol["status"] != "LOCKED_BEFORE_LOCAL_FEASIBILITY_AUDIT":
        raise ValueError("public leading-data protocol is not locked")
    prerequisite_results = _verify_prerequisites(protocol)
    decisions = [
        _source_decision(source, protocol["primary_oos_gate"])
        for source in protocol["sources"]
    ]
    ready = [
        decision["source"] for decision in decisions
        if decision["primary_oos_ready"]
    ]
    finra = next(
        decision for decision in decisions
        if decision["source"] == "FINRA_EXCHANGE_LISTED_SHORT_INTEREST"
    )
    return {
        "report_version": "PUBLIC_LEADING_DATA_FEASIBILITY_V1",
        "status": (
            "PUBLIC_PRIMARY_SOURCE_READY"
            if ready else "NO_PUBLIC_SOURCE_READY_FOR_PRIMARY_OOS"
        ),
        "protocol_sha256": _sha256(protocol_path),
        "as_of": protocol["as_of"],
        "research_tier": protocol["research_tier"],
        "prerequisites": prerequisite_results,
        "source_decisions": decisions,
        "ready_primary_sources": ready,
        "ready_primary_source_count": len(ready),
        "sec_13f_master_inventory": _master_13f_inventory(),
        "finra_recent_lane_feasible": (
            finra["status"]
            == "PROSPECTIVE_SHADOW_AND_RECENT_SENSITIVITY_ONLY"
        ),
        "new_direction_hypothesis_preregistered": False,
        "price_outcomes_opened": False,
        "herd_formula_change_allowed": False,
        "blind_holdout_access": False,
        "operational_action_authority": False,
        "operational_action_ratio": 0.0,
        "next_priority": (
            "PREREGISTER_ONE_READY_PUBLIC_SOURCE"
            if ready else
            "BUILD_FINRA_SHORT_INTEREST_IMMUTABLE_CENSUS_FOR_RECENT_SENSITIVITY_AND_PROSPECTIVE_SHADOW_ONLY"
        ),
        "stop_conditions": [
            "DO_NOT_CALL_FINRA_RECENT_LANE_PRIMARY_OOS",
            "DO_NOT_USE_13F_AS_RARE_TIMING_TRIGGER",
            "DO_NOT_SUBSTITUTE_FREE_OPTION_VOLUME_FOR_IV_OR_SKEW",
            "DO_NOT_CHANGE_HERD_OR_ACTION_RATIO"
        ],
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
