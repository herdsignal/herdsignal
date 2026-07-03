# HerdSignal Roadmap

## 1. HerdSignal이란

HerdSignal은 미국 주식 장기투자자가 매수와 익절 타이밍을 데이터로 판단하도록 돕는 도구다.
감정이 아니라 종목별 HERD Index와 포트폴리오 맥락을 기준으로 행동을 제안한다.

## 2. Core Principle

HERD Index는 군중의 이탈, 흩어짐, 균형, 쏠림, 밀집을 종목별 역사 데이터 기준으로 해석해 행동 가능한 타이밍 신호로 바꾼다. HerdSignal은 점수를 보여주는 데서 끝나지 않고, 장기투자자가 실제로 취할 수 있는 추가매수, 보유, 일부 익절, 적극 익절 행동으로 번역한다.

- v1: RSI와 가격 위치 중심의 기본 심리 지표
- v2: 장기 추세 지표와 백테스트 기반 가중치 개선
- v3: 거래량 비활성화, 200주 MA와 장기 구조 반영
- v4: EPS 서프라이즈와 섹터 상대 강도 보정
- v5~v6: 섹터별 파라미터 분리와 ML 기반 가중치 최적화

## 3. Now

- Phase 3: Decision Engine 고도화
- AI 리밸런싱 MVP 완성, Claude API 연결 전 규칙 기반 판단 강화
- HERD 신뢰도, Watchlist 기회 큐, 새로고침 UX 정리

## 4. Next

- Claude API 기반 리밸런싱 설명 생성
- HERD 데이터 품질과 신뢰도 표시
- Watchlist 매수 대기열 고도화
- StockDetail 판단 요약 고도화
- Railway 배포 준비

## 5. Later

- 멀티유저와 인증
- 증권사 연동, 토스증권 API
- 알림 시스템
- 섹터별 파라미터 분리, v5
- ML 기반 가중치 최적화, v6

## 6. Done

- HERD 알고리즘, v1~v4
- 전체 데이터 파이프라인
- Dashboard: SPY Herd Flow, 포트폴리오 요약, 목표 비중 리밸런싱, 자산 진단
- StockDetail: HERD v4, 차트, 재무, 판단 요약, 다음 행동
- Watchlist, Search, History, 규칙 기반 AI 리밸런싱, Herd Flow Preview
