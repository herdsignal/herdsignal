import json
from pathlib import Path


TEST_ROOT = Path(__file__).parent
PROFILE_PATH = TEST_ROOT / "test_profiles.json"


def test_repository_profile_exclusions_are_explicit_existing_modules() -> None:
    payload = json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
    assert payload["version"] == "HERD_TEST_PROFILES_V1"
    profile = payload["profiles"]["repository"]
    excluded_modules = profile["excluded_modules"]
    excluded_tests = profile["excluded_tests"]

    assert excluded_modules
    assert excluded_tests
    assert all(reason.strip() for reason in excluded_modules.values())
    assert all(reason.strip() for reason in excluded_tests.values())
    assert all((TEST_ROOT / module).is_file() for module in excluded_modules)
    assert all(
        (TEST_ROOT / test_id.split("::", maxsplit=1)[0]).is_file()
        for test_id in excluded_tests
    )


def test_repository_profile_does_not_exclude_ordinary_unit_tests() -> None:
    payload = json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
    profile = payload["profiles"]["repository"]
    excluded = {
        *profile["excluded_modules"],
        *(test_id.split("::", maxsplit=1)[0] for test_id in profile["excluded_tests"]),
    }

    assert "test_calculator.py" not in excluded
    assert "test_storage_audit.py" not in excluded
    assert "test_test_profiles.py" not in excluded
