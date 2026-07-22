from pathlib import Path

from herd.research_artifact_catalog import load_catalog, validate_active_chain


ROOT = Path(__file__).resolve().parents[2]
CATALOG = ROOT / "data" / "herd" / "research_artifact_catalog.json"


def test_active_research_chain_exists() -> None:
    catalog = load_catalog(CATALOG)
    assert validate_active_chain(catalog, ROOT) == []


def test_deletion_requires_reproducibility_checks() -> None:
    catalog = load_catalog(CATALOG)
    assert len(catalog["retention"]["delete_only_when"]) >= 4
    assert catalog["retention"]["unclassified_policy"] == "REVIEW_REQUIRED"
