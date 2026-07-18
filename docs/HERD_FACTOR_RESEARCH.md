# 차세대 HERD 구성 요소 조사

상태: `RESEARCH_BASELINE`  
작성일: 2026-07-19  
목적: Buy & Hold를 장기적으로 이길 HERD 후보 요소를 유명세가 아니라 근거, 독립성, 데이터 현실성으로 선별한다.

## 결론

차세대 HERD는 현재 v4의 다섯 가격 지표와 v6.1의 객관적 분석을 그대로 더한 점수가 되어서는 안 된다. RSI, 이동평균 이격, 52주 위치, 가격 모멘텀은 같은 가격 경로를 여러 번 세는 경향이 있기 때문이다.

첫 연구 모델은 다음 다섯 증거군을 대상으로 한다.

| 증거군 | 우선 후보 | HERD에서의 역할 | 우선순위 |
|---|---|---|---|
| 군중 참여·위치 | 거래량 충격, 회전율, 시장 폭, 신고가·신저가, 가격 범위 내 위치 | 실제 밀집·분산의 중심 | 1 |
| 추세·상대강도 | 12-1개월 모멘텀, 장기 추세, 종목→섹터→SPY 상대강도 | 밀집의 지속성 구분 | 1 |
| 위험·취약성 | 하방 변동성, 낙폭, 갭 위험, 시장 변동성 체제 | Healthy/Exhausted 상태 구분 | 1 |
| 기업 상태 | 수익성, 재무 건전성, 가치, 실적 수정 | 가격 신호의 구조적 배경 | 2 |
| 시장 심리·포지셔닝 | 옵션, 신용 스프레드, 안전자산 수요, 뉴스, 자금 흐름 | SPY 체제와 극단 상태 보조 | 3 |

`DATA QUALITY`와 `MODEL CONFIDENCE`는 방향성 증거가 아니다. 최종 HERD의 신뢰도와 공개 여부를 제한하는 게이트로 둔다.

## 조사에서 확인한 것

### 근거가 상대적으로 강한 요소

1. **중기 모멘텀과 장기 추세**
   - 자산과 시대를 가로지른 추세 추종 근거가 존재한다.
   - 12개월 수익률에서 최근 1개월을 제외한 `12-1` 모멘텀을 기준선으로 둔다.
   - 단기 RSI 여러 개보다 장기 상대강도와 추세 지속성을 우선 검증한다.

2. **품질과 수익성**
   - ROE, 낮은 발생액, 낮은 레버리지 같은 품질 정의는 주요 지수 사업자도 사용한다.
   - 가격만으로 구분하기 어려운 구조적 부진과 건전한 조정을 가르는 후보가 된다.
   - 당시 공개된 재무 데이터를 복원할 수 있을 때만 사용한다.

3. **상대 가치**
   - 장기 기대수익과 관련된 전통적 근거가 있지만, 값이 싸다는 이유만으로 군중 이탈이 끝났다고 볼 수 없다.
   - HERD를 선형으로 올리거나 내리기보다 Flee/Scatter의 성격을 구분하는 조건부 정보로 시험한다.

4. **시장 폭과 참여**
   - 경쟁 시장 심리 지수는 가격 모멘텀뿐 아니라 신고가·신저가, 시장 폭, 옵션, 신용, 변동성, 안전자산 수요를 함께 본다.
   - SPY에서는 지수 내부 참여율이 군중이라는 이름과 가장 직접적으로 맞는다.
   - 개별 종목에서는 동일 개념을 거래 참여와 섹터 참여로 치환해야 한다.

### 유효할 수 있지만 과신하면 안 되는 요소

1. **변동성 타이밍**
   - 고변동 시 노출을 낮추는 연구와 실전 OOS 성과가 약하다는 반대 연구가 모두 있다.
   - 변동성은 수익률 방향 점수보다 취약성과 행동 한도를 정하는 요소로 먼저 시험한다.

2. **실적 서프라이즈와 리비전**
   - 실적 발표 뒤 가격 드리프트 근거가 있으나 최근 표본에서 약화 또는 반전됐다는 연구도 있다.
   - 발표일, 당시 컨센서스, 수정 전 수치를 복원하지 못하면 사용하지 않는다.

3. **투자자 심리**
   - 특히 작고 젊고 적자이며 변동성이 큰 종목에서 설명력이 더 크다는 연구가 있다.
   - 뉴스 감성은 효과 기간이 짧고 데이터 비용이 높아 장기 핵심 요소로 부적합할 수 있다.

4. **옵션·자금 흐름·공매도**
   - 시장 스트레스와 포지셔닝에 의미가 있지만 무료 장기 이력과 시점 정합 데이터가 부족하다.
   - SPY 연구 후보로 보관하고 운영 핵심에는 즉시 넣지 않는다.

## 경쟁 서비스에서 가져올 것과 버릴 것

| 사례 | 참고할 점 | 그대로 쓰지 않을 점 |
|---|---|---|
| CNN Fear & Greed | 서로 다른 7개 시장 증거를 사용하고 동일 개념의 중복을 줄임 | SPY용 시장 심리를 개별 종목 점수로 복제 |
| Seeking Alpha Quant | 가치·성장·수익성·모멘텀·EPS 수정, 섹터 상대평가 | 유료 데이터와 비공개 종합 공식 모방 |
| Morningstar | 가치와 불확실성을 분리 | 애널리스트 DCF 공정가치 흉내 |
| MSCI/S&P Factor | 표준화된 가치·품질·모멘텀·저변동 정의 | 장기 팩터 수익률을 현재 군중 상태와 동일시 |

HERD는 경쟁사의 추천 등급을 복제하지 않고, 서로 다른 증거를 Flee–Rush라는 시장 상태로 압축한다.

## 권장 계산 구조

```text
시점 정합 원천 데이터
    ↓
개별 지표 계산
    ↓
종목 자체 역사 + 섹터 기준 정규화
    ↓
증거군 내부 중복 제거
    ↓
증거군별 상태 산출
    ↓
상태 의존 결합
    ↓
최종 HERD 0~100
```

### 단순 평균을 쓰지 않는 이유

- RSI와 가격 위치를 각각 넣으면 같은 상승을 여러 번 센다.
- 높은 품질은 좋은 기업을 뜻하지만 군중이 밀집했다는 뜻은 아니다.
- 높은 변동성은 Flee와 Rush 양쪽 극단에서 발생할 수 있다.
- 동일 지표도 SPY와 개별 종목에서 의미가 다르다.

먼저 증거군별 대표값을 만들고, 방향이 맥락에 따라 달라지는 값은 조건부 분류에 쓴다. 예를 들어 강한 추세와 넓은 참여가 동반된 Rush는 `Healthy Rush`, 추세 둔화·폭 축소·하방 위험 증가가 동반되면 `Exhausted Rush` 후보가 된다. 같은 80점대라도 내부 상태 태그는 달라야 한다.

## SPY와 개별 종목

하나의 공식에 억지로 맞추지 않는다.

### SPY

- S&P 500 구성 종목의 상승 참여율
- 200일선 상회 비율
- 신고가·신저가
- 동일가중지수 대비 시가총액가중지수
- VIX 또는 변동성 체제
- 신용 및 안전자산 수요
- 장기 추세와 모멘텀

### 개별 종목

- 종목 자체 장기 추세와 12-1 모멘텀
- 섹터 ETF 및 SPY 대비 상대강도
- 거래량·회전율·갭·하방 변동
- 낙폭과 회복 구조
- 시점 정합 품질·가치·실적 수정
- 해당 섹터의 참여 상태

공통 증거군은 유지하되, 시장 폭처럼 자산 유형에 따라 관측 방법이 다른 항목은 어댑터로 분리한다.

## 구현 전 검증 순서

1. 현재 v4와 v6.1의 모든 객관 지표를 한 테이블에 기록한다.
2. 지표별 정의, 방향, 기간, 데이터 출처, 시점 정합성을 고정한다.
3. 상관행렬과 군집 분석으로 중복 지표를 찾는다.
4. 각 증거군을 단독 OOS로 평가한다.
5. 기존 HERD에 하나씩 추가하는 ablation test를 수행한다.
6. 섹터·시대·상승/하락 체제별 효과 방향을 확인한다.
7. 가중치 한 점이 아니라 인접 범위의 안정성을 확인한다.
8. 후보 시험 횟수, PBO, Deflated Sharpe를 기록한다.
9. Blind holdout을 열기 전에 결합식과 임계값을 잠근다.

## 첫 실험 세트

가중치는 아직 확정하지 않는다. 다음 모델만 먼저 비교한다.

- `B0`: 현재 HERD v4
- `B1`: 중복 제거한 가격·추세 핵심
- `B2`: B1 + 상대강도 + 시장/섹터 참여
- `B3`: B2 + 하방 위험 상태
- `B4`: B3 + 시점 정합 기업 상태

중간 후보는 아래 진단을 개선해야 한다. 최종 후보는 이 진단뿐 아니라 동일 조건의 `HERD Benchmark Strategy`가 비용 차감 후 Buy & Hold를 초과해야 한다.

- Flee/Scatter와 Calm의 장기 결과 분리
- Healthy/Exhausted Rush 구분
- 섹터 간 일관성
- 상태 전환 안정성
- 데이터 가용성과 재현성
- 비용 차감 후 CAGR과 Buy & Hold 초과수익
- 최대낙폭, Sortino, Calmar
- 상승장 포착률과 하락장 손실 포착률

## 당장 채택하지 않는 값

- 소셜 미디어 언급량
- 생성형 AI 감성 점수
- 애널리스트 목표가 평균
- 현재 구성 종목만 사용한 과거 시장 폭
- 수정 후 재무 데이터
- 출처가 불명확한 종합 점수
- 백테스트에서 한 번 잘 나온 기술 지표
- 사용자 보유 비중과 위험 성향

## 참고 자료

- [AQR, A Century of Evidence on Trend-Following Investing](https://www.aqr.com/Insights/Research/Journal-Article/A-Century-of-Evidence-on-Trend-Following-Investing)
- [Jegadeesh & Titman, Profitability of Momentum Strategies](https://www.nber.org/papers/w7159)
- [MSCI, Foundations of Factor Investing](https://www.msci.com/research-and-insights/paper/foundations-of-factor-investing)
- [S&P DJI, Factor definitions](https://www.spglobal.com/spdji/en/landing/investment-themes/factors/)
- [Novy-Marx, profitability research](https://www.nber.org/papers/w23910)
- [Moreira & Muir, volatility-managed portfolios](https://papers.ssrn.com/abstract%3D2773438)
- [Cederburg et al., volatility-managed strategy counter-evidence](https://papers.ssrn.com/sol3/Delivery.cfm/SSRN_ID3357038_code707144.pdf?abstractid=3357038&mirid=1)
- [Baker & Wurgler, investor sentiment](https://www.nber.org/papers/w10449)
- [Federal Reserve, variance risk premium](https://www.federalreserve.gov/econres/feds/stock-return-predictability-and-variance-risk-premia-statistical-inference-and-international-evidence.htm)
- [Federal Reserve, global return prediction](https://www.federalreserve.gov/econres/ifdp/predicting-global-stock-returns.htm)
- [CNN Fear & Greed](https://edition-prod-cf.sitemirror.cnn.com/markets/fear-and-greed)
- [Seeking Alpha Quant methodology](https://help.seekingalpha.com/premium/quant-ratings-and-factor-grades-faq)
- [Morningstar stock rating methodology](https://www.morningstar.com/help-center/morningstars-approach-to-investing/morningstars-stock-ratings)
- [Feng, Giglio & Xiu, Taming the Factor Zoo](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3330843)

핵심 근거와 사용한 데이터 버전은 구현용 모델 카드에도 원문 단위로 고정한다.
