# 신규 행동 가설 V1

상태: `HISTORICAL_FALSIFICATION_FAILED` / `PROSPECTIVE_COLLECTION_ONLY`
운영 행동: `HOLD·0%`

## 가설

종목이 `RUSH`에 있을 때 SEC에 접수된 분기 실적 공시 이후 3개 완결
거래일의 종목 수익률이 섹터 ETF보다 5%p 이상 낮으면, 향후 126거래일
안에 5% 부분 익절·재진입 사이클이 Buy & Hold보다 유리할 가능성이
높다는 단일 가설이다.

높은 HERD, RSI 또는 가격 이격만으로 익절하지 않는다. 새 기업 정보에
대한 시장 반응과 기존 군중 상태가 충돌하는 사건만 후보로 삼는다.

## 시점 계약

1. SEC 접수시각 이전 정보는 사용하지 않는다.
2. 접수 뒤 3개 거래일이 완전히 끝나야 반응을 확정한다.
3. 해당 시점에 5거래 세션 이내의 주간 `RUSH` 관찰이 있어야 한다.
4. 후보 체결은 모든 확인 뒤 다음 거래일 시가다.
5. 익절한 5%는 매도 뒤 63거래 세션에 고정 재진입한다.
6. 결과는 126거래일과 재진입 사이클이 끝나기 전에 열지 않는다.

정식 전향 OOS에는 2026-08-03 이전 사건과 기존 1,998·2,161개 라벨을
소급하지 않는다. 별도로 기존 439종목과 겹치지 않는 54종목 역사 표본은
전향 연구를 시작할 가치가 있는지 빠르게 탈락시키는 용도로만 사용했다.

## 채택 게이트

- 성숙 사건 40건, 종목 20개, 연도 3개 이상
- 세 연도 모두 비용 후 자산 차이 양수
- 큰 조정·구조 훼손 비율 55% 이상
- 기본 왕복 30bp와 스트레스 70bp 모두 중앙 자산 차이 양수
- 스트레스 비용 후 이익인 완결 사이클 55% 이상

통과해도 연구 방향 증거만 인정한다. 바로 서비스 행동을 켜지 않으며,
생존자 편향·포트폴리오 완결 검증과 사람 승인은 별도로 남는다.

## ticker-disjoint 역사 사전 평가

- 결과를 보기 전에 54종목·동일 S1 공식·SEC 접수시각·63세션 재진입·
  30/70bp 비용을 고정했다.
- SEC 실적 사건은 3,978건, 최종 조건을 충족한 완결 사건은 22건·16종목이다.
- adverse precision, 비용 후 중앙 자산 차이, 연도 방향, 양의 사이클 비율은
  기준을 충족했다.
- 그러나 사전 최소치인 40건·20종목을 충족하지 못해 전체 판정은 실패다.
- 임계값을 완화하지 않는다. SEC 사건 수집은 계속하지만, 전향 결과 확인은
  더 많은 독립 사건이 쌓이기 전까지 차단한다.

결과는 `data/reports/ticker_disjoint_earnings_reaction_oos_v1.json`, 조건부
전향 게이트는 `data/reports/rush_earnings_prospective_confirmation_gate_v1.json`이다.

## 전향 입력

SEC 원문 사건은 버전 관리 밖의 해시 체인 append-only 원장
`data/runtime/action-research/sec-earnings-events-v1.jsonl`에 저장한다.
매 거래일 스케줄러는 최신 주간 S1이 Rush인 종목만 공식 SEC submissions
API에서 확인한다. 이 원장 수집은 행동 신호가 아니며 가격 갱신 실패 여부와
분리된다.

```bash
./scripts/evaluate-action-hypothesis.sh
```

현재 조건부 게이트가 닫혀 있으므로 전향 결과 판정은 실행하지 않는다.

## ticker-disjoint 편출 종목 확장 V2

- 검증된 S&P 500 편출 사건 중 기존 439종목과 V1 54종목에 없는 기업만
  결과 비관측 상태에서 선별했다.
- 공식 사건 원장의 CIK 후보와 공식 S&P 표의 GICS 섹터가 모두 확인된
  25종목을 가격 수집 대기열로 고정했다. WHR·ZION의 회사명 기반 CIK 후보는
  편출 전후 SEC 공시 표지의 tagged `TradingSymbol` 연속성으로 바로잡았다.
- Yahoo 가격 실패 CMA·FRC·GPS와 재사용 ticker로 판정된 SBNY를 제외해
  최소 4년 가격을 가진 21종목·주간 State S1 12,541행을 해시 고정했다.
- 21종목 모두에서 2012-01-11~2026-07-31 SEC 실적 사건 2,070건을 별도
  append-only 원장으로 확보했다. 3거래일 반응과 미래 결과는 아직 열지
  않았으며 V1의 22건과 합쳐 표본 기준을 맞추지 않는다.

입력 계약과 결과는
`data/herd/ticker_disjoint_earnings_oos_expansion_v2.json`,
`data/reports/ticker_disjoint_earnings_oos_expansion_v2.json`,
`data/herd/ticker_disjoint_sec_earnings_census_v2.json`에 보존한다.

## 편출 종목 독립 OOS 판정

- V1과 표본을 합치지 않고 동일한 Rush, 3거래일 섹터 잔차 -5%, 연 2회,
  63세션 cooldown, 5% 익절·63세션 재진입 공식을 그대로 적용했다.
- 후보는 15건·9종목·7개 연도였다. 사전 기준 40건·20종목에 미달했다.
- adverse precision은 53.3%, 기본 비용 HOLD 대비 순최종자산 중앙값은
  -10.66%p, 스트레스 비용에서는 -11.25%p였다.
- 표본 수뿐 아니라 방향성과 경제성도 반복되지 않았으므로
  `INDEPENDENT_HISTORICAL_OOS_FAILED`로 종료한다. 임계값 조정, V1 합산,
  전향 확인, 행동 권한 부여는 모두 금지한다.
