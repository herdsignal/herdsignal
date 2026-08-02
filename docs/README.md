# HerdSignal 문서 안내

문서는 경로보다 역할과 상태로 구분한다. 고정 연구 산출물의 경로를 옮기면
해시·재현 원장이 깨질 수 있어 현재는 최상위에 보존한다. 현재 구현 판단은
아래 여섯 문서만 순서대로 읽는다.

## 현재 기준

1. [HERD_LONG_TERM_OPERATING_SYSTEM.md](HERD_LONG_TERM_OPERATING_SYSTEM.md) — 서비스 목적과 장기 운용 판단 체계
2. [CURRENT_STATE.md](CURRENT_STATE.md) — 현재 제품·연구 판정과 다음 허용 작업
3. [PRODUCT_SCOPE.md](PRODUCT_SCOPE.md) — 사용자, 핵심 흐름, 제공·비제공 범위
4. [HERD_MODEL_CHARTER.md](HERD_MODEL_CHARTER.md) — 모델 목표와 경계
5. [HERD_ADOPTION_POLICY.md](HERD_ADOPTION_POLICY.md) — 행동 모델 채택 기준
6. [ARCHITECTURE.md](ARCHITECTURE.md) — 현재 코드 구조와 변경 원칙

`CURRENT_STATE.md`와 위 문서가 충돌하면 `CURRENT_STATE.md`의 현재 운영
판정을 우선하되, 채택 수치는 `HERD_ADOPTION_POLICY.md`를 완화할 수 없다.

## 활성 연구·운영 보조 문서

- [HERD_DECISION_ARCHITECTURE.md](HERD_DECISION_ARCHITECTURE.md) — 상태·행동 우위·포트폴리오 정책 분리
- [HERD_RESEARCH_STATUS.md](HERD_RESEARCH_STATUS.md) — append-only 누적 연구 판정 일지
- [HERD_AI_EVIDENCE_REVIEW.md](HERD_AI_EVIDENCE_REVIEW.md) — 출처 제한 AI 연구 프로토타입
- [HERD_ACTION_HYPOTHESIS_V1.md](HERD_ACTION_HYPOTHESIS_V1.md) — 잠긴 전향 행동 가설

## 데이터와 재현 계약

- [HERD_REPRODUCIBLE_RESEARCH.md](HERD_REPRODUCIBLE_RESEARCH.md) — 입력, fold, 비용, 재현 절차
- [HERD_POINT_IN_TIME_DATA.md](HERD_POINT_IN_TIME_DATA.md) — SEC·구성 종목 PIT 상태
- [HERD_CONSTITUENT_EVENT_RESOLUTION.md](HERD_CONSTITUENT_EVENT_RESOLUTION.md) — 과거 구성 사건 해결 현황
- [HERD_OOS_EVIDENCE_PROTOCOL.md](HERD_OOS_EVIDENCE_PROTOCOL.md) — 독립 OOS 증거 계약
- [HERD_ARTIFACT_CATALOG.md](HERD_ARTIFACT_CATALOG.md) — 산출물 분류와 보존 기준

## 완료·탈락 연구 기록 — 현재 구현 입력 금지

- [HERD_S1_PRODUCTIZATION_PLAN.md](HERD_S1_PRODUCTIZATION_PLAN.md) — State S1 제품 연결 기록
- [HERD_BUSINESS_GUARD_STUDY.md](HERD_BUSINESS_GUARD_STUDY.md) — 기업 상태 가설 결과
- [HERD_RUSH_TURNING_POINT_STUDY.md](HERD_RUSH_TURNING_POINT_STUDY.md) — Rush 전환점 가설 결과

이 문서들은 실패를 포함한 연구 경로를 재현하기 위해 보존한다. 오래된
수치나 파서 버전이 최신 결론과 충돌하면 `HERD_RESEARCH_STATUS.md` 상단과
기계 판독 결정 원장을 우선한다.

## 정리 규칙

- `APPROVED`, `LOCKED`, `CURRENT`: 현재 기준 또는 변경 금지 계약
- `RESEARCH_ONLY`, `SOURCE_VALIDATION`: 운영 권한 없는 연구·데이터 문서
- `REJECTED`, `HISTORICAL`: 재현을 위해 보존하되 신규 구현 입력 금지
- `COMPLETED`: 완료 기록이며 현재 요구사항을 정의하지 않음
- 코드·JSON·다른 문서에서 참조되는 연구 문서는 이름과 경로를 유지한다.
- 최종 구현 후 참조가 없고 다른 문서에 내용이 흡수된 파일만 삭제한다.
