import pandas as pd

from herd.rush_feature_selection_v1 import build_selection


def test_near_miss_is_a_lead_but_not_admitted():
    columns = {
        "feature":["A"], "rank_biserial":[.25], "same_direction_halves":[2],
        "retained_for_preregistration":[False]
    }
    table, report = build_selection(pd.DataFrame(columns), pd.DataFrame(columns))
    assert report["retained_count"] == 0
    assert report["research_leads_not_admitted"] == ["A"]
    assert set(table["selection_status"]) == {"RESEARCH_LEAD_NOT_ADMITTED"}
