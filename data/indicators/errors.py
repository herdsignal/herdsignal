"""지표 계산에서 데이터 품질 오류와 단순 이력 부족을 구분한다."""


class InsufficientIndicatorHistoryError(ValueError):
    """지표 공식이 요구하는 최소 관측 기간을 충족하지 못한 경우."""
