"""해시가 검증된 운영 사건으로 최근 실행 요약을 생성한다."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

_DATA_DIR = Path(__file__).resolve().parent.parent
if str(_DATA_DIR) not in sys.path:
    sys.path.insert(0, str(_DATA_DIR))

from scheduler.operation_log import SCHEMA_VERSION


def load_verified_events(directory: Path) -> list[dict[str, Any]]:
    events = []
    for path in sorted(directory.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        digest = payload.pop("contentSha256", None)
        canonical = json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        if payload.get("schemaVersion") != SCHEMA_VERSION:
            raise ValueError(f"지원하지 않는 운영 로그 형식: {path.name}")
        if digest != hashlib.sha256(canonical).hexdigest():
            raise ValueError(f"운영 로그 해시 불일치: {path.name}")
        events.append(payload)
    return events


def build_weekly_report(
    events: list[dict[str, Any]],
    *,
    now: datetime,
    days: int = 7,
) -> dict[str, Any]:
    end = now.astimezone(UTC)
    start = end - timedelta(days=days)
    selected = [
        event for event in events
        if start <= datetime.fromisoformat(
            event["recordedAt"].replace("Z", "+00:00")
        ) <= end
    ]
    statuses = Counter(event["result"].get("status", "UNKNOWN") for event in selected)
    completed = [event for event in selected if event["result"].get("total", 0) > 0]
    total_requested = sum(int(event["result"].get("total", 0)) for event in completed)
    total_succeeded = sum(
        len(event["result"].get("success", [])) for event in completed
    )
    failed_tickers = Counter(
        ticker
        for event in selected
        for ticker in event["result"].get("failed", [])
    )
    skipped_tickers = Counter(
        ticker
        for event in selected
        for ticker in event["result"].get("skipped", [])
    )
    return {
        "schemaVersion": "HERD_WEEKLY_OPERATIONS_V1",
        "generatedAt": end.isoformat().replace("+00:00", "Z"),
        "period": {
            "start": start.isoformat().replace("+00:00", "Z"),
            "end": end.isoformat().replace("+00:00", "Z"),
            "days": days,
        },
        "runCount": len(selected),
        "statusCounts": dict(sorted(statuses.items())),
        "tickerExecution": {
            "requested": total_requested,
            "succeeded": total_succeeded,
            "successRate": (
                round(total_succeeded / total_requested, 6)
                if total_requested else None
            ),
            "failed": dict(sorted(failed_tickers.items())),
            "skipped": dict(sorted(skipped_tickers.items())),
        },
        "latestResult": selected[-1]["result"] if selected else None,
    }


def render_markdown(report: dict[str, Any]) -> str:
    execution = report["tickerExecution"]
    rate = execution["successRate"]
    rate_text = "—" if rate is None else f"{rate * 100:.1f}%"
    return "\n".join([
        "# HerdSignal 주간 운영 보고",
        "",
        f"- 생성: {report['generatedAt']}",
        f"- 실행: {report['runCount']}회",
        f"- 종목 처리 성공률: {rate_text}",
        f"- 상태: {json.dumps(report['statusCounts'], ensure_ascii=False)}",
        f"- 실패 종목: {json.dumps(execution['failed'], ensure_ascii=False)}",
        f"- 적격성 제외: {json.dumps(execution['skipped'], ensure_ascii=False)}",
        "",
    ])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--days", type=int, default=7)
    args = parser.parse_args()
    if args.days < 1:
        raise ValueError("days는 1 이상이어야 합니다.")
    report = build_weekly_report(
        load_verified_events(args.input),
        now=datetime.now(UTC),
        days=args.days,
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "weekly-latest.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (args.output_dir / "weekly-latest.md").write_text(
        render_markdown(report),
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
