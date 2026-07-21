import numpy as np
import pandas as pd

from herd.peer_cluster_breadth_v1 import leave_one_out_share, load_protocol


def test_subject_is_excluded_from_peer_share():
    indicator = pd.DataFrame({"A": [1.0], "B": [0.0], "C": [1.0]})
    result = leave_one_out_share(indicator, minimum_peers=2)
    assert result["A"].iloc[0] == 0.5
    assert result["B"].iloc[0] == 1.0


def test_insufficient_peer_count_is_missing():
    indicator = pd.DataFrame({"A": [1.0], "B": [np.nan], "C": [0.0]})
    result = leave_one_out_share(indicator, minimum_peers=2)
    assert result["A"].isna().iloc[0]


def test_protocol_preserves_survivorship_claim_boundary():
    protocol = load_protocol()
    assert protocol["claim_boundary"] == "CURRENT_CONSTITUENTS_ROBUSTNESS_ONLY"
    assert "CLAIM_SURVIVORSHIP_SAFE" in protocol["forbidden"]
