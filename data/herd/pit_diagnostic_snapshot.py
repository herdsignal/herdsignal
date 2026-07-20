"""불완전한 PIT 구성 재생 결과를 연구용 진단 스냅샷으로 동결한다."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path

FORMAT_VERSION = "herd-pit-diagnostic-v1"
DATASET_STATUS = "PIT_DIAGNOSTIC_V1"
REQUIRED_ARTIFACTS = (
    "integrated_event_ledger.csv",
    "blocker_backlog.csv",
    "replay.json",
)
ALLOWED_USES = (
    "MODEL_ELIMINATION",
    "UNCERTAINTY_SENSITIVITY",
    "RESEARCH_PIPELINE_VALIDATION",
)
FORBIDDEN_USES = (
    "FINAL_MODEL_ADOPTION",
    "PRODUCTION_SIGNAL",
    "SURVIVORSHIP_SAFE_CLAIM",
)


class PitDiagnosticSnapshotError(RuntimeError):
    pass


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_json(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _validate_source(
    source: Path,
    *,
    manifest_name: str = "manifest.json",
) -> tuple[dict, dict, list[dict]]:
    source_manifest = _read_json(source / manifest_name)
    replay = _read_json(source / "replay.json")
    blockers = _read_csv(source / "blocker_backlog.csv")
    gates = source_manifest.get("gates", {})
    audit = replay.get("audit", {})

    if gates.get("regression_failures") != []:
        raise PitDiagnosticSnapshotError("source has regression failures")
    if gates.get("replay_errors") != 0 or audit.get("errors") != 0:
        raise PitDiagnosticSnapshotError("source has replay errors")
    if gates.get("survivorship_safe") is not False:
        raise PitDiagnosticSnapshotError(
            "diagnostic snapshot requires survivorship_safe=false"
        )
    blocked = gates.get("blocked_events")
    if not isinstance(blocked, int) or blocked <= 0:
        raise PitDiagnosticSnapshotError(
            "diagnostic snapshot requires explicit unresolved events"
        )
    if blocked != len(blockers) or audit.get("blocked_events") != blocked:
        raise PitDiagnosticSnapshotError("blocker counts do not agree")
    if any(row.get("promotion_allowed") != "false" for row in blockers):
        raise PitDiagnosticSnapshotError("blocked event allows promotion")
    final_count = audit.get("final_count")
    if not isinstance(final_count, int) or not 480 <= final_count <= 510:
        raise PitDiagnosticSnapshotError("implausible final constituent count")
    return source_manifest, replay, blockers


def create_snapshot(
    snapshot_id: str,
    source_pipeline: Path,
    *,
    root: Path,
    created_at: datetime | None = None,
) -> Path:
    source = Path(source_pipeline).resolve()
    destination = Path(root) / snapshot_id
    if destination.exists():
        raise PitDiagnosticSnapshotError(
            f"snapshot already exists: {destination}"
        )
    for name in ("manifest.json", *REQUIRED_ARTIFACTS):
        if not (source / name).is_file():
            raise PitDiagnosticSnapshotError(f"missing source artifact: {name}")
    source_manifest, replay, blockers = _validate_source(source)

    temporary = Path(root) / f".{snapshot_id}.tmp-{uuid.uuid4().hex}"
    temporary.mkdir(parents=True)
    try:
        copied = {}
        for name in REQUIRED_ARTIFACTS:
            target = temporary / name
            shutil.copyfile(source / name, target)
            copied[name] = {
                "bytes": target.stat().st_size,
                "sha256": _sha256(target),
            }
        source_copy = temporary / "source_manifest.json"
        shutil.copyfile(source / "manifest.json", source_copy)
        copied[source_copy.name] = {
            "bytes": source_copy.stat().st_size,
            "sha256": _sha256(source_copy),
        }

        blocker_keys = sorted(
            {
                (
                    row["candidate_effective_date"],
                    row["action"],
                    row["ticker"],
                )
                for row in blockers
            }
        )
        body = {
            "format_version": FORMAT_VERSION,
            "snapshot_id": snapshot_id,
            "status": DATASET_STATUS,
            "created_at": (
                created_at or datetime.now(timezone.utc)
            ).astimezone(timezone.utc).isoformat(),
            "source": {
                "pipeline_path": str(source),
                "pipeline_manifest_sha256": _sha256(source / "manifest.json"),
                "pipeline_format_version": source_manifest.get(
                    "format_version", ""
                ),
                "period": source_manifest.get("period", {}),
            },
            "quality": {
                "replay_errors": 0,
                "final_constituent_count": replay["audit"]["final_count"],
                "blocked_events": len(blockers),
                "survivorship_safe": False,
                "replay_complete": False,
            },
            "uncertainty": {
                "event_keys": [
                    {
                        "candidate_effective_date": effective,
                        "action": action,
                        "ticker": ticker,
                    }
                    for effective, action, ticker in blocker_keys
                ],
                "handling": "FAIL_CLOSED_AND_SCENARIO_TESTED",
            },
            "policy": {
                "allowed_uses": list(ALLOWED_USES),
                "forbidden_uses": list(FORBIDDEN_USES),
            },
            "artifacts": copied,
        }
        manifest = {
            **body,
            "snapshot_sha256": hashlib.sha256(
                _canonical_json(body)
            ).hexdigest(),
        }
        (temporary / "manifest.json").write_text(
            json.dumps(
                manifest, ensure_ascii=False, indent=2, sort_keys=True
            ) + "\n",
            encoding="utf-8",
        )
        Path(root).mkdir(parents=True, exist_ok=True)
        temporary.rename(destination)
        return destination
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise


def verify_snapshot(path: Path) -> dict:
    directory = Path(path)
    manifest = _read_json(directory / "manifest.json")
    body = {
        key: value
        for key, value in manifest.items()
        if key != "snapshot_sha256"
    }
    if manifest.get("format_version") != FORMAT_VERSION:
        raise PitDiagnosticSnapshotError("unsupported snapshot format")
    if manifest.get("status") != DATASET_STATUS:
        raise PitDiagnosticSnapshotError("unexpected snapshot status")
    if hashlib.sha256(_canonical_json(body)).hexdigest() != manifest.get(
        "snapshot_sha256"
    ):
        raise PitDiagnosticSnapshotError("manifest checksum mismatch")
    if manifest["quality"].get("survivorship_safe") is not False:
        raise PitDiagnosticSnapshotError("diagnostic snapshot promoted")
    for name, metadata in manifest["artifacts"].items():
        artifact = directory / name
        if (
            not artifact.is_file()
            or artifact.stat().st_size != metadata["bytes"]
            or _sha256(artifact) != metadata["sha256"]
        ):
            raise PitDiagnosticSnapshotError(f"{name}: checksum mismatch")
    _validate_source(directory, manifest_name="source_manifest.json")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    create = subparsers.add_parser("create")
    create.add_argument("snapshot_id")
    create.add_argument("source_pipeline", type=Path)
    create.add_argument("--root", type=Path, required=True)
    verify = subparsers.add_parser("verify")
    verify.add_argument("snapshot", type=Path)
    args = parser.parse_args()
    if args.command == "create":
        print(
            create_snapshot(
                args.snapshot_id,
                args.source_pipeline,
                root=args.root,
            )
        )
    else:
        print(
            json.dumps(
                verify_snapshot(args.snapshot), ensure_ascii=False, indent=2
            )
        )


if __name__ == "__main__":
    main()
