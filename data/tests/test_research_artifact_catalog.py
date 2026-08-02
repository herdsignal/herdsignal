from pathlib import Path

import pytest

from herd.research_artifact_catalog import (
    build_inventory,
    discover_artifact_paths,
    find_duplicate_chain_memberships,
    load_catalog,
    validate_active_chain,
    validate_all_chain_paths,
    validate_inventory,
)


ROOT = Path(__file__).resolve().parents[2]
V1_CATALOG = ROOT / "data" / "herd" / "research_artifact_catalog.json"
CATALOG = ROOT / "data" / "herd" / "research_artifact_catalog_v2.json"
INVENTORY = ROOT / "data" / "herd" / "research_artifact_inventory_v1.json"


def test_active_research_chain_exists() -> None:
    catalog = load_catalog(CATALOG)
    assert validate_active_chain(catalog, ROOT) == []
    assert validate_all_chain_paths(catalog, ROOT) == []


def test_v1_catalog_remains_readable_for_historical_completion_receipts() -> None:
    catalog = load_catalog(V1_CATALOG)
    assert validate_active_chain(catalog, ROOT) == []


def test_v2_catalog_has_no_conflicting_statuses() -> None:
    catalog = load_catalog(CATALOG)
    assert find_duplicate_chain_memberships(catalog) == {}
    assert catalog["current_decision"]["status"] == "STATE_OBSERVATION_MVP_READY"
    assert (
        catalog["current_decision"]["action_candidate"]
        == "NO_ADOPTABLE_ACTION_CANDIDATE"
    )
    assert catalog["current_decision"]["state_measurement"] == "HERD_STATE_S1"
    assert catalog["current_decision"]["state_display_ready"] is True
    assert catalog["current_decision"]["transition_measurement"] == "HERD_TRANSITION_S1"
    assert catalog["current_decision"]["transition_display_ready"] is True
    assert (
        catalog["current_decision"]["canonical_decision"]
        == "data/herd/research_decision_v3.json"
    )
    assert catalog["current_decision"]["personal_policy_candidate"] == "HERD_GIVEBACK_S1"
    assert catalog["current_decision"]["personal_policy_events_ready"] is True
    assert catalog["model_boundaries"]["HERD_V4"]["role"] == "LEGACY_REFERENCE_ONLY"
    assert catalog["model_boundaries"]["HERD_V6_1"]["role"] == "LEGACY_REFERENCE_ONLY"
    assert "data/reports/profit_giveback_economic_v1.json" in catalog["chains"]["REJECTED"]
    assert "data/reports/profit_giveback_economic_v1.json" not in catalog["chains"]["ACTIVE"]


def test_deletion_requires_reproducibility_checks() -> None:
    catalog = load_catalog(CATALOG)
    assert len(catalog["retention"]["delete_only_when"]) >= 4
    assert catalog["retention"]["unclassified_policy"] == "REVIEW_REQUIRED"


def test_v2_catalog_rejects_conflicting_chain_membership(tmp_path: Path) -> None:
    payload = load_catalog(CATALOG)
    payload["chains"]["DIAGNOSTIC"].append(payload["chains"]["ACTIVE"][0])
    path = tmp_path / "catalog.json"
    path.write_text(__import__("json").dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="conflicting statuses"):
        load_catalog(path)


def test_inventory_covers_current_research_artifact_names() -> None:
    import json

    catalog = load_catalog(CATALOG)
    inventory = json.loads(INVENTORY.read_text())

    assert validate_inventory(catalog, inventory, ROOT) == {
        "new_paths": [],
        "missing_paths": [],
        "status_changes": {},
    }
    assert len(discover_artifact_paths(catalog, ROOT)) == len(inventory["artifacts"])


def test_inventory_detects_unreviewed_new_artifact(tmp_path: Path) -> None:
    catalog = load_catalog(CATALOG)
    catalog["retention"]["inventory_scope"] = {
        "roots": [{"path": "reports", "extensions": [".json"]}],
        "exclude": [],
    }
    reports = tmp_path / "reports"
    reports.mkdir()
    (reports / "known.json").write_text("{}")
    inventory = build_inventory(catalog, tmp_path)
    (reports / "new.json").write_text("{}")

    assert validate_inventory(catalog, inventory, tmp_path)["new_paths"] == [
        "reports/new.json"
    ]
