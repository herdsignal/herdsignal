"""로컬 대용량 corpus와 저장소 재현 테스트의 실행 경계를 정의한다."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

PROFILE_ENV = "HERD_TEST_PROFILE"
DEFAULT_PROFILE = "full"
PROFILE_PATH = Path(__file__).with_name("test_profiles.json")


def _load_profiles() -> dict:
    return json.loads(PROFILE_PATH.read_text(encoding="utf-8"))["profiles"]


def _selected_profile() -> str:
    return os.getenv(PROFILE_ENV, DEFAULT_PROFILE).strip().lower()


def pytest_configure(config: pytest.Config) -> None:
    profile = _selected_profile()
    if profile != DEFAULT_PROFILE and profile not in _load_profiles():
        raise pytest.UsageError(
            f"unknown {PROFILE_ENV}={profile!r}; "
            f"expected one of: {DEFAULT_PROFILE}, {', '.join(_load_profiles())}"
        )


def pytest_ignore_collect(collection_path: Path, config: pytest.Config) -> bool:
    profile = _selected_profile()
    if profile == DEFAULT_PROFILE:
        return False
    excluded = _load_profiles()[profile]["excluded_modules"]
    return collection_path.name in excluded


def pytest_collection_modifyitems(
    config: pytest.Config,
    items: list[pytest.Item],
) -> None:
    profile = _selected_profile()
    if profile == DEFAULT_PROFILE:
        return
    excluded = _load_profiles()[profile]["excluded_tests"]
    reason = f"{profile} profile: local immutable corpus required"
    for item in items:
        key = f"{item.path.name}::{item.name}"
        if key in excluded:
            item.add_marker(pytest.mark.skip(reason=reason))


def pytest_report_header(config: pytest.Config) -> str:
    profile = _selected_profile()
    if profile == DEFAULT_PROFILE:
        return "HERD test profile: full (local immutable corpora required)"
    specification = _load_profiles()[profile]
    return (
        f"HERD test profile: {profile} "
        f"({len(specification['excluded_modules'])} modules, "
        f"{len(specification['excluded_tests'])} corpus tests excluded)"
    )
