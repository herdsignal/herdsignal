# HERD Point-in-time 데이터 계약

상태: `SOURCE_VALIDATION`  
최신화: 2026-07-19

## 목적

과거 날짜에 실제로 존재했던 투자 가능 종목과 그날까지 공개된 정보만으로
HERD를 검증한다. 현재 살아남은 종목을 과거 전체에 소급하지 않는다.

## 출처 등급

| 등급 | 예시 | 모델 검증 사용 |
|---|---|---|
| `LICENSED_AUTHORITATIVE` | CRSP/WRDS 일별 S&P 500 구성원, S&P DJI 라이선스 데이터 | 가능 |
| `OFFICIAL_RECONSTRUCTION` | S&P DJI 발표문을 effective date 기준으로 재구성 | 교차검증 후 가능 |
| `COMMUNITY_RECONSTRUCTION` | 공개 저장소의 과거 구성 재구성 | 탐색·누락 조사만 가능 |

무료 재구성본은 종목 코드 변경, 재사용된 티커, 빠진 변경일을 완전히 판별할
수 없으므로 `survivorship_safe=true`로 승격하지 않는다.

## 구성원 스키마

```text
index_id
security_id
ticker
effective_from
effective_to
source_tier
source_uri
```

- 구간은 `[effective_from, effective_to)`다.
- `effective_to`가 비어 있으면 마지막 관측일까지 구성원이었다는 뜻이다.
- ticker는 표시 값이며 영구 식별자가 아니다.
- 권위 데이터는 CRSP `PERMNO` 같은 안정적인 `security_id`가 필수다.
- 추가·편출 공지일과 실제 적용일은 별도 이벤트로 보존한다.

## 품질 게이트

다음 조건을 전부 만족해야 생존자 편향 안전 검증에 사용할 수 있다.

1. 출처 등급이 `LICENSED_AUTHORITATIVE` 또는 검증된
   `OFFICIAL_RECONSTRUCTION`
2. 모든 레코드에 안정적인 security ID 존재
3. 구성 구간 중복·역전 없음
4. 각 관측일 구성 수가 허용 범위 내
5. 공식 변경 표본과 추가·편출 날짜 교차검증 통과
6. 원본 파일과 정규화 산출물의 SHA-256 저장
7. 합병·상장폐지·티커 변경 이벤트 연결

## 확보 전략

1. 대학 계정의 WRDS/CRSP 구독 가능 여부를 확인한다.
2. 가능하면 `dsp500list_v2`의 `PERMNO`, 시작일, 종료일을 기준 원천으로
   사용한다.
3. 접근 전에는 MIT 공개 재구성본을 가져와 데이터 파이프라인과 비생존
   종목 목록을 준비한다.
4. S&P DJI 공식 발표문 표본과 공개본의 변경일을 대조한다.
5. 권위 원천을 확보하기 전에는 Blind holdout과 차세대 채택 판정을
   실행하지 않는다.

## 공개 재구성본 진단

`community-sp500-1996-2026`을 파이프라인 점검용으로 생성했다.

- 원본 관측일: 3,480개
- 범위: 1996-01-02~2025-08-23
- 고유 ticker: 1,128개
- 구성 구간: 1,177개
- 구성 수 범위: 442~505개
- 480개 미만 관측: 2,309개
- 같은 날짜의 충돌 레코드: 2개

비생존 ticker 후보를 찾는 데는 유용하지만 구성 수 누락, 안정적인 security
ID 부재, 공식 변경일 미대조 때문에 생존자 편향 안전 데이터로 사용할 수
없다. 이 결과는 CRSP/WRDS 또는 S&P 공식 원천 확보 필요성을 확인한
진단이며 채택 검증 데이터가 아니다.

## 발표일 기준 기업 데이터

SEC EDGAR `submissions`의 접수 시각과 `companyfacts`의 `filed`, `accn`,
`form`, `fy`, `fp`, 기간 정보를 함께 저장한다. 동일 기간의 수정 공시는
이전 값을 덮어쓰지 않고 별도 버전으로 보존한다. 특정 날짜의 값은
`filed <= as_of`인 레코드 중 당시 최신 공시만 선택한다.

과거 컨센서스 EPS는 SEC 데이터에 없으므로 별도 라이선스 원천 없이는
구현 완료로 처리하지 않는다.
