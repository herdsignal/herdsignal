import json
from pathlib import Path

import pandas as pd

from herd.sec_guidance_v6_second_wave import select_second_wave
from herd.sec_guidance_v6_third_wave import select_third_wave


ROOT = Path(__file__).resolve().parents[2]


def test_second_wave_is_outcome_blind_and_unreviewed() -> None:
    protocol = json.loads((ROOT / "data/herd/sec_guidance_v6_second_wave.json").read_text())
    universe, catalog, report = select_second_wave(protocol)
    assert len(universe) == 23
    assert len(catalog) == 819
    assert report["selection_used_guidance_text"] is False
    assert report["selection_used_parser_output"] is False
    assert report["selection_used_price_outcomes"] is False


def test_third_wave_extends_locked_sector_rotation_order() -> None:
    universe, report = select_third_wave()
    locked = set(pd.read_csv(ROOT / "data/reports/sec_guidance_v5_broad_metadata_universe.csv")["ticker"].astype(str))
    assert len(universe) == 30
    assert set(universe["ticker"].astype(str)).isdisjoint(locked)
    assert report["selection_used_guidance_text"] is False
    assert report["selection_used_parser_output"] is False
    assert report["selection_used_price_outcomes"] is False
