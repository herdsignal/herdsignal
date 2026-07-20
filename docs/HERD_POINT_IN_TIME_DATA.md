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

강남대학교 계정으로 WRDS/CRSP를 이용할 수 없다는 전제에서 공식 공개
원천 복원을 우선한다.

1. 공개 재구성본은 공식 변경 근거를 찾기 위한 후보 목록으로만 쓴다.
2. 최근 10년 S&P Global 보도자료 원문을 저장하고 SHA-256으로 고정한다.
3. 후보의 ticker와 적용일을 공식 문서에 연결한 뒤 사람이 편입·편출,
   발표일, 적용일을 확인한다.
4. 확인된 이벤트만 공식 원장으로 승격하고 검증된 기준 구성에서 재생한다.
5. SEC CIK·접수번호로 합병·상장폐지·기업 데이터 이력을 연결한다.
6. 유료 권위 원천과 동등한 완전성을 입증하기 전에는 Blind holdout과
   차세대 채택 판정을 실행하지 않는다.

### WRDS 없이 사용하는 복원 계약

최근 10년은 다음 순서로 복원한다.

1. 공개 구성 재구성본에서 추가·편출 후보만 추출한다.
2. 각 후보에 S&P Global 공식 발표 URL을 연결한다.
3. 발표 원문을 저장하고 SHA-256을 이벤트 원장에 기록한다.
4. `announcement_date`와 `effective_date`를 구분한다.
5. 기준일의 검증된 구성 스냅샷에서 REMOVE 후 ADD 순서로 이벤트를 재생한다.
6. 없는 종목 편출, 이미 있는 종목 추가, 구성 수 480~510 이탈 시 중단한다.
7. 후보 이벤트 전부에 공식 근거가 연결되기 전에는 완성으로 판정하지 않는다.

S&P 공식 URL 또는 저장한 원문이 없는 이벤트는 구성 복원에 사용할 수
없다. 검색 결과의 요약문과 Wikipedia는 후보 발견에만 쓴다.

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

## 공식 변경 근거 수집 현황

대상 기간은 기존 가격 스냅샷과 같은 2016-07-18~2026-07-17이다.

- 공개본에서 추출한 변경 후보: 397건(ADD 210, REMOVE 187)
- S&P Global 공식 보도자료: 130건
- 실제 발표 범위: 2016-08-31~2026-06-23
- 원문 SHA-256 불일치: 0건
- 거래소와 ticker 표기가 공식 원문에서 발견된 후보: 309개 문서 연결
- 공식 표에서 구조적으로 추출한 전체 이벤트: 202건
- 위 이벤트와 공개본 후보의 날짜·행동·ticker 완전 일치: 96건
- 같은 이벤트를 재공지한 공식 표: 1건
- 최초 TBA 후 후속 공지에서 적용일이 확정된 이벤트: 1건
- 독립 서술문 사건 추출을 포함한 공식 구성 해결: 301/397건
- 공식 표로 공개본 날짜 교정: 56건
- 공식 서술문으로 공개본 날짜 교정: 11건
- SEC 동일 CIK와 적용일이 검증된 ticker 변경: 16건
- 구성 변경 후보에서 동일성 변경으로 재분류한 행: 32건
- 현재 차단 후보 행: 36건
- 공개 재구성본 이상 격리: 20건
- 공식 S&P 보도자료 병합 corpus: 138건
- `asPDF=1` 보조 원문: 130건, SHA-256 불일치 0건

자동 ticker 연결은 검증 완료가 아니라 `REQUIRES_HUMAN_REVIEW`다. 문장에 ticker가
존재해도 해당 종목이 S&P 500에 편입·편출된다는 의미인지, 적용일이 후보와
같은지는 원문을 확인해야 한다. 차단 36건은 자동 추정하지 않는다.
공식 문서 재탐색, 남은 문장 의미, 행동 충돌, ticker 동일성·적용 날짜를
각각 독립 검토한다.

재현 도구:

- `spglobal_release_archive.py`: 공식 보도자료와 해시 manifest 수집
- `baseline_membership_correction.py`: 사후 공식 연속성 근거의 진단 기준 보정
- `constituent_blocker_backlog.py`: 차단 사건을 증명 경로별로 분류
- `spglobal_evidence_matcher.py`: 강한 ticker 표기만 검토 후보로 연결
- `spglobal_event_extractor.py`: 공식 표의 S&P 500 행과 적용일 구조화
- `spglobal_prose_event_verifier.py`: 행동 표현과 적용일이 같은 문맥인 후보만 검증
- `spglobal_candidate_semantics.py`: 후보 독립 복수 사건 추출
- `spglobal_identity_change.py`: ticker 변경과 구성 변경 분리
- `spglobal_pdf_archive.py`: 공식 PDF 보조 원문과 해시 manifest 고정
- `candidate_identity_pairing.py`: 미해결 REMOVE/ADD 동일성 후보 생성
- `sec_trading_symbol_evidence.py`: 동일 CIK의 사건 전후 ticker와 적용일 검증
- `identity_transition_reconciliation.py`: 구성 변경과 ticker 변경 원장 분리
- `official_candidate_reconciliation.py`: 공식 날짜 교정과 미해결 사유 분류
- `official_constituent_ledger.py`: 검증 원장 무결성 검사와 구성 재생

## 발표일 기준 기업 데이터

SEC EDGAR `submissions`의 접수 시각과 `companyfacts`의 `filed`, `accn`,
`form`, `fy`, `fp`, 기간 정보를 함께 저장한다. 동일 기간의 수정 공시는
이전 값을 덮어쓰지 않고 별도 버전으로 보존한다. 특정 날짜의 값은
accession number가 일치하고 `acceptanceDateTime <= as_of`인 레코드만
선택한다.

`sec_point_in_time_fundamentals.py`는 다음을 강제한다.

- 기본 submissions와 과거 filings 조각의 accession–접수 시각 색인
- Company Facts 관측값과 accession 결합
- 수정공시를 포함한 모든 버전 보존
- timezone 없는 조회 시각 거부
- 접수 시각을 연결하지 못한 관측값의 엄격 모드 제외
- 하나라도 접수 시각이 누락되면 `point_in_time_ready=false`

Company Facts의 `filed` 날짜만으로 장중 공개 시각을 추정하지 않는다.
실제 SEC 수집에는 식별 가능한 User-Agent와 공정 접근 속도 제한을
적용하고, 원본 JSON·SHA-256·수집 시각을 함께 보관해야 한다.

과거 컨센서스 EPS는 SEC 데이터에 없으므로 별도 라이선스 원천 없이는
구현 완료로 처리하지 않는다.

### 가격·fold 연결과 결측 제출 격리

55종목 가격 스냅샷 중 ETF 4개를 제외한 51개 기업을 SEC CIK에 연결했다.
기업 승계가 있는 XOM은 CIK 유효기간을 적용해 2026년 재편 전 fold에
`0000034088`을 사용한다. 최신 fold의 엄격 접수시각 연결률은 50/51이다.

CRM CompanyFacts에는 submissions 이력에서 접수시각을 찾을 수 없는
`0001108524-21-000014` 관측이 있다. `filed` 날짜나 임의 장 마감 시각으로
대체하지 않고 555개 관측을 계속 제외한다. 제외 후에도 다섯 fold 모두에서
매출, 순이익, 영업현금흐름, 자산, 부채·차입금 그룹의 검증된 최신 관측이
550일 이내 존재한다.

따라서 CRM은 전체 corpus 기준 `strict_corpus_ready=false`를 유지하되,
기업 상태 악화 시 추가매수만 막는 방어 지표 연구에는
`BUSINESS_GUARD_READY_WITH_DISCLOSED_EXCLUSIONS`로 포함할 수 있다.
제외된 관측을 복원하거나 HERD 과열 점수에 직접 가감하는 용도로는
사용하지 않는다.

### EDGAR master index 확보

`sec-master-2016q3-2026q3-20260719` 스냅샷을 로컬에 고정했다.

- 공식 분기 파일: 41개
- 접수 색인 행: 11,017,497개
- 실제 접수일 범위: 2016-07-01~2026-07-17
- 원본 크기: 991,976,693바이트
- SHA-256 불일치: 0건

각 파일의 SEC URL, 분기, 행 수, 최초·최종 접수일, 바이트와 SHA-256을
manifest에 저장한다. User-Agent 이메일은 manifest와 로그에 저장하지 않는다.
이 색인은 회사명–CIK 후보 발견과 Form 25·8-K·S-4·DEFM14A 접수번호
탐색에 사용하며, 그 자체로 ticker의 과거 소유 관계를 확정하지 않는다.

공식 표 이벤트 202건을 EDGAR 회사명과 연결한 결과:

- 유일한 CIK 이름 후보: 169건
- CIK 후보 없음: 18건
- 복수 CIK로 모호함: 15건

회사명은 문장부호 정규화 후 먼저 완전 일치시키고, 실패한 경우에만
Inc·Corp·Company·PLC 같은 법인 접미사를 제거한다. 같은 이름에 CIK가
둘 이상이면 임의 선택하지 않는다. 169건도 submissions의 현재·과거
회사명과 사건 전후 공시를 확인하기 전에는 `CIK_NAME_CANDIDATE`다.

### Form 25/25-NSE 상장폐지 증거

유일 CIK가 연결된 공식 편출 이벤트 87건을 대상으로 적용일 전 30일~후
180일의 Form 25/25-NSE를 조사했다.

- 단일 Form 25 후보: 31건
- 복수 Form 25 후보: 2건
- 해당 기간 Form 25 없음: 55건
- 수집한 원문: 33개
- 보통주만 포함: 28개
- 보통주와 다른 증권을 함께 포함: 3개
- 보통주가 아닌 증권만 포함: 2개
- 보통주 Form 25가 연결된 편출 이벤트: 31건

Flowserve의 2021년 Form 25는 선순위 채권, Kansas City Southern의 한
Form 25는 우선주 대상이었다. 따라서 Form 25 존재 여부만으로 회사
보통주 상장폐지를 판정하지 않는다. 원문의 `descriptionClassSecurity`에
보통주가 명시된 경우만 상장폐지 증거로 사용하며, 최종 사건 원인은
8-K·S-4·DEFM14A와 함께 검토한다.

### 합병·인수 공시 증거

유일 CIK 편출 사건 87건 주변에서 8-K는 적용일 전 45일~후 60일,
S-4·DEFM14A는 전 400일~후 30일 범위로 조사했다.

- 공시 후보가 있는 편출 사건: 83건
- 수집·해시 고정한 원문: 304개
- 8-K/8-KA: 278개
- DEFM14A: 24개
- S-4/S-4A: 2개
- 합병 완료 표현이 있는 문서: 118개
- 그중 상장폐지 표현도 있는 문서: 60개
- 합병 계약 표현만 있는 문서: 10개
- 합병 완료 증거가 있는 편출 사건: 50건
- 계약 증거만 있는 편출 사건: 1건

계약 체결은 합병 완료로 승격하지 않는다. 자동 문구 분류 결과는
`REQUIRES_HUMAN_REVIEW`이며, 최종 관계는 접수번호·대상 CIK·효력일과
Form 25를 함께 대조한 뒤 확정한다.

### S&P–SEC 통합 사건 원장

아래 수치는 독립 사건 추출 전 생성한 기존 통합 원장 스냅샷이다. 최신
통합 원장은 별도 v3 산출물로 생성했으며 기존 스냅샷을 덮어쓰지 않는다.

공개본 후보 397건에 S&P 공식 근거, 공식 적용일, CIK 후보, Form 25와
합병 공시 증거를 결합했다.

- 공식 검증 이벤트: 157건
- 그중 SEC 기업행동 증거가 연결된 이벤트: 42건
- 보통주 Form 25가 연결된 공식 이벤트: 26건
- 합병 완료 표현이 연결된 공식 이벤트: 42건
- 공식 문서는 있으나 행동·날짜 검토 필요: 151건
- 공식 문서 미연결: 89건
- `replay_ready=false`
- `survivorship_safe=false`

SEC 증거가 있어도 자동 문구 분류 단계에서는
`OFFICIAL_EVENT_WITH_SEC_ACTION_EVIDENCE`로만 표시한다. 원문 검토 전
`CORPORATE_ACTION_CONFIRMED`로 승격하지 않는다. 미해결 이벤트가 있으므로
전체 기간 일별 구성의 완료 판정도 차단한다.

### 구성 재생 진단

아래 20건 오류 수치는 기존 157건 원장의 이전 결과다. 최신 진단 결과로
오해하지 않는다.

최신 v8 진단은 공식 구성·SEC 기업행동·ticker 및 기업 연속성으로 검증한
322건을 재생했다. EVHC·DXC·NLOK 연속성은 공식 S&P 문서와 SEC 원문으로
확인했다. HCP는 2016-10-24 공식 S&P 발표에서 기존 구성 종목이자 분할 후
잔류 종목으로 확인되지만 근거일이 기준일보다 늦으므로, 원본 기준 480개를
덮어쓰지 않고 진단 전용으로 HCP 1개를 추가했다.

Discovery의 DISCA·DISCK는 같은 날 WBD 한 클래스로 전환됐다. S&P 공식
발표의 구성 잔류 문구와 SEC 8-K의 클래스 전환·거래 시작일을 함께
확인해 하나의 다중 클래스 동일성 사건으로 재생한다.

- 원본 기준 구성: 480종목
- 진단 보정 기준 구성: 481종목
- 검증 사건: 322건
- 미해결로 차단된 사건: 36건
- 진단 최종 구성 수: 493종목
- 구성 재생 오류: 0건
- 기준 보정 범위: `DIAGNOSTIC_BASELINE_ONLY`
- `diagnostic_only=true`
- `replay_complete=false`
- `survivorship_safe=false`

HCP 보정은 사후 공식 근거를 이용한 연속성 추론이다. 따라서 오류가
0건이어도 공식 일별 구성으로 저장하거나 채택 연구에 사용하지 않는다.
재생 엔진은 REMOVE 후 ADD 순서를 강제하고, 완전하지 않은 원장은 기본
모드에서 즉시 거부한다.

### SEC PIT corpus 최종 감사

유일 CIK 후보 157개에 대해 2016-07-18~2026-07-17 범위의 submissions,
Company Facts와 필요한 과거 filing 조각을 고정했다.

- CIK: 157개
- 원본 JSON: 362개
- 과거 submissions 조각: 52개
- 원본 크기: 506,466,890바이트
- SHA-256 불일치: 0건
- Company Facts 미제공: 4개 CIK
- 접수 시각이 연결된 재무 관측값: 2,119,906개
- 접수 시각 미연결: 0개
- CIK별 PIT 준비 완료: 153개
- 전체 `pit_ready=false`

Company Facts 404는 빈 재무 데이터로 대체하지 않고
`COMPANYFACTS_UNAVAILABLE`로 보존한다. 제공된 153개 CIK는 최근 10년
관측값의 accession이 모두 `acceptanceDateTime`에 연결됐다. 그러나 4개
CIK의 공식 재무 데이터가 없고 S&P 구성 원장도 미완성이므로 전체 연구
데이터는 아직 채택 검증에 사용할 수 없다.
