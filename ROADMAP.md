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
- 관심 종목 기회 대기열과 보유 종목 행동 판단 완성도

## 4. Next

- HERD 신뢰도와 Action Layer 설명 최소화
- StockDetail 핵심 정보 재정리
- CSV/엑셀 import 기반 포트폴리오 입력 지원

## 5. Later

- 멀티유저와 인증
- 공식 증권사 API 연동, 토스증권 API 공개 시 검토
- 토스증권 스크린샷/OCR import
- 알림 시스템
- Claude API 기반 리밸런싱 설명
- 섹터별 파라미터 분리, v6
- ML 기반 가중치 최적화, v7

## 6. Done

- HERD 알고리즘, v1~v4
- 전체 데이터 파이프라인
- HERD_v5 Balanced Action Layer
- Dashboard: SPY Herd Flow, 포트폴리오 요약, 핵심 리밸런싱 체크
- StockDetail: HERD v4, 차트, 재무, 판단 요약, 다음 행동
- Watchlist: 기회 대기열, 기회 점수순 HERD 카드
- Search: 심볼 검색, HERD 미리보기, 포트폴리오/관심종목 추가
- HERD Lab: 모델 버전, 백테스트 요약, Action Matrix
