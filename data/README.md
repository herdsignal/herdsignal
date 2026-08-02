# HerdSignal 데이터 디렉터리

`data/`는 운영 코드, 재현 가능한 연구 코드, 대용량 원문을 함께 담고 있어
역할을 구분해서 다룬다.

## 보존 등급

| 등급 | 경로 | 원칙 |
| --- | --- | --- |
| 운영 | `scheduler/`, `collectors/`, `indicators/`, `config/` | 서비스 실행과 함께 테스트한다 |
| 현재 연구 | `herd/`의 `ACTIVE`, `DATA_PIPELINE` 산출물 | 카탈로그와 해시를 유지한다 |
| 연구 이력 | `REJECTED`, `LEGACY_REFERENCE`, `DIAGNOSTIC` | 새 모델 입력으로 재사용하지 않고 재현용으로 보존한다 |
| 런타임 | `runtime/` | Git에 넣지 않고 최신 관찰과 복구에 사용한다 |
| 대용량 원문 | `reference/`, `snapshots/`, `walk_forward/` | Git에 넣지 않고 manifest·SHA-256으로 식별한다 |

연구 산출물의 현재 분류는
`herd/research_artifact_catalog_v2.json`이 담당한다. 새 JSON·CSV·문서는
`REVIEW_REQUIRED`로 차단되며 분류 없이 회귀 검증을 통과할 수 없다.

## 삭제 기준

다음 조건을 모두 만족하기 전에는 원문이나 버전별 연구 파일을 삭제하지 않는다.

1. Git import와 문서 참조가 없다.
2. 고정 manifest 또는 해시 입력이 아니다.
3. 실험 판정 재현에 필요하지 않다.
4. 별도 백업 또는 재수집 경로가 확인됐다.
5. 삭제 후 `./scripts/verify.sh`가 통과한다.

대용량 원문은 iCloud 동기화 폴더보다 로컬 비동기 경로 또는 외장 저장소에
두는 것을 권장한다. Git에는 원문 대신 계약, manifest, 해시와 작은 검수
표본만 남긴다.
