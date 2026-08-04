"""현재 HERD 연구 경계를 사람이 빠르게 읽을 수 있게 요약한다."""

from __future__ import annotations

import argparse
import json
from typing import Any

from tools.current_state_audit import build_current_state


def build_summary(state: dict[str, Any]) -> dict[str, Any]:
    batches = state["sec_8k_review_batches"]
    boundary = state["research_boundary"]
    reviewed = batches["rows"] - boundary["pending_sec_identity_reviews"]
    return {
        "audit_status": state["status"],
        "state_model": state["product"]["state_model"],
        "operational_action": state["action_research"]["default_action"],
        "operational_action_ratio": state["action_research"][
            "operational_action_ratio"
        ],
        "adoptable_action_candidates": state["action_research"][
            "adoptable_candidates"
        ],
        "sec_review": {
            "reviewed": reviewed,
            "total": batches["rows"],
            "pending": boundary["pending_sec_identity_reviews"],
            "next_batch": batches["next_pending_batch"],
        },
        "next_stage": boundary["next_stage"],
        "contradictions": state["contradictions"],
    }


def format_text(summary: dict[str, Any]) -> str:
    sec = summary["sec_review"]
    action = (
        f"{summary['operational_action']} "
        f"({summary['operational_action_ratio']:.0%})"
    )
    lines = [
        f"감사: {summary['audit_status']}",
        f"상태 모델: {summary['state_model']}",
        f"운영 행동: {action}",
        f"채택된 행동 후보: {summary['adoptable_action_candidates']}",
        (
            "SEC 원문 검수: "
            f"{sec['reviewed']}/{sec['total']} 완료 · {sec['pending']}건 남음"
        ),
        f"다음 배치: {sec['next_batch'] or 'COMPLETE'}",
        f"다음 단계: {summary['next_stage']}",
    ]
    if summary["contradictions"]:
        lines.append(f"모순: {len(summary['contradictions'])}건")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="JSON으로 출력")
    args = parser.parse_args()
    summary = build_summary(build_current_state())
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print(format_text(summary))
    return 0 if summary["audit_status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
