# HerdSignal 문서 안내

문서는 목적, 현재 상태, 계약, 역사 기록으로 구분한다. 같은 구현 결과를 여러
문서에 반복해서 적지 않는다. 고정 연구 산출물의 경로를 옮기면 해시·재현
원장이 깨질 수 있어 기존 경로는 보존한다.

## 현재 기준

1. [HERD_LONG_TERM_OPERATING_SYSTEM.md](HERD_LONG_TERM_OPERATING_SYSTEM.md) — 왜 만들고 어떤 판단 구조를 사용하는가
2. [CURRENT_STATE.md](CURRENT_STATE.md) — 지금 무엇이 가능하고 다음 작업은 무엇인가
3. [PRODUCT_SCOPE.md](PRODUCT_SCOPE.md) — 사용자에게 무엇을 제공하고 제공하지 않는가
4. [HERD_ADOPTION_POLICY.md](HERD_ADOPTION_POLICY.md) — 어떤 증거가 있어야 행동 권한을 여는가
5. [ARCHITECTURE.md](ARCHITECTURE.md) — 코드 책임과 변경 원칙

`CURRENT_STATE.md`와 위 문서가 충돌하면 `CURRENT_STATE.md`의 현재 운영
판정을 우선하되, 채택 수치는 `HERD_ADOPTION_POLICY.md`를 완화할 수 없다.

## 활성 연구·운영 보조 문서

- [HERD_DECISION_ARCHITECTURE.md](HERD_DECISION_ARCHITECTURE.md) — 상태·행동 우위·포트폴리오 정책 분리
- [HERD_RESEARCH_STATUS.md](HERD_RESEARCH_STATUS.md) — append-only 과거 연구 판정 일지, 현재 상태로 사용 금지
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

## 갱신 규칙

- 서비스 목적과 판단 구조 변경만 `HERD_LONG_TERM_OPERATING_SYSTEM.md`에 쓴다.
- 현재 수치와 다음 단계는 `CURRENT_STATE.md`에만 쓴다.
- 재현 명령과 입력 계약은 `HERD_REPRODUCIBLE_RESEARCH.md`에만 쓴다.
- 새 연구의 최종 판정만 `HERD_RESEARCH_STATUS.md`에 append한다. 구현 진행률은
  반복해서 적지 않는다.
- 기계 판독 가능한 수치는 JSON report가 정본이며 Markdown이 이를 덮어쓰지 않는다.

2026-08-03 전수 감사에서 동일 파일 해시와 완전 중복 문서는 없었다. 완료·탈락
문서도 `research_artifact_inventory_v1.json` 또는 V2 카탈로그가 경로를
참조하므로 삭제하지 않았다. 파일 수를 줄이기 위해 재현 근거를 제거하지 않는다.
