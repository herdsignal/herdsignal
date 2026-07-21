from herd.cycle_value_protocol_v1 import load_protocol


def test_cycle_value_contract_is_locked_and_non_executable():
    protocol = load_protocol()
    assert protocol["execution"]["profit_take_fraction"] == 0.05
    assert protocol["ceilings"]["constrained_oracle"]["minimum_net_discount_from_sale_execution"] == 0.03
    assert protocol["ceilings"]["constrained_oracle"]["minimum_consecutive_qualifying_sessions"] == 3
    assert protocol["interpretation"]["future_low_is_never_a_feature"] is True
    assert protocol["interpretation"]["oracle_result_does_not_authorize_action"] is True
    assert protocol["interpretation"]["feasibility_pass_only_allows_new_target_research"] is True
