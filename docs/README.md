# HerdSignal 문서 안내

문서가 많아 보여도 모두 같은 역할을 하지 않는다. 현재 제품 판단은 아래
순서로 읽고, 버전별 실패 기록은 재현 이력으로만 사용한다.

## 현재 기준

1. [PRODUCT_SCOPE.md](PRODUCT_SCOPE.md) — 사용자, 핵심 흐름, 제공·비제공 범위
2. [HERD_MODEL_CHARTER.md](HERD_MODEL_CHARTER.md) — 모델 목표와 경계
3. [HERD_ADOPTION_POLICY.md](HERD_ADOPTION_POLICY.md) — 행동 모델 채택 기준
4. [HERD_RESEARCH_STATUS.md](HERD_RESEARCH_STATUS.md) — 상단의 최신 연구 판정
5. [ARCHITECTURE.md](ARCHITECTURE.md) — 현재 코드 구조와 변경 원칙

## 데이터와 재현 계약

- [HERD_REPRODUCIBLE_RESEARCH.md](HERD_REPRODUCIBLE_RESEARCH.md) — 입력, fold, 비용, 재현 절차
- [HERD_POINT_IN_TIME_DATA.md](HERD_POINT_IN_TIME_DATA.md) — SEC·구성 종목 PIT 상태
- [HERD_CONSTITUENT_EVENT_RESOLUTION.md](HERD_CONSTITUENT_EVENT_RESOLUTION.md) — 과거 구성 사건 해결 현황
- [HERD_OOS_EVIDENCE_PROTOCOL.md](HERD_OOS_EVIDENCE_PROTOCOL.md) — 독립 OOS 증거 계약
- [HERD_ARTIFACT_CATALOG.md](HERD_ARTIFACT_CATALOG.md) — 산출물 분류와 보존 기준

## 완료·탈락 연구 기록

- [HERD_S1_PRODUCTIZATION_PLAN.md](HERD_S1_PRODUCTIZATION_PLAN.md) — State S1 제품 연결 기록
- [HERD_BUSINESS_GUARD_STUDY.md](HERD_BUSINESS_GUARD_STUDY.md) — 기업 상태 가설 결과
- [HERD_RUSH_TURNING_POINT_STUDY.md](HERD_RUSH_TURNING_POINT_STUDY.md) — Rush 전환점 가설 결과

이 문서들은 실패를 포함한 연구 경로를 재현하기 위해 보존한다. 오래된
수치나 파서 버전이 최신 결론과 충돌하면 `HERD_RESEARCH_STATUS.md` 상단과
기계 판독 결정 원장을 우선한다.
