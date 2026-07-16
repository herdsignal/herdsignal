"""스케줄러 장애를 외부 웹훅으로 전달한다."""

from __future__ import annotations

import logging
from dataclasses import dataclass

import requests

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class IncidentAlertConfig:
    webhook_url: str = ""
    notify_success: bool = False
    timeout_seconds: float = 5.0


def build_scheduler_message(result: dict) -> str | None:
    status = result.get("status", "UNKNOWN")
    total = int(result.get("total", 0))
    failed = list(result.get("failed") or [])
    if status == "SUCCESS":
        return f"[HerdSignal] 스케줄러 완료 · {total}개 종목 갱신"
    failed_summary = ", ".join(failed[:10]) if failed else "전체 작업"
    suffix = f" 외 {len(failed) - 10}개" if len(failed) > 10 else ""
    return (
        f"[HerdSignal] 스케줄러 {status} · 성공 {len(result.get('success') or [])}/{total} · "
        f"확인 대상: {failed_summary}{suffix}"
    )


def send_scheduler_alert(result: dict, config: IncidentAlertConfig) -> bool:
    """설정되지 않았거나 성공 알림이 꺼져 있으면 아무 작업도 하지 않는다."""
    if not config.webhook_url:
        return False
    if result.get("status") == "SUCCESS" and not config.notify_success:
        return False

    message = build_scheduler_message(result)
    if not message:
        return False
    try:
        response = requests.post(
            config.webhook_url,
            json={"text": message, "content": message},
            timeout=config.timeout_seconds,
        )
        response.raise_for_status()
        return True
    except requests.RequestException as exc:
        logger.error("[Alert] 장애 알림 전송 실패: %s", exc)
        return False

