# AI 근거 검토 프로토타입

상태: `RESEARCH_ONLY`  
운영 기본값: 비활성화

## 목적

State S1의 현재 관찰값을 여러 관점에서 짧게 정리한다. 모델이 새로운
시장 사실을 찾거나 가격 방향, 매수·익절 비율을 결정하는 기능이 아니다.

## 입력 경계

현재 입력은 해당 종목의 시점이 고정된 State S1 사실뿐이다.

- 상태 점수·단계·전이
- 4주·13주 변화
- 가격 확장·추세 위치·상대 위치·참여
- 하방 위험 맥락과 참조 섹터 ETF

각 값은 `OBS.*` 근거 ID를 가진다. 뉴스, 기억에 의존한 기업 정보, 사용자
자산 및 거래 내역은 전송하지 않는다.

## 출력 경계

`HERD_STATE`, `MARKET_CONTEXT`, `RISK`, `RED_TEAM` 네 관점만 반환한다.
모든 주장에는 입력에 존재하는 근거 ID가 필요하다. 알 수 없는 근거 ID,
누락된 관점, 방향 예측, `HOLD` 이외 행동 또는 0% 이외 비율이 하나라도
있으면 전체 응답을 `PROVIDER_ERROR`로 폐기한다.

API는 인증된 `POST /api/research/evidence-reviews/{ticker}`다. 기능이 꺼져
있으면 `DISABLED`, State S1이 없으면 `INSUFFICIENT_EVIDENCE`를 반환한다.

## 설정

```env
HERD_AI_EVIDENCE_REVIEW_ENABLED=false
OPENAI_API_KEY=
OPENAI_EVIDENCE_MODEL=gpt-5.6-terra
OPENAI_EVIDENCE_TIMEOUT=30s
```

요청은 저장하지 않으며 사용자 식별자는 SHA-256으로 축약한다. API 키가
없거나 기능이 꺼진 상태가 정상 기본값이다.

## 승격 금지

이 프로토타입의 문장은 행동 모델의 학습 feature, label 또는 OOS 증거로
사용하지 않는다. 행동 가설은 별도 사전등록과 독립 OOS 검증을 거친다.
