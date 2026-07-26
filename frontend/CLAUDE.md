# frontend/ — React UI

최종 업데이트: 2026-07-26

## 역할

Spring Boot API의 State S1 관찰값과 사용자 포트폴리오를 보여준다. 프론트에서
HERD 점수나 행동 비율을 계산하지 않는다. 현재 운영 행동 모델은 승인되지 않았으므로
모든 기본 화면은 상태·전환·근거·사용자 기록만 다룬다.

## 화면 구조

```text
src/
├── api/                 API 호출 경계
├── auth/                로그인·보호 라우트
├── components/
│   ├── HerdLens/        고정된 점 개수로 표현하는 HERD 상태 시각화
│   ├── MarketField/     SPY 집계 전용 시장 필드
│   ├── Layout/          상단·모바일 공통 탐색
│   ├── ModalDialog/     포커스 트랩·복귀를 포함한 공통 모달
│   └── StockAvatar/     회사 로고와 티커 fallback
├── pages/
│   ├── MarketHome/      SPY MARKET_AGGREGATE State S1
│   ├── Portfolio/       계좌 요약·자산 이력·보유 종목
│   ├── StockDetail/     개별 종목 State/Transition S1
│   ├── Search/          종목 검색과 목록 추가
│   ├── Watchlist/       관찰 종목 상태 목록
│   ├── History/         장기 자산 기록
│   ├── Journal/         사용자가 직접 남긴 판단 기록
│   ├── HerdLab/         레거시·차세대 연구 상태
│   └── Settings/        계정·투자 프로필
├── features/portfolio/  사용자별 포트폴리오 캐시
├── styles/              전역 토큰
└── utils/               통화·단계·관찰값 정규화
```

## 라우트 계약

- `/`: 공개 홈
- `/app`: SPY 시장 집계만 보여주는 로그인 후 첫 화면
- `/portfolio`: 총자산, 주식 평가액, 현금, 오늘 등락, 통화 전환, 자산 이력,
  보유 비중·평가액·수익률·HERD
- `/stock/:ticker`: 개별 종목 State S1, Transition S1, 네 증거군, 과거 흐름
- `/search`: 검색, State S1 준비 상태, 포트폴리오·관찰 목록 추가
- `/watchlist`: 낮은 HERD부터 높은 HERD까지 상태 관찰
- `/history`, `/journal`, `/herd-lab`, `/settings`: 보조 화면

SPY `MARKET_AGGREGATE`와 개별 종목 점수는 같은 의미로 표현하지 않는다. v4·v6.1은
`/herd-lab`의 레거시 연구 기록이며 기본 화면의 매수·익절 권고로 사용하지 않는다.

## UI 원칙

- 문장으로 설득하지 않고 숫자, 위치, 밀도, 변화로 먼저 보여준다.
- Flee–Scatter–Calm–Drift–Rush 색은 의미가 있을 때만 사용한다.
- 고정된 점 개수가 흩어지고 밀집되는 `HERD Lens`를 제품의 시각 언어로 사용한다.
- loading, empty, partial error, unavailable, stale을 정상 화면 상태로 설계한다.
- 페이지 JSX는 조립, `use*Data`는 I/O와 비동기 상태, `*Model`은 순수 계산을 담당한다.
- 동일 정보를 시장 홈과 포트폴리오에 중복 배치하지 않는다.
- 승인되지 않은 `BUY`, `SELL`, 행동 비율, 행동 우선순위는 화면에서 파생하지 않는다.

기준 시안은 `wireframes/wireframe-portfolio-lens-v6.html`이며 전환·삭제 기준은
이 문서의 라우트 계약과 검증 항목으로 관리한다.

## 캐시

- `hs_portfolio_realtime:{userId}`: 포트폴리오 평가 요약
- `hs_portfolio_herd:{userId}`: 보유 종목 State S1
- `hs_portfolio_herd_time:{userId}`: 관찰값 저장 시각
- `hs_cache_time:{userId}`: 포트폴리오 요약 저장 시각
- `hs_portfolio_cache_version`: 포트폴리오 캐시 스키마 버전
- `hs_recent_searches`: 최근 검색
- `herdsignal_currency`: KRW/USD 표시
- `herdsignal_portfolio_lens_sort`: 포트폴리오 정렬

사용자가 바뀌면 포트폴리오 캐시는 섞이지 않아야 한다. 캐시 오류는 API 재조회로
복구하며, 시장 캐시와 포트폴리오 캐시를 한 번에 지우지 않는다.

## 검증

```bash
npm run lint
npm test -- --run
npm run build
npm run test:bundle
npm run test:visual
```

- Vitest는 상태 정규화, 캐시 격리, 요청 경합과 핵심 렌더링 계약을 검증한다.
- Playwright는 공개 홈·로그인과 보호된 9개 화면 전체를 1920px 와이드,
  1440px 데스크톱, 412px 모바일에서 캡처하고 키보드 탐색·가로 넘침을 검사한다.
- 의도적인 화면 변경 때만 `npm run test:visual:update`를 실행한다.
- 번들 예산은 `frontend/scripts/checkBundleBudget.mjs`에서 관리한다.

## 화면 비율 계약

- 콘텐츠 최대 폭은 `1680px`, 좌우 여백은 `20~48px` 범위에서 반응형으로 적용한다.
- 일반 정보 글자는 `11px` 미만으로 내리지 않는다. 기본 계층은
  micro 11, label 12, body-small 13, body 14, subtitle 16, title 28px이다.
- `Layout.main`이 공통 콘텐츠 폭과 좌우 여백을 소유한다. 개별 페이지는 같은
  수평 여백을 중복 적용하지 않는다.
- 기존 `--bg`, `--surface`, `--border`, `--text-*` 토큰은 `--hs-*` 의미 토큰의
  별칭으로 유지해 신규 화면과 연구·기록 화면의 색 계층을 일치시킨다.

## 작업 원칙

- API 호출은 `src/api/herdApi.js`에 모은다.
- 실제 구현을 문서보다 우선하고, 구현 변경과 함께 이 문서를 갱신한다.
- 연구 결과 재현을 위한 backend/data 파일은 프론트 정리 범위로 삭제하지 않는다.
- 새 행동 모델은 backend의 승격 경계를 통과한 뒤 별도 제품 설계로 연결한다.
