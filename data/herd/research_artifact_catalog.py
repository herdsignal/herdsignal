from __future__ import annotations

import argparse
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
INVENTORY_VERSION = "HERD_RESEARCH_ARTIFACT_INVENTORY_V1"
REVIEW_REQUIRED = "REVIEW_REQUIRED"


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


def discover_artifact_paths(catalog: dict, root: Path) -> list[str]:
    """카탈로그가 관리하도록 선언한 연구 산출물을 결정적으로 찾는다."""
    scope = catalog.get("retention", {}).get("inventory_scope", {})
    excluded = set(scope.get("exclude", []))
    discovered: set[str] = set()
    for rule in scope.get("roots", []):
        base = root / rule["path"]
        extensions = set(rule["extensions"])
        if not base.is_dir():
            continue
        for path in base.iterdir():
            relative = path.relative_to(root).as_posix()
            if path.is_file() and path.suffix in extensions and relative not in excluded:
                discovered.add(relative)
    return sorted(discovered)


def build_inventory(catalog: dict, root: Path) -> dict:
    memberships = {
        relative: status
        for status, paths in catalog["chains"].items()
        for relative in paths
    }
    return {
        "version": INVENTORY_VERSION,
        "catalog_version": catalog["version"],
        "artifacts": [
            {
                "path": relative,
                "status": memberships.get(relative, REVIEW_REQUIRED),
            }
            for relative in discover_artifact_paths(catalog, root)
        ],
    }


def validate_inventory(catalog: dict, inventory: dict, root: Path) -> dict:
    """새 파일·삭제·상태 변경을 명시적인 검토 전까지 차단한다."""
    if inventory.get("version") != INVENTORY_VERSION:
        raise ValueError("artifact inventory version changed")
    expected = {
        item["path"]: item["status"]
        for item in inventory.get("artifacts", [])
    }
    actual_inventory = build_inventory(catalog, root)
    actual = {
        item["path"]: item["status"]
        for item in actual_inventory["artifacts"]
    }
    return {
        "new_paths": sorted(set(actual) - set(expected)),
        "missing_paths": sorted(set(expected) - set(actual)),
        "status_changes": {
            path: {"expected": expected[path], "actual": actual[path]}
            for path in sorted(set(expected) & set(actual))
            if expected[path] != actual[path]
        },
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
    scope = catalog.get("retention", {}).get("inventory_scope", {})
    if not scope.get("roots"):
        raise ValueError("V2 catalog must define artifact inventory scope")


def main() -> int:
    parser = argparse.ArgumentParser(description="HERD 연구 산출물 카탈로그 검증")
    parser.add_argument(
        "--refresh-inventory",
        action="store_true",
        help="현재 파일 집합을 검토 완료 상태의 inventory로 갱신",
    )
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    catalog_path = Path(__file__).with_name("research_artifact_catalog_v2.json")
    inventory_path = Path(__file__).with_name("research_artifact_inventory_v1.json")
    catalog = load_catalog(catalog_path)
    missing = validate_all_chain_paths(catalog, root)
    if missing:
        raise SystemExit(f"missing classified research artifacts: {', '.join(missing)}")
    if args.refresh_inventory:
        inventory_path.write_text(
            json.dumps(build_inventory(catalog, root), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    drift = validate_inventory(catalog, inventory, root)
    if any(drift.values()):
        raise SystemExit(
            "research artifact inventory review required: "
            + json.dumps(drift, ensure_ascii=False)
        )
    print(
        json.dumps(
            {
                "status": "OK",
                "version": catalog["version"],
                "chains": {
                    status: len(paths)
                    for status, paths in catalog["chains"].items()
                },
                "inventory_artifacts": len(inventory["artifacts"]),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
