"""HERD 계산 실패를 운영 장애와 입력 적격성 제외로 구분한다."""

from __future__ import annotations


class InsufficientModelHistoryError(RuntimeError):
    """모델 계약이 요구하는 최소 가격 이력을 충족하지 못한 경우."""

    def __init__(self, ticker: str, indicators: list[str], details: list[str]):
        self.ticker = ticker.upper()
        self.indicators = tuple(indicators)
        self.details = tuple(details)
        super().__init__(
            f"[{self.ticker}] 모델 최소 이력 미달 "
            f"({', '.join(self.indicators)}): {'; '.join(self.details)}"
        )
