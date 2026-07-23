from __future__ import annotations

import json
from pathlib import Path


V1_ALLOWED_STATUSES = {"ACTIVE", "REJECTED", "LEGACY", "DATA_PIPELINE"}
V2_ALLOWED_STATUSES = {
    "ACTIVE",
    "DATA_PIPELINE",
    "REJECTED",
    "LEGACY_REFERENCE",
    "DIAGNOSTIC",
}


def load_catalog(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    version = payload.get("version")
    allowed_statuses = (
        V2_ALLOWED_STATUSES
        if version == "HERD_RESEARCH_ARTIFACT_CATALOG_V2"
        else V1_ALLOWED_STATUSES
    )
    if set(payload.get("statuses", {})) != allowed_statuses:
        raise ValueError("artifact status vocabulary changed")
    if payload.get("retention", {}).get("unclassified_policy") != "REVIEW_REQUIRED":
        raise ValueError("unclassified artifacts must fail closed")
    if version == "HERD_RESEARCH_ARTIFACT_CATALOG_V2":
        _validate_v2_contract(payload)
    return payload


def validate_active_chain(catalog: dict, root: Path) -> list[str]:
    active_chain = catalog.get("active_chain")
    if active_chain is None:
        active_chain = catalog["chains"]["ACTIVE"]
    return [relative for relative in active_chain if not (root / relative).is_file()]


def validate_all_chain_paths(catalog: dict, root: Path) -> list[str]:
    chains = catalog.get("chains")
    if chains is None:
        return validate_active_chain(catalog, root)
    return [
        relative
        for paths in chains.values()
        for relative in paths
        if not (root / relative).is_file()
    ]


def find_duplicate_chain_memberships(catalog: dict) -> dict[str, list[str]]:
    memberships: dict[str, list[str]] = {}
    for status, paths in catalog.get("chains", {}).items():
        for relative in paths:
            memberships.setdefault(relative, []).append(status)
    return {
        relative: statuses
        for relative, statuses in memberships.items()
        if len(statuses) > 1
    }


def _validate_v2_contract(catalog: dict) -> None:
    chains = catalog.get("chains")
    if not isinstance(chains, dict) or set(chains) != V2_ALLOWED_STATUSES:
        raise ValueError("V2 catalog must define one explicit chain per status")
    duplicates = find_duplicate_chain_memberships(catalog)
    if duplicates:
        raise ValueError(f"artifacts have conflicting statuses: {duplicates}")
    boundaries = catalog.get("model_boundaries", {})
    for model in ("HERD_V4", "HERD_V6_1"):
        if boundaries.get(model, {}).get("role") != "LEGACY_REFERENCE_ONLY":
            raise ValueError(f"{model} must remain reference-only")
    if catalog.get("current_decision", {}).get("operational_action_ratio") != 0.0:
        raise ValueError("unapproved research must keep operational actions disabled")


def main() -> int:
    root = Path(__file__).resolve().parents[2]
    catalog_path = Path(__file__).with_name("research_artifact_catalog_v2.json")
    catalog = load_catalog(catalog_path)
    missing = validate_all_chain_paths(catalog, root)
    if missing:
        raise SystemExit(f"missing classified research artifacts: {', '.join(missing)}")
    print(
        json.dumps(
            {
                "status": "OK",
                "version": catalog["version"],
                "chains": {
                    status: len(paths)
                    for status, paths in catalog["chains"].items()
                },
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
