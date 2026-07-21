from herd.sec_8k_guidance_coverage_v1 import measure_text, plain_text


def test_detects_issuer_guidance_range_period_and_metric_without_direction():
    measured = measure_text(
        "For fiscal 2025, the company expects adjusted EPS in a range of $4.20 to $4.50."
    )
    assert measured == {
        "guidance_language": True, "quantitative_range": True,
        "target_period": True, "metrics": ["EPS"],
    }


def test_generic_historical_number_is_not_guidance():
    measured = measure_text("Revenue for 2024 was between $10 million and $12 million.")
    assert measured["guidance_language"] is False
    assert measured["quantitative_range"] is False


def test_html_is_reduced_to_visible_text():
    assert plain_text(b"<p>Company &amp; outlook</p><script>ignore()</script>") == "Company & outlook"
