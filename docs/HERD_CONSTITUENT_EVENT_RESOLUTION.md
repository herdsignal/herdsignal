# S&P 500 구성 사건 해결 규칙

## 목표

미해결 240건을 임의 보정하지 않고, 당시 알 수 있었던 공식 발표만으로
구성 편입·편출과 적용 시점을 복원한다. 이 원장은 생존자 편향을 줄이기
위한 연구 입력이며 SEC 공시만으로 S&P 500 편입·편출을 추론하지 않는다.

## 증거 우선순위

1. S&P DJI 공식 보도자료의 구조화된 S&P 500 변경 표
2. S&P DJI 공식 보도자료의 회사·티커·행동·적용 시점이 연결된 서술문
3. S&P DJI의 후속 정정 발표
4. SEC CIK와 공시는 회사 동일성 및 합병·상장폐지 원인 확인에만 사용
5. 거래소·회사 보도자료는 공식 S&P 문서를 찾는 보조 단서로만 사용
6. 커뮤니티 구성 이력은 후보 발견용이며 최종 증거가 아니다

S&P 공식 근거 없이 SEC Form 25, 8-K 또는 합병 완료일만으로 지수
편출일을 확정하지 않는다. Form 25의 상장폐지 효력과 지수 구성 변경은
서로 다른 사건이다.

## 적용 시점 모델

날짜 하나로 정보를 축약하지 않고 다음 필드를 보존한다.

- `announcement_date`: 공식 발표일
- `stated_effective_date`: S&P 문서에 적힌 날짜
- `effective_timing`: `PRIOR_TO_OPEN`, `AFTER_CLOSE`, `UNSPECIFIED`
- `membership_session_date`: 일별 연구 구성에 실제 반영할 거래 세션
- `timing_evidence_context`: 적용 시점 문구가 포함된 원문 일부

`PRIOR_TO_OPEN`은 명시된 날짜의 세션부터 반영한다. `AFTER_CLOSE`는 다음
정규 거래 세션부터 반영한다. 휴장·예상치 못한 조기 폐장과 S&P의 후속
변경 공지가 있으면 자동 계산을 중단하고 별도 검토한다.

## 초기 240건의 해결 경로

- `OFFICIAL_DOCUMENT_TICKER_ONLY` 148건:
  문서는 있으나 행동 또는 적용일 의미가 검증되지 않았다. 구형 HTML,
  병합 셀, 표 머리글 변형과 서술문 문법을 추출한다.
- `NO_OFFICIAL_DOCUMENT_MATCH` 89건:
  현재 아카이브 검색으로 문서를 찾지 못했다. 공식 Media Center,
  `press.spglobal.com` 과거 URL, 제목 변형 및 후속 정정 발표를 탐색한다.
- `DISTANT_SAME_TICKER_EVENT_REQUIRES_IDENTITY_REVIEW` 3건:
  동일 ticker 재사용, 공개 후보 날짜 오류 또는 중복 사건 가능성을 CIK와
  공식 문맥으로 판정한다.

첫 감사 결과 공식 문서 후보가 하나 이상 연결된 사건은 150건, 아직
후보가 없는 사건은 90건이다. 후보 적용일이 주말인 사건은 15건이며,
같은 후보 날짜의 ADD/REMOVE 수가 맞지 않는 사건은 94건이다. 후자의
수치는 누락 사건의 연쇄 영향을 찾기 위한 진단값이지 개별 사건의 오류
확정값은 아니다.

### 서술문 파서 v2 결과

공식 corpus 253개를 계측한 결과 저장 원문은 모두 HTML이었다. 2016~2019
발표는 최신 구조화 표보다 `A will replace B in the S&P 500` 형식이
중심이었다. 기존 파서는 연도 없는 날짜와 장 마감 후 적용을 후보의 다음
거래 세션으로 연결하지 못했다.

v2는 발표일 기준 연도 추론, 연말 이월, `PRIOR_TO_OPEN`,
`AFTER_CLOSE`, `UNSPECIFIED` 구분과 중복 후속 발표의 의미 충돌 검사를
추가했다. 합병 예정일은 지수 적용일로 사용하지 않는다.

- 공식 검증 완료: 157건 → 257건
- 미해결: 240건 → 140건
- 서술문으로 새로 해결: 100건
- 공식 문서 의미 추출 잔여: 48건
- 공식 문서 재탐색 잔여: 89건
- ticker·날짜 충돌 잔여: 3건

`AFTER_CLOSE`는 다음 거래 세션을 의미하므로 문서상 날짜와 구성 반영
날짜를 별도로 보존한다. 이 변환은 최종적으로 독립 거래 캘린더와 다시
대조해야 한다.

### 독립 사건 추출과 잔여 사건 분리 결과

후보 행 하나를 기준으로 문장을 해석하던 방식에서 벗어나 공식 문서
전체에서 사건을 먼저 추출한 뒤 후보와 대조한다. `switch places`,
`move to`, 여러 종목이 순서대로 대응되는 `respectively`를 독립 문법으로
처리하고, 장 마감 후 변경은 XNYS 캘린더의 다음 거래 세션에 반영한다.

- 공식 구성 사건 해결: 301/397건
- 검증된 ticker 동일성 변경: 16건
- 미해결·격리 후보 행: 64건
- 완전 일치: 공식 서술문 138건, 공식 표 96건
- 후보 날짜 교정: 공식 표 56건, 공식 서술문 11건
- 실제 구성 변경이지만 의미 확인 필요: 6건
- 공식 문서 누락: 38건
- 공개 재구성본 이상 격리: 20건, 7개 폐쇄 루프
- 행동 충돌: 3건
- 동일성·날짜 충돌: 3건

공식 `asPDF=1` 원문 130건은 HTML 원문과 SHA-256으로 연결해 보조 증거로
고정했다. PDF는 표·서술문 누락을 확인하는 수단이며 HTML보다 높은
증거 등급을 부여하지 않는다.

ticker 변경은 SEC 공시 표지의 사건 전후 `TradingSymbol`이 동일 CIK에
속하고 원문에서 적용 날짜까지 확인된 경우만 별도 사건으로 승격한다.
현재 16건을 검증해 기존 REMOVE/ADD 32행을 `IDENTITY_CHANGE` 16행으로
대체했다. 동일 CIK만 확인되고 날짜가 없는 후보는 계속 보류한다.

최신 통합 원장은 361행이다. 공식 구성 사건 301건, ticker 변경 16건,
차단 사건 44건으로 구성된다. 공개본의 표기 진동과 즉시 반전 20행은
구성 순효과가 0임을 확인한 뒤 원장 밖으로 격리했다. 2016-07-18 공개
기준 구성으로 수행한 진단 재생은 317개 검증 사건을 반영했으며 오류
4건, 최종 구성 493개다. 네 오류는 모두 미해결 선행 사건으로 설명된다.
공개 기준 구성과 미해결 선행 사건이 남아 있어 `replay_ready=false`,
`survivorship_safe=false`다.

## 승격 조건

사건은 아래 조건을 모두 충족할 때만 `VERIFIED_OFFICIAL_EVENT`가 된다.

- 공식 S&P 출처 URL과 원문 SHA-256이 고정됨
- S&P 500 대상임이 명시됨
- ADD/REMOVE 행동이 회사·ticker와 문법적으로 연결됨
- 적용 날짜와 장 시작 전/마감 후 의미가 보존됨
- ticker 재사용 또는 회사명 충돌이 없음
- 같은 날짜의 교체 관계와 재생 전후 구성이 모순되지 않음

자동 추출은 `STRUCTURE_VERIFIED` 또는 `SEMANTICS_VERIFIED`까지만 허용한다.
애매한 문장, 복수 날짜, TBA, 정정 발표, ticker 충돌은 fail-closed로
검토 큐에 남긴다.

## 구현 순서

1. 미해결 사건 분류 감사 산출물 고정
2. 적용 시점과 증거 신뢰등급 데이터 계약 추가
3. 구형·변형 표와 독립 서술문 사건 파서
4. 공식 PDF 보조 원문 해시 고정
5. 누락 공식 문서 재탐색과 44건 잔여 의미 검증
6. CIK 기반 ticker 재사용·합병 관계 재연결
7. 교체 쌍·구성 수·거래일 불변식 검사
8. 통합 원장 재생성 및 일별 구성 재생

## 공식 기준 자료

- [S&P U.S. Indices Methodology](https://www.spglobal.com/spdji/en/methodology/article/sp-us-indices-methodology/)
- [S&P DJI Equity Indices Policies & Practices](https://www.spglobal.com/spdji/en/documents/methodologies/methodology-sp-equity-indices-policies-practices.pdf)
- [S&P DJI News & Announcements](https://www.spglobal.com/spdji/en/media-center/news-announcements/)
- [SEC Rule 12d2-2와 Form 25 설명](https://www.sec.gov/rules-regulations/2004/06/removal-listing-registration-securities-pursuant-section-12d-securities-exchange-act-1934)
- [SEC Exchange Act Rules 해석](https://www.sec.gov/rules-regulations/staff-guidance/corporation-finance-interpretations/exchange-act-rules)
