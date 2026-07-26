"""Tier1 저장 전에 가격 프레임의 운영 불변식을 강제한다."""

from __future__ import annotations

from datetime import date

import pandas as pd

from herd.data_quality_audit import audit_price_frame


class DataQualityGateError(ValueError):
    pass


def validate_operational_price_frame(
    ticker: str,
    frame: pd.DataFrame,
    *,
    as_of: date | None = None,
) -> dict:
    report = audit_price_frame(
        frame,
        as_of=as_of or date.today(),
        minimum_rows=1,
        maximum_staleness_days=7,
    )
    if report["passed"]:
        return report
    failed_checks = sorted(
        name for name, passed in report.get("checks", {}).items() if not passed
    )
    if not failed_checks and report.get("missing_columns"):
        failed_checks = [f"missing:{name}" for name in report["missing_columns"]]
    raise DataQualityGateError(
        f"{ticker} 가격 품질 게이트 실패: {', '.join(failed_checks) or report['status']}"
    )
