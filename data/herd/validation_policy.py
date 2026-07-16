"""HERD 검증에서 사용하는 변경 제한 정책."""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class ValidationPolicy:
    """운영 후보 검증은 고정값을 기본으로 하고 자동 선택은 연구용으로 격리한다."""

    mode: str = "fixed"
    fixed_ratio_scale: float = 1.0
    fixed_cooldown_days: int = 20
    candidate_ratio_scales: tuple[float, ...] = (0.8, 1.0, 1.2)
    candidate_cooldown_days: tuple[int, ...] = (15, 20, 30)

    def applied_parameters(self, selected_scale: float, selected_cooldown: int) -> tuple[float, int]:
        if self.mode == "train-selected":
            return selected_scale, selected_cooldown
        return self.fixed_ratio_scale, self.fixed_cooldown_days

    def metadata(self) -> dict:
        data = asdict(self)
        data["candidate_count"] = len(self.candidate_ratio_scales) * len(self.candidate_cooldown_days)
        data["automatic_selection_applied"] = self.mode == "train-selected"
        return data

