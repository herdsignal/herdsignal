# AI 근거 검토 프로토타입 V2

상태: `RESEARCH_ONLY`  
운영 기본값: 비활성화

## 목적

장기 운용 Evidence Packet을 서로 겹치지 않는 관점에서 짧게 정리한다.
모델이 새로운 시장 사실을 찾거나 가격 방향, 매수·익절 비율을 결정하는
기능이 아니다.

## 입력 경계

현재 입력은 해당 종목의 시점이 고정된 장기 운용 Evidence Packet이다.

- SEC PIT 기업 체력 사실
- 원문 검수 SEC 가이던스 사실
- SPY·섹터·종목 고유 가격 경로 맥락
- State S1 상태·전이와 구성 관측값
- 정보 변화 소스별 연결 상태

각 값은 영역, 품질, 기준일, 접수·관측시각, 출처와 근거 ID를 가진다. 사용자
보유 비중, 현금, 자산과 거래 내역은 전송하지 않는다.

## 출력 경계

`BUSINESS_HEALTH`, `EXPECTATION_VALUATION`, `MARKET_SECTOR`, `CHART_CROWD`,
`INFORMATION_CHANGE`, `RED_TEAM` 여섯 관점만 반환한다. 앞의 다섯 관점은
자기 영역의 `AVAILABLE` 근거만 인용할 수 있고, `RED_TEAM`만 영역을 가로질러
반대 근거를 대조할 수 있다. 사용 가능한 근거가 없으면 의견 대신
`missingEvidence`를 반환해야 한다.

Strict JSON Schema 통과 뒤에도 서버가 관점 수, 근거 ID, 영역 소속, 품질과
행동 권한을 다시 검증한다. 알 수 없는 근거 ID, 영역 혼용, 사용 불가 사실
인용, 누락된 관점, 방향 예측, `HOLD` 이외 행동 또는 0% 이외 비율이 하나라도
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

구조화 출력은 형식을 강제하지만 값 자체의 사실성을 보장하지 않는다. 따라서
근거 ID의 존재와 영역 소속을 애플리케이션에서 별도로 검증한다. 설계 원칙은
NIST AI RMF의 투명성·설명 가능성·안전한 실패와 OpenAI Structured Outputs의
제약 및 한계를 따른다.
