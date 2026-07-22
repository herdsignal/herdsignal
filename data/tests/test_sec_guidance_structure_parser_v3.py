from pathlib import Path

import pandas as pd

from herd.sec_guidance_block_extraction_v1 import load_aliases
from herd.sec_guidance_structure_parser_v3 import parse_block_v3
from herd.sec_guidance_structure_parser_v3 import build_from_v2_ledger
import json


ROOT = Path(__file__).resolve().parents[2]
ALIASES = load_aliases(ROOT / "data/herd/sec_guidance_metric_aliases_v1.csv")


def _review_rows() -> pd.DataFrame:
    return pd.read_csv(ROOT / "data/reports/sec_guidance_structure_reviewed_v2.csv")


def _matches(row: pd.Series) -> bool:
    candidates = parse_block_v3(row["block_text"], row["ticker"], ALIASES)
    return any(
        candidate["metric"] == row["metric"]
        and candidate["fiscal_period"] == row["fiscal_period"]
        and candidate["lower_bound"] == row["lower_bound"]
        and candidate["upper_bound"] == row["upper_bound"]
        for candidate in candidates
    )


def test_v3_removes_known_comparison_period_failures() -> None:
    rows = _review_rows().set_index("review_id")
    for review_id in [f"SG2-{number:04d}" for number in range(59, 69)]:
        assert not _matches(rows.loc[review_id])


def test_v3_removes_wrong_metric_and_scale_failures() -> None:
    rows = _review_rows().set_index("review_id")
    for review_id in ("SG2-0013", "SG2-0014", "SG2-0022", "SG2-0050", "SG2-0072"):
        assert not _matches(rows.loc[review_id])


def test_v3_retains_explicit_current_guidance_examples() -> None:
    rows = _review_rows().set_index("review_id")
    for review_id in ("SG2-0001", "SG2-0015", "SG2-0037", "SG2-0051", "SG2-0075"):
        assert _matches(rows.loc[review_id])


def test_v3_fresh_sample_excludes_all_v1_v2_accessions() -> None:
    protocol = json.loads((ROOT / "data/herd/sec_guidance_structure_parser_v3.json").read_text())
    candidates, review, report = build_from_v2_ledger(
        ROOT / protocol["v2_candidate_ledger"], ALIASES, protocol,
    )
    excluded = set()
    for path in protocol["development_reviews"]:
        excluded.update(pd.read_csv(ROOT / path)["accession_number"].astype(str))

    assert not set(review["accession_number"].astype(str)) & excluded
    assert report["review_sample_gate_ready"] is False
    assert report["next_decision"] == "FRESH_REVIEW_SAMPLE_COVERAGE_BLOCKED"
    assert len(candidates) > len(review)
