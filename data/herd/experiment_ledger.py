"""사전등록 HERD 실험의 입력·결과·판정을 해시 체인으로 검증한다."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
LEDGER_PATH = Path(__file__).with_name("experiment_ledger.json")
LEDGER_VERSION = "HERD_EXPERIMENT_LEDGER_V1"


class ExperimentLedgerError(RuntimeError):
    """실험 원장이 불완전하거나 원본과 불일치할 때 발생한다."""


def _canonical_json(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def record_sha256(record: dict) -> str:
    payload = {key: value for key, value in record.items() if key != "record_sha256"}
    return hashlib.sha256(_canonical_json(payload)).hexdigest()


def _repository_file(relative_path: str) -> Path:
    candidate = (REPOSITORY_ROOT / relative_path).resolve()
    if not candidate.is_relative_to(REPOSITORY_ROOT):
        raise ExperimentLedgerError(f"path escapes repository: {relative_path}")
    if not candidate.is_file():
        raise ExperimentLedgerError(f"missing experiment artifact: {relative_path}")
    return candidate


def validate_ledger(ledger: dict) -> dict:
    if ledger.get("ledger_version") != LEDGER_VERSION:
        raise ExperimentLedgerError("unsupported ledger version")

    records = ledger.get("records", [])
    if not records:
        raise ExperimentLedgerError("experiment ledger is empty")

    seen_ids: set[str] = set()
    previous_hash = None
    total_declared_tests = 0
    decisions: dict[str, int] = {}

    for expected_sequence, record in enumerate(records, start=1):
        experiment_id = record.get("experiment_id")
        if record.get("sequence") != expected_sequence:
            raise ExperimentLedgerError("record sequence is not contiguous")
        if not experiment_id or experiment_id in seen_ids:
            raise ExperimentLedgerError("experiment id is missing or duplicated")
        if record.get("previous_record_sha256") != previous_hash:
            raise ExperimentLedgerError(f"broken hash chain: {experiment_id}")
        if record.get("promotion_allowed") is not False:
            raise ExperimentLedgerError(
                f"research result cannot promote itself: {experiment_id}"
            )
        declared_tests = record.get("declared_test_count")
        if not isinstance(declared_tests, int) or declared_tests <= 0:
            raise ExperimentLedgerError(f"invalid test count: {experiment_id}")

        for kind in ("protocol", "report"):
            artifact = _repository_file(record[f"{kind}_path"])
            if _sha256(artifact) != record.get(f"{kind}_sha256"):
                raise ExperimentLedgerError(
                    f"{kind} hash mismatch: {experiment_id}"
                )

        calculated_hash = record_sha256(record)
        if calculated_hash != record.get("record_sha256"):
            raise ExperimentLedgerError(f"record hash mismatch: {experiment_id}")

        decision = record.get("decision")
        if not decision:
            raise ExperimentLedgerError(f"missing decision: {experiment_id}")
        decisions[decision] = decisions.get(decision, 0) + 1
        total_declared_tests += declared_tests
        previous_hash = calculated_hash
        seen_ids.add(experiment_id)

    return {
        "ledger_version": LEDGER_VERSION,
        "record_count": len(records),
        "declared_test_count": total_declared_tests,
        "head_sha256": previous_hash,
        "decisions": decisions,
        "promotion_allowed": False,
    }


def load_ledger(path: Path = LEDGER_PATH) -> tuple[dict, dict]:
    ledger = json.loads(path.read_text(encoding="utf-8"))
    return ledger, validate_ledger(ledger)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ledger", type=Path, default=LEDGER_PATH)
    args = parser.parse_args()
    _, audit = load_ledger(args.ledger)
    print(json.dumps(audit, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
