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

## 현재 240건의 해결 경로

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
3. 구형·변형 표 파서와 PDF 텍스트 추출
4. 서술문 사건 단위 파서 및 날짜 의미 분석
5. 누락 공식 문서 재탐색과 원문 해시 고정
6. CIK 기반 ticker 재사용·합병 관계 검증
7. 교체 쌍·구성 수·거래일 불변식 검사
8. 잔여 수동 검토 후 통합 원장과 일별 구성 재생

## 공식 기준 자료

- [S&P U.S. Indices Methodology](https://www.spglobal.com/spdji/en/methodology/article/sp-us-indices-methodology/)
- [S&P DJI Equity Indices Policies & Practices](https://www.spglobal.com/spdji/en/documents/methodologies/methodology-sp-equity-indices-policies-practices.pdf)
- [S&P DJI News & Announcements](https://www.spglobal.com/spdji/en/media-center/news-announcements/)
- [SEC Rule 12d2-2와 Form 25 설명](https://www.sec.gov/rules-regulations/2004/06/removal-listing-registration-securities-pursuant-section-12d-securities-exchange-act-1934)
- [SEC Exchange Act Rules 해석](https://www.sec.gov/rules-regulations/staff-guidance/corporation-finance-interpretations/exchange-act-rules)
