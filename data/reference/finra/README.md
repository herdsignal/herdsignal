# FINRA reference data

공식 FINRA 원본을 로컬에 보존하는 디렉터리입니다. 대용량 원본과 receipt는
Git에 넣지 않고, 추적 가능한 전체 해시 manifest만 `data/herd`에 커밋합니다.

현재 corpus:

- `short-interest-census-v1-202106-20260723/`
- 원본: `raw/{settlement_date}/{sha256}.csv`
- 최초 수집 receipt: `receipts/{settlement_date}/{sha256}.json`
- 로컬 manifest: `manifest.json`

재수집 시 같은 결제기준일의 SHA-256이 달라지면 기존 파일을 덮어쓰지 않고 새
버전으로 추가합니다. FINRA가 census 시작 전에 교체한 과거 정정본은 복원할 수
없습니다.
