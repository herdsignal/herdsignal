"""최신 Tier1 실행과 State S1 발행 결과를 하나의 계약으로 감사한다."""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_DATA_DIR = Path(__file__).resolve().parent.parent
if str(_DATA_DIR) not in sys.path:
    sys.path.insert(0, str(_DATA_DIR))

from config.database import create_db_engine, get_session_factory
from init_db import HerdObservation, SchedulerRun
from scheduler.observation_s1 import ROOT, load_service_contract
from scheduler.observation_store import validate_observation_bundle


JOB_NAME = "HERD_TIER1_DAILY"
_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class AuditCheck:
    name: str
    passed: bool
    detail: str


def _utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _ticker_list(raw: str | None, field_name: str) -> list[str]:
    if not raw:
        return []
    payload = json.loads(raw)
    if not isinstance(payload, list) or not all(isinstance(item, str) for item in payload):
        raise ValueError(f"{field_name} must be a JSON string array")
    return sorted({item.strip().upper() for item in payload if item.strip()})


def _check(name: str, passed: bool, detail: str) -> AuditCheck:
    return AuditCheck(name=name, passed=passed, detail=detail)


def evaluate_completion(
    *,
    run: dict[str, Any],
    bundle: dict[str, Any],
    contract: dict[str, Any],
    stored_pairs: set[tuple[str, str]],
) -> dict[str, Any]:
    """DB 접근과 분리된 완결 판정. 테스트와 운영 명령이 같은 규칙을 쓴다."""
    validated = validate_observation_bundle(bundle)
    expected_pairs = {
        (str(item["ticker"]), item["observation_date"].isoformat())
        for item in validated
    }
    missing_pairs = sorted(expected_pairs - stored_pairs)
    reference = bundle["referenceUniverse"]
    expected_reference = int(contract["reference_universe"]["expected_equities"])
    minimum_coverage = float(
        contract["reference_universe"]["minimum_total_coverage_fraction"]
    )
    failed = list(run["failed_tickers"])
    skipped = list(run["skipped_tickers"])
    generated_at = datetime.fromisoformat(
        str(bundle["generatedAt"]).replace("Z", "+00:00")
    ).astimezone(UTC)
    started_at = _utc(run["started_at"])
    finished_at = _utc(run["finished_at"])
    publish_status = run.get("publish_status")
    universe_sha256 = run.get("universe_sha256")
    publish_contract_recorded = publish_status is not None or universe_sha256 is not None

    checks = [
        _check(
            "run_finished_successfully",
            run["status"] == "SUCCESS" and finished_at is not None,
            f"status={run['status']}",
        ),
        _check(
            "state_publish_succeeded",
            (
                publish_status == "SUCCESS"
                if publish_contract_recorded
                else run["status"] == "SUCCESS"
            ),
            (
                f"publish={publish_status}"
                if publish_contract_recorded
                else "legacy_pre_v8=true"
            ),
        ),
        _check(
            "ticker_universe_contract_recorded",
            (
                bool(_SHA256_PATTERN.fullmatch(str(universe_sha256)))
                if publish_contract_recorded
                else True
            ),
            (
                f"sha256={universe_sha256}"
                if publish_contract_recorded
                else "legacy_pre_v8=true"
            ),
        ),
        _check(
            "ticker_count_arithmetic",
            run["total_count"] > 0
            and run["success_count"] + run["skipped_count"] == run["total_count"]
            and run["failed_count"] == 0
            and not failed,
            (
                f"total={run['total_count']} success={run['success_count']} "
                f"skipped={run['skipped_count']} failed={run['failed_count']}"
            ),
        ),
        _check(
            "reference_universe_locked",
            int(reference["expected"]) == expected_reference,
            f"expected={reference['expected']} contract={expected_reference}",
        ),
        _check(
            "reference_coverage",
            float(reference["coverageFraction"]) >= minimum_coverage,
            (
                f"coverage={float(reference['coverageFraction']):.4f} "
                f"minimum={minimum_coverage:.4f}"
            ),
        ),
        _check(
            "bundle_belongs_to_run",
            started_at is not None
            and generated_at >= started_at
            and (finished_at is None or generated_at <= finished_at),
            (
                f"started={started_at.isoformat() if started_at else None} "
                f"generated={generated_at.isoformat()} "
                f"finished={finished_at.isoformat() if finished_at else None}"
            ),
        ),
        _check(
            "observation_rows_committed",
            not missing_pairs,
            f"expected={len(expected_pairs)} missing={len(missing_pairs)}",
        ),
    ]
    passed = all(item.passed for item in checks)
    return {
        "status": "PASS" if passed else (
            "RUNNING" if run["status"] == "RUNNING" else "FAIL"
        ),
        "passed": passed,
        "runId": run["id"],
        "publishStatus": publish_status,
        "universeSha256": universe_sha256,
        "failedTickers": failed,
        "skippedTickers": skipped,
        "missingObservationPairs": [
            {"ticker": ticker, "observationDate": observation_date}
            for ticker, observation_date in missing_pairs
        ],
        "checks": [asdict(item) for item in checks],
    }


def audit_latest_run() -> dict[str, Any]:
    contract = load_service_contract()
    output_path = (ROOT / contract["runtime_output"]).resolve()
    session_factory = get_session_factory(create_db_engine())
    with session_factory() as session:
        row = (
            session.query(SchedulerRun)
            .filter(SchedulerRun.job_name == JOB_NAME)
            .order_by(SchedulerRun.started_at.desc())
            .first()
        )
        if row is None:
            raise RuntimeError("scheduler run history is empty")
        run = {
            "id": row.id,
            "status": row.status,
            "started_at": row.started_at,
            "finished_at": row.finished_at,
            "total_count": int(row.total_count or 0),
            "success_count": int(row.success_count or 0),
            "failed_count": int(row.failed_count or 0),
            "failed_tickers": _ticker_list(row.failed_tickers, "failed_tickers"),
            "skipped_count": int(row.skipped_count or 0),
            "skipped_tickers": _ticker_list(
                row.skipped_tickers, "skipped_tickers"
            ),
            "publish_status": row.publish_status,
            "universe_sha256": row.universe_sha256,
        }
    if not output_path.is_relative_to(ROOT) or not output_path.is_file():
        running = run["status"] == "RUNNING"
        return {
            "status": "RUNNING" if running else "FAIL",
            "passed": False,
            "runId": run["id"],
            "failedTickers": run["failed_tickers"],
            "skippedTickers": run["skipped_tickers"],
            "missingObservationPairs": [],
            "checks": [
                asdict(_check(
                    "observation_bundle_exists",
                    False,
                    f"missing={output_path}",
                ))
            ],
        }

    bundle = json.loads(output_path.read_text(encoding="utf-8"))
    with session_factory() as session:
        record_tickers = sorted(bundle.get("records", {}))
        rows = (
            session.query(
                HerdObservation.ticker,
                HerdObservation.observation_date,
            )
            .filter(
                HerdObservation.state_model_version
                == bundle["stateModelVersion"],
                HerdObservation.ticker.in_(record_tickers),
            )
            .all()
        )
        stored_pairs = {
            (str(ticker), observation_date.isoformat())
            for ticker, observation_date in rows
        }
    return evaluate_completion(
        run=run,
        bundle=bundle,
        contract=contract,
        stored_pairs=stored_pairs,
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="최신 Tier1 실행과 State S1 DB 발행을 감사합니다."
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="감사 JSON을 저장할 선택 경로",
    )
    args = parser.parse_args()
    result = audit_latest_run()
    rendered = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    if result["passed"]:
        return 0
    return 2 if result["status"] == "RUNNING" else 1


if __name__ == "__main__":
    raise SystemExit(main())
