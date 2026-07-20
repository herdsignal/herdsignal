"""공식 지수 문서의 복수 주식 클래스 표기를 개별 티커 사건으로 정규화한다."""

from __future__ import annotations

import re


class ShareClassNormalizationError(RuntimeError):
    pass


TICKER = re.compile(r"^[A-Z][A-Z0-9.-]{0,9}$")


def split_share_classes(value: str) -> list[str]:
    raw = value.strip().upper()
    if "/" not in raw:
        if not TICKER.fullmatch(raw):
            raise ShareClassNormalizationError(f"invalid ticker: {value}")
        return [raw]
    values = [part.strip() for part in raw.split("/")]
    if (
        len(values) < 2
        or len(values) != len(set(values))
        or any(not TICKER.fullmatch(part) for part in values)
    ):
        raise ShareClassNormalizationError(f"invalid multi-class ticker: {value}")
    return values


def normalize_share_class_events(rows: list[dict]) -> tuple[list[dict], dict]:
    normalized = []
    expanded_rows = 0
    for row in rows:
        tickers = split_share_classes(row["ticker"])
        if len(tickers) > 1:
            expanded_rows += 1
        for ticker in tickers:
            normalized.append({
                **row,
                "ticker": ticker,
                "source_ticker_expression": row["ticker"],
            })
    keys = [
        (row["effective_date"], row["action"], row["ticker"])
        for row in normalized
    ]
    if len(keys) != len(set(keys)):
        raise ShareClassNormalizationError(
            "share-class expansion created duplicate official events"
        )
    return normalized, {
        "source_events": len(rows),
        "normalized_events": len(normalized),
        "expanded_source_events": expanded_rows,
    }
