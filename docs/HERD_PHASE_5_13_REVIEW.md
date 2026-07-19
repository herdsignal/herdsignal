# HERD 5~13단계 최종 리뷰

검토일: 2026-07-19

## 최종 판정

차세대 HERD 운영 승격 후보는 없다. v4, Python v6.1, B0~B4 모두 사전
고정한 Buy & Hold 초과 수익 기준을 통과하지 못했다. 기존 운영 응답은
유지하고 차세대 shadow mode는 비활성 상태로 잠갔다.

| 모델 | 중앙 초과 CAGR | 양수 종목 비율 | 판정 |
|---|---:|---:|---|
| 기존 v4 행동 | -2.25%p | 25.5% | 실패 |
| Python v6.1 | -2.59%p | 12.7% | 실패 |
| B0 | -0.20%p | 43.6% | 실패 |
| B1 | -1.84%p | 12.7% | 실패 |
| B2 | -2.18%p | 14.5% | 실패 |
| B3 | -2.36%p | 10.9% | 실패 |
| B4 | - | - | PIT 데이터 부재 |

B2·B3은 MDD를 각각 2.49%p, 3.19%p 개선했지만 장기 상승 복리를 더 많이
잃었다. 현재 목표인 비용 차감 후 Buy & Hold 초과를 달성하지 못했다.

## 이번 단계에서 해결한 오류

1. 과최적화 지표가 0~100을 반환하고 채택 게이트는 0~1로 비교하던 단위
   오류를 수정했다.
2. 월말 후보 비중을 매일 반복 적용해 과도한 회전율을 만들던 리밸런싱
   오류를 수정했다.
3. Python 저장·포트폴리오·스케줄러 모듈이 import 시 DB에 연결하던 구조를
   지연 초기화로 바꿨다.
4. 개인 투자 설정을 HERD 시장 판단과 분리해 행동 비율의 상한만 조정하게
   했다.
5. 검증 실패 모델은 설정을 켜도 후보 ID와 holdout 통과가 없으면 shadow
   mode에 진입하지 못하게 했다.

## 전체 검증

- Backend: 46 tests, 0 failures
- Python: 90 tests, 0 failures
- Frontend: 28 tests, 0 failures
- Frontend ESLint: 통과
- Frontend production build: 통과
- Git diff whitespace 검사: 통과

React Router v7 future-flag 경고 2종은 테스트 실패가 아니며 현재 동작에는
영향이 없다.

## 유지보수 진단

### 우선 수정

- `ActionDecisionService.java`는 876줄이다. 개인 번역은 분리했지만 추세,
  모멘텀, lifecycle, confidence, regime, cooldown, portfolio 제한이 한
  클래스에 남아 있다. 다음 리팩터링은 계산 결과를 바꾸지 않는 특성화
  테스트를 먼저 만든 뒤 `MarketRegimeEvaluator`, `ActionRiskGate`,
  `CooldownPolicy` 순으로 분리해야 한다.
- `Dashboard.module.css`는 3,206줄, `Dashboard.jsx`는 502줄이다. 화면
  섹션별 CSS module 분리와 SPY 시장 화면/포트폴리오 화면의 책임 분리가
  필요하다.
- `StockDetail.jsx`는 529줄이다. 이미 일부 하위 컴포넌트가 있으므로
  Action Layer와 신뢰도 영역을 추가 분리할 수 있다.

### 연구 인프라

- 차세대 후보 보고서에 일별 수익 시계열과 시간축 fold가 없어 정식
  Walk-forward·시대별 DSR을 수행하지 못했다.
- 현존 55종목, 조정 가격 중심이라 생존자 편향·기업행동 원천 대조가 남아
  있다.
- `backtest_action_layer.py`, `backtest_validation_v2.py`,
  `history_backfill.py`, `setup_sp500_tickers.py`는 아직 import 시 DB를
  초기화한다. 현재 CLI 실행에는 문제가 없지만 재사용 가능한 모듈로 만들
  때 같은 지연 초기화가 필요하다.
- 55종목 데이터를 단계별로 반복 다운로드한다. 다음 연구에서는 원천
  데이터 스냅샷 ID와 체크섬을 가진 읽기 전용 캐시를 사용해야 결과
  재현성과 실행 시간을 함께 개선할 수 있다.

### 저장 용량

종목별 상세 JSON은 감사 추적에는 유용하지만 후보 보고서 하나가 5천 줄을
넘는다. 장기적으로는 Git에는 요약·스키마·체크섬만 두고 상세 산출물은
버전된 artifact 저장소로 옮기는 편이 낫다.

## 다음 연구 시작 조건

1. PIT 과거 유니버스와 기업 발표일 데이터 확보
2. 고정 데이터 스냅샷 생성
3. 일별 후보 수익 시계열과 시간축 fold 저장
4. B0보다 나은 새 가설을 사전 등록
5. pre-holdout 기준 통과 후에만 새 Blind holdout 배정

이 조건 전에는 UI에 차세대 HERD 점수나 확정 행동으로 표시하지 않는다.
