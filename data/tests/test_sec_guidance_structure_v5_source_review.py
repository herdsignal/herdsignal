import json
from pathlib import Path

import pandas as pd

from herd.sec_guidance_block_source_review_v1 import adjudicate


ROOT = Path(__file__).resolve().parents[2]


def test_v5_source_review_is_complete_independent_and_fail_closed() -> None:
    config = json.loads((ROOT / "data/herd/sec_guidance_structure_v5_review.json").read_text())
    protocol = json.loads((ROOT / "data/herd/sec_guidance_structure_parser_v5.json").read_text())
    reviewed, report = adjudicate(
        ROOT / config["review_template"], ROOT / config["labels"], config, protocol,
    )
    v4_accessions = set(pd.read_csv(ROOT / "data/reports/sec_guidance_structure_v4_reviewed.csv")["accession_number"].astype(str))
    assert len(reviewed) == 80
    assert reviewed["ticker"].nunique() >= 20
    assert set(reviewed["accession_number"].astype(str)).isdisjoint(v4_accessions)
    assert report["reviewed_rows"] == 80
    assert report["review_gate_passed"] is False
    assert report["price_outcomes_observed"] is False
