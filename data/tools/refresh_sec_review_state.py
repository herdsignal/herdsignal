"""사람이 판정한 SEC 8-K 정본에서 허용된 파생 연구 상태만 갱신한다."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Callable

from herd import failed_action_research_synthesis_v1 as failure
from herd import independent_evidence_role_audit_v1 as roles
from herd import role_specific_source_gap_priority_v1 as priority
from herd import runtime_evidence_role_mapping_v1 as runtime
from herd import sec_8k_identity_source_review_v1 as source_review
from herd import sec_8k_material_event_review_batching_v1 as batching
from tools.current_state_audit import build_current_state


ROOT = Path(__file__).resolve().parents[2]


class SecReviewRefreshError(ValueError):
    """허용되지 않은 해시 연결이나 상태 변경을 발견하면 발생한다."""


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_report(path: Path, report: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def replace_locked_hash(
    protocol_path: Path,
    input_path: str,
    digest: str,
) -> None:
    """정확히 하나의 허용된 path/sha256 연결만 교체한다."""
    content = protocol_path.read_text(encoding="utf-8")
    escaped_path = re.escape(json.dumps(input_path))
    pattern = re.compile(
        rf'("path"\s*:\s*{escaped_path}\s*,\s*"sha256"\s*:\s*")[0-9a-f]{{64}}(")'
    )
    updated, replacements = pattern.subn(rf"\g<1>{digest}\g<2>", content)
    if replacements != 1:
        raise SecReviewRefreshError(
            f"expected one locked hash for {input_path}, found {replacements}"
        )
    protocol_path.write_text(updated, encoding="utf-8")


def _refresh_report(
    builder: Callable[[Path], dict[str, Any]],
    protocol_path: Path,
    report_path: Path,
) -> None:
    _write_report(report_path, builder(protocol_path))


def run() -> dict[str, Any]:
    source = source_review.run()
    batch = batching.run()
    source_report = "data/reports/sec_8k_identity_source_review_v1.json"
    source_digest = _sha256(ROOT / source_report)

    for protocol_path in (
        failure.PROTOCOL,
        roles.PROTOCOL,
        priority.PROTOCOL,
    ):
        replace_locked_hash(protocol_path, source_report, source_digest)

    _refresh_report(failure.synthesize, failure.PROTOCOL, failure.REPORT)
    failure_report = "data/reports/failed_action_research_synthesis_v1.json"
    replace_locked_hash(
        roles.PROTOCOL,
        failure_report,
        _sha256(ROOT / failure_report),
    )

    _refresh_report(roles.audit, roles.PROTOCOL, roles.REPORT)
    roles_report = "data/reports/independent_evidence_role_audit_v1.json"
    replace_locked_hash(
        runtime.PROTOCOL,
        roles_report,
        _sha256(ROOT / roles_report),
    )

    _refresh_report(runtime.audit, runtime.PROTOCOL, runtime.REPORT)
    _refresh_report(priority.audit, priority.PROTOCOL, priority.REPORT)

    state = build_current_state()
    if state["status"] != "PASS":
        raise SecReviewRefreshError("current-state audit failed after refresh")
    if state["action_research"]["operational_action_ratio"] != 0.0:
        raise SecReviewRefreshError("refresh unexpectedly opened action authority")
    return {
        "status": "PASS",
        "reviewed": batch["rows"]
        - sum(item["pending"] for item in batch["batches"]),
        "total": batch["rows"],
        "next_batch": batch["next_pending_batch"],
        "source_review_status": source["status"],
        "identity_promotion_allowed": source["identity_promotion_allowed"],
        "operational_action_ratio": 0.0,
    }


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False, indent=2))
