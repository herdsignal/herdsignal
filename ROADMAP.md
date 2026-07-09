# HerdSignal Roadmap

## 1. HerdSignal이란

HerdSignal은 미국 주식 장기투자자가 매수와 익절 타이밍을 데이터로 판단하도록 돕는 도구다.
포트폴리오 트래커가 아니라 보유 종목과 관심 종목의 HERD Index를 기준으로 추가매수, 보유, 익절 판단을 정리하는 타이밍 엔진이다.

## 2. Core Principle

HERD Index는 군중의 이탈, 흩어짐, 균형, 쏠림, 밀집을 종목별 역사 데이터 기준으로 해석해 행동 가능한 타이밍 신호로 바꾼다. HerdSignal은 점수를 보여주는 데서 끝나지 않고, 장기투자자가 실제로 취할 수 있는 추가매수, 보유, 일부 익절, 적극 익절 행동으로 번역한다.

- v1: RSI와 가격 위치 중심의 기본 심리 지표
- v2: 장기 추세 지표와 백테스트 기반 가중치 개선
- v3: 거래량 비활성화, 200주 MA와 장기 구조 반영
- v4: EPS 서프라이즈와 섹터 상대 강도 보정
- v5: Balanced Action Layer로 HERD 점수를 장기투자 행동 추천으로 확장
- v6: 섹터별 파라미터 분리
- v7: ML 기반 가중치 최적화

## 3. Now

- MVP 집중: Dashboard, Watchlist, Search, HERD Lab
- HERD_v5 Balanced Action Layer 안정화
- 실제 사용 중 HERD 신호 신뢰도와 판단 기록 품질 점검

## 4. Next

- 1~2주 로컬 실사용 후 Dashboard/Watchlist/Search 마찰 제거
- StockDetail 판단 기록을 장기 매매 일지로 더 확장
- 신호 알림 전 단계: 일간/주간 확인 루틴 설계
- HERD_v6 후보: Rush/Flee 내부 강도와 피크아웃/바닥 확인 백테스트
- 종목별 HERD 백테스트 카드

## 5. Later

- 멀티유저와 인증
- 공식 증권사 API 연동, 토스증권 API 공개 시 검토
- 저마찰 포트폴리오 import 흐름
- 알림 시스템: 강한 Flee/Rush, 목표비중 이탈, 장기 신호 지속만 대상으로 제한
- Claude API 기반 리밸런싱 설명
- 섹터별 파라미터 분리, v6
- ML 기반 가중치 최적화, v7

## 6. Done

- HERD 알고리즘, v1~v4
- 전체 데이터 파이프라인
- HERD_v5 Balanced Action Layer
- Dashboard: Signal Command Center, SPY Herd Flow, Action Queue, 현금 포함 포트폴리오 요약, 총자산 히스토리
- StockDetail: 결론, 근거, 신뢰도, HERD 히스토리, 재무 가드, 판단 기록
- Watchlist: 매수 대기열, Action Queue 리스트
- Search: 심볼 검색, HERD 미리보기, 편입 판단, 데이터 품질 상태
- HERD Lab: 모델 버전, 백테스트 요약, Action Matrix
