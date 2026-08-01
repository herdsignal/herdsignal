"""스케줄러 성공 결과와 함께 런타임 연구 상태 보고서를 최신화한다."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from scheduler.action_research_intake_gate import build_report as build_action_report
from scheduler.model_readiness_audit import load_and_build as build_readiness_report
from scheduler.prospective_evidence import DEFAULT_ARCHIVE_DIR, audit_archive


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REPORT_DIR = ROOT / "data/runtime/reports"


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def write_operational_reports(
    prospective: dict[str, Any],
    readiness: dict[str, Any],
    action_intake: dict[str, Any],
    *,
    report_dir: Path = DEFAULT_REPORT_DIR,
) -> list[Path]:
    reports = {
        "prospective-evidence-latest.json": prospective,
        "model-readiness-latest.json": readiness,
        "action-research-intake-latest.json": action_intake,
    }
    written: list[Path] = []
    for name, payload in reports.items():
        target = report_dir / name
        _atomic_json(target, payload)
        written.append(target)
    return written


def refresh_operational_reports(
    *,
    archive_dir: Path = DEFAULT_ARCHIVE_DIR,
    report_dir: Path = DEFAULT_REPORT_DIR,
) -> dict[str, Any]:
    """동일 archive를 기준으로 사용자 노출용 상태 보고서 세 개를 갱신한다."""
    prospective = audit_archive(archive_dir)
    readiness = build_readiness_report(archive_dir)
    action_intake = build_action_report(prospective)
    written = write_operational_reports(
        prospective,
        readiness,
        action_intake,
        report_dir=report_dir,
    )
    return {
        "status": "SUCCESS",
        "reports": [str(path) for path in written],
        "observationArchives": prospective["observationArchives"],
        "pendingOutcomes": prospective["pendingOutcomes"],
    }
