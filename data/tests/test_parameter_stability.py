import unittest

from herd.parameter_stability import analyze_parameter_stability


def row(year, scale, cooldown, result=10):
    return {"ticker": "SPY", "mode": "rolling", "test_start": year,
            "ratio_scale": scale, "cooldown_days": cooldown,
            "v61_return": result, "v61_mdd": -10}


class ParameterStabilityTest(unittest.TestCase):
    def test_recommends_fixed_parameters_when_selection_changes(self):
        rows = [row(2020, 0.8, 15), row(2021, 1.0, 20), row(2022, 1.2, 30)]
        result = analyze_parameter_stability(rows)
        self.assertEqual(result["transition_stability"]["same_parameter_rate"], 0)
        self.assertEqual(result["recommendation"], "USE_FIXED_PARAMETERS")

    def test_accepts_consistent_selection(self):
        rows = [row(year, 1.0, 20) for year in range(2020, 2025)]
        result = analyze_parameter_stability(rows)
        self.assertEqual(result["recommendation"], "AUTO_SELECTION_ACCEPTABLE")
        self.assertEqual(result["ratio_scale_frequency"]["1.0"]["rate"], 100)

    def test_flags_isolated_objective_spike(self):
        rows = [row(2020, 1.0, 20, 30), row(2021, 0.8, 20, 10)]
        self.assertTrue(analyze_parameter_stability(rows)["single_parameter_spike"])


if __name__ == "__main__": unittest.main()
