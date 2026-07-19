# HERD 재현 가능한 연구 계약

HERD 후보는 같은 데이터와 같은 시간 분할로 다시 실행했을 때 같은 결과가
나와야 비교 대상이 된다. 이 문서는 데이터 스냅샷과 Walk-forward 산출물의
고정 규칙이다.

## 1. 가격 데이터 스냅샷

### 목적

- 실행할 때마다 외부 API에서 달라지는 가격을 다시 받지 않는다.
- 어떤 종목, 기간, 조정 방식으로 검증했는지 파일 단위로 추적한다.
- 파일 누락이나 사후 수정을 검증 전에 차단한다.

### 저장 구조

```text
data/snapshots/<snapshot-id>/
├── manifest.json
└── prices/
    ├── AAPL.csv.gz
    └── ...
```

`manifest.json`에는 다음을 기록한다.

- 스냅샷 형식 버전과 생성 시각
- 데이터 공급자와 수집 옵션
- 유니버스 버전과 요청·완료 종목
- 종목별 행 수, 시작일, 종료일, 파일 크기, SHA-256
- 전체 manifest의 SHA-256

가격 파일은 `Date, Open, High, Low, Close, Volume` 순서의 gzip CSV로
고정한다. 날짜 오름차순, 중복 날짜 없음, 유한한 양수 OHLC, 음수가 아닌
거래량을 강제한다. 생성은 임시 디렉터리에서 완료한 뒤 한 번에 이동하며,
이미 존재하는 스냅샷은 덮어쓰지 않는다.

검증 코드는 manifest와 모든 파일의 해시를 확인한 스냅샷만 읽는다.
외부 API와 스냅샷을 한 실행에서 섞지 않는다.

## 2. 시간축 Walk-forward

### 분할 규칙

- 폴드는 시간 순서만 사용한다.
- 기본 학습 최소 길이: 4년
- 기본 테스트 길이: 1년
- 기본 이동 간격: 1년
- 학습 구간은 누적 anchored 방식이다.
- 최초 학습 구간 4년을 확보한 뒤 경계 간격을 별도로 둔다.
- 학습 말단에서 `purge_days`만큼 제거한다.
- purge 뒤에 `embargo_days`만큼 추가 간격을 둔다.
- 테스트 구간은 서로 겹치지 않는다.

`purge_days`는 학습 라벨의 미래 참조 길이 이상이어야 한다. 일별 전략
수익률 검증 기본값은 1거래일이다. 12개월 선행수익률을 학습 라벨로 쓰는
연구는 별도 실행에서 252거래일 이상으로 올려야 한다.

### 저장 구조

```text
data/walk_forward/<run-id>/
├── manifest.json
├── folds.csv
├── fold_metrics.csv
└── daily_returns.csv.gz
```

- `folds.csv`: 실제 학습·간격·테스트 경계와 관측 수
- `fold_metrics.csv`: 폴드·종목·후보별 CAGR, MDD, Sortino, Calmar,
  상승·하락 포착률, 회전율
- `daily_returns.csv.gz`: 날짜별 전략 수익률, Buy & Hold 수익률, 자산,
  노출 비중
- `manifest.json`: 입력 스냅샷 해시, 실행 설정, 후보 목록, 각 산출물 해시

산출물은 임시 디렉터리에서 작성하고 검증한 뒤 원자적으로 확정한다.
동일한 `run-id`를 덮어쓰지 않는다. 이 실행기는 holdout 기간을 임의로
정하지 않는다. Blind holdout을 잠근 뒤에는 `research_end`를 그 시작일
이전으로 지정해 연구 산출물에서 제외해야 한다.

## 3. 판정 원칙

스냅샷과 시간 분할은 모델 성능을 본 뒤 바꾸지 않는다. 후보가 탈락해도
실행 manifest와 일별 수익률을 보존한다. 집계 결과만 저장한 과거 보고서는
참고 기록일 뿐 차세대 HERD 채택 근거로 사용하지 않는다.

## 근거

- scikit-learn `TimeSeriesSplit`: 시간 순서를 보존하고 train과 test 사이
  `gap`을 지원한다.
- López de Prado의 purged/embargoed cross-validation: 라벨 구간 중첩과
  시계열 의존성에 의한 누출을 줄인다.
- pandas gzip의 고정 `mtime`: 동일 입력 파일을 재현 가능한 바이트로
  저장할 수 있다.
- SHA-256: 파일 무결성과 실행 입력 식별에 사용한다.
