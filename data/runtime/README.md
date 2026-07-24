# Runtime observations

이 디렉터리는 스케줄러가 생성하는 최신 HERD 관찰 번들을 저장한다.
JSON 본문은 DB 저장 전 복구·진단용이며 Git에 커밋하지 않는다.

현재 계약:

- `HERD_STATE_S1`: 개별 종목의 현재 군중 상태
- `HERD_TRANSITION_S1`: 최근 주간 상태 변화
- `SPY`: SPY 가격 점수가 아니라 고정 종목군의 S&P 500 군중 집계
- 행동 권한: 항상 `HOLD`, `0%`
