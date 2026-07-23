"""FINRA short-interest corpus를 append-only 방식으로 증분 갱신한다."""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from email.message import Message
from pathlib import Path
from typing import Callable

from herd.finra_short_interest_census_v1 import (
    PROTOCOL as V1_PROTOCOL,
    ROOT,
    _download,
    _sha256_bytes,
    _sha256_file,
    _write_version,
    parse_file,
)


PROTOCOL = Path(__file__).with_suffix(".json")
MANIFEST = Path(__file__).with_name(
    "finra_short_interest_incremental_v2_manifest.json"
)
REPORT = ROOT / "data/reports/finra_short_interest_incremental_v2.json"


class FinraIncrementalV2Error(RuntimeError):
    pass


def _rooted(relative: str) -> Path:
    path = (ROOT / relative).resolve()
    if not path.is_relative_to(ROOT.resolve()):
        raise FinraIncrementalV2Error(f"path escapes repository: {relative}")
    return path


def _display_path(path: Path) -> str:
    resolved = path.resolve()
    if resolved.is_relative_to(ROOT.resolve()):
        return resolved.relative_to(ROOT.resolve()).as_posix()
    return resolved.as_posix()


def _atomic_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def _parse_instant(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise FinraIncrementalV2Error(f"timezone required: {value}")
    return parsed.astimezone(timezone.utc)


def load_and_verify(protocol_path: Path = PROTOCOL) -> tuple[dict, dict, dict]:
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    if protocol["status"] != "LOCKED_BEFORE_INCREMENTAL_COLLECTION":
        raise FinraIncrementalV2Error("incremental protocol is not locked")
    baseline_ref = protocol["baseline_manifest"]
    baseline_path = _rooted(baseline_ref["path"])
    if _sha256_file(baseline_path) != baseline_ref["sha256"]:
        raise FinraIncrementalV2Error("baseline FINRA manifest changed")
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    gate_ref = protocol["lifecycle_gate"]
    gate_path = _rooted(gate_ref["path"])
    if _sha256_file(gate_path) != gate_ref["sha256"]:
        raise FinraIncrementalV2Error("lifecycle gate report changed")
    gate = json.loads(gate_path.read_text(encoding="utf-8"))
    if (
        gate["status"] != gate_ref["required_status"]
        or gate["decision"] != gate_ref["required_decision"]
    ):
        raise FinraIncrementalV2Error("lifecycle gate contract changed")
    if gate["primary_long_horizon_oos_allowed"]:
        raise FinraIncrementalV2Error("FINRA authority unexpectedly expanded")
    return protocol, baseline, gate


def verify_baseline_entries(entries: list[dict]) -> None:
    for entry in entries:
        raw = _rooted(entry["raw_path"])
        receipt = _rooted(entry["receipt_path"])
        if _sha256_file(raw) != entry["sha256"]:
            raise FinraIncrementalV2Error(
                f"baseline raw hash mismatch: {entry['raw_path']}"
            )
        receipt_payload = json.loads(receipt.read_text(encoding="utf-8"))
        if receipt_payload["sha256"] != entry["sha256"]:
            raise FinraIncrementalV2Error(
                f"baseline receipt mismatch: {entry['receipt_path']}"
            )


def _resume_entries(
    protocol_path: Path,
    manifest_path: Path,
    baseline: dict,
) -> list[dict]:
    if not manifest_path.exists():
        return list(baseline["entries"])
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest["manifest_version"] != "FINRA_SHORT_INTEREST_INCREMENTAL_V2":
        raise FinraIncrementalV2Error("unexpected incremental manifest version")
    baseline_keys = {
        (row["settlement_date"], row["sha256"])
        for row in baseline["entries"]
    }
    resumed_keys = {
        (row["settlement_date"], row["sha256"])
        for row in manifest["entries"]
    }
    if not baseline_keys.issubset(resumed_keys):
        raise FinraIncrementalV2Error(
            "incremental manifest dropped a baseline hash version"
        )
    if manifest["protocol_sha256"] != _sha256_file(protocol_path):
        if resumed_keys == baseline_keys:
            return list(baseline["entries"])
        raise FinraIncrementalV2Error("incremental manifest protocol changed")
    return list(manifest["entries"])


def _url(protocol: dict, settlement_date: str) -> str:
    return protocol["official_source"]["download_template"].format(
        settlement_yyyymmdd=settlement_date.replace("-", "")
    )


def _entry(
    raw_path: Path,
    receipt_path: Path,
) -> dict:
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    return {
        **receipt,
        "raw_path": _display_path(raw_path),
        "receipt_path": _display_path(receipt_path),
    }


def _merge_entries(entries: list[dict]) -> list[dict]:
    unique = {
        (row["settlement_date"], row["sha256"]): row
        for row in entries
    }
    return [
        unique[key] for key in sorted(unique)
    ]


def _build_manifest(
    protocol_path: Path,
    protocol: dict,
    entries: list[dict],
    collected_at: str,
    new_versions: int,
    revision_probe_dates: list[str],
) -> dict:
    versions_by_date: dict[str, int] = {}
    for entry in entries:
        day = entry["settlement_date"]
        versions_by_date[day] = versions_by_date.get(day, 0) + 1
    return {
        "manifest_version": "FINRA_SHORT_INTEREST_INCREMENTAL_V2",
        "protocol_path": _display_path(protocol_path),
        "protocol_sha256": _sha256_file(protocol_path),
        "created_at_utc": collected_at,
        "research_tier": protocol["research_tier"],
        "allowed_research_role": protocol["authority"][
            "allowed_research_role"
        ],
        "file_count": len(entries),
        "settlement_date_count": len(versions_by_date),
        "first_settlement_date": entries[0]["settlement_date"],
        "last_settlement_date": entries[-1]["settlement_date"],
        "total_bytes": sum(row["bytes"] for row in entries),
        "total_rows": sum(row["row_count"] for row in entries),
        "revision_flag_rows": sum(
            row["revision_flag_rows"] for row in entries
        ),
        "settlement_dates_with_multiple_local_versions": sorted(
            day for day, count in versions_by_date.items() if count > 1
        ),
        "new_versions_this_run": new_versions,
        "revision_probe_dates": revision_probe_dates,
        "source_revision_limitation": (
            "Only versions observed after local collection can be preserved; "
            "FINRA exposes only the most recent corrected item."
        ),
        "entries": entries,
        "authority": protocol["authority"],
    }


def collect_incremental(
    protocol_path: Path = PROTOCOL,
    manifest_path: Path = MANIFEST,
    report_path: Path = REPORT,
    timeout: int = 60,
    now: datetime | None = None,
    downloader: Callable[[str, int], tuple[bytes, Message]] = _download,
) -> dict:
    protocol, baseline, gate = load_and_verify(protocol_path)
    entries = _resume_entries(
        protocol_path,
        manifest_path,
        baseline,
    )
    resumed_existing_incremental_manifest = (
        len(entries) > len(baseline["entries"])
    )
    if protocol["incremental_policy"]["verify_every_baseline_hash_before_publish"]:
        verify_baseline_entries(entries)
    v1 = json.loads(V1_PROTOCOL.read_text(encoding="utf-8"))
    corpus_root = _rooted(v1["immutable_storage"]["local_root"])
    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    retrieved_at = current.isoformat()
    existing_dates = sorted({row["settlement_date"] for row in entries})
    probe_count = protocol["incremental_policy"]["recent_revision_probe_count"]
    revision_probe_dates = existing_dates[-probe_count:]
    attempts: list[tuple[str, str]] = [
        (day, "REVISION_PROBE") for day in revision_probe_dates
    ]
    pending = []
    for candidate in protocol["scheduled_candidates"]:
        day = candidate["settlement_date"]
        if day in existing_dates:
            continue
        if current < _parse_instant(candidate["download_not_before"]):
            pending.append({
                **candidate,
                "status": "PENDING_OFFICIAL_PUBLICATION_WINDOW",
            })
            continue
        attempts.append((day, "NEW_SCHEDULED_FILE"))

    new_versions = 0
    attempt_results = []
    for settlement, purpose in attempts:
        url = _url(protocol, settlement)
        try:
            content, headers = downloader(url, timeout)
        except Exception as error:
            if (
                purpose == "REVISION_PROBE"
                and protocol["incremental_policy"][
                    "revision_probe_is_best_effort"
                ]
            ):
                attempt_results.append({
                    "settlement_date": settlement,
                    "purpose": purpose,
                    "status": "REVISION_PROBE_UNAVAILABLE",
                    "error_type": type(error).__name__,
                })
                continue
            raise FinraIncrementalV2Error(
                f"due FINRA file unavailable: {settlement}"
            ) from error
        parsed = parse_file(content, v1["required_columns"])
        if parsed.settlement_date != settlement:
            raise FinraIncrementalV2Error(
                f"filename/content date mismatch: {settlement}"
            )
        digest = _sha256_bytes(content)
        raw_path, receipt_path, created = _write_version(
            corpus_root,
            parsed,
            content,
            digest,
            url,
            headers,
            retrieved_at,
        )
        entries.append(_entry(raw_path, receipt_path))
        new_versions += int(created)
        attempt_results.append({
            "settlement_date": settlement,
            "purpose": purpose,
            "status": "NEW_HASH_VERSION" if created else "HASH_UNCHANGED",
            "sha256": digest,
        })

    entries = _merge_entries(entries)
    manifest = _build_manifest(
        protocol_path,
        protocol,
        entries,
        retrieved_at,
        new_versions,
        revision_probe_dates,
    )
    _atomic_json(manifest_path, manifest)
    report = {
        "report_version": "FINRA_SHORT_INTEREST_INCREMENTAL_V2",
        "status": (
            "PENDING_OFFICIAL_PUBLICATION_WINDOW"
            if pending and new_versions == 0
            else "HASH_LOCKED_INCREMENTAL_CENSUS_UPDATED"
        ),
        "as_of_utc": retrieved_at,
        "baseline_settlement_date_count": baseline["settlement_date_count"],
        "resumed_existing_incremental_manifest": (
            resumed_existing_incremental_manifest
        ),
        "settlement_date_count": manifest["settlement_date_count"],
        "last_settlement_date": manifest["last_settlement_date"],
        "new_versions_this_run": new_versions,
        "pending_candidates": pending,
        "attempt_results": attempt_results,
        "all_baseline_hashes_verified": True,
        "manifest_path": _display_path(manifest_path),
        "manifest_sha256": _sha256_file(manifest_path),
        "lifecycle_gate": {
            "finra_shadow_identifier_gate_passed": gate[
                "finra_shadow_identifier_gate_passed"
            ],
            "all_target_identifiers_complete": gate[
                "all_target_identifiers_complete"
            ],
            "blocked_target_count": gate["target_gap_audit"][
                "blocked_target_count"
            ],
        },
        "primary_long_horizon_oos_allowed": False,
        "price_outcomes_opened": False,
        "direction_hypothesis_preregistered": False,
        "herd_formula_change_allowed": False,
        "operational_action_ratio": 0.0,
        "next_priority": "BUILD_UNIFIED_PROSPECTIVE_PIT_SHADOW_PANEL",
    }
    _atomic_json(report_path, report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, default=PROTOCOL)
    parser.add_argument("--manifest", type=Path, default=MANIFEST)
    parser.add_argument("--report", type=Path, default=REPORT)
    parser.add_argument("--timeout", type=int, default=60)
    args = parser.parse_args()
    print(json.dumps(
        collect_incremental(
            args.protocol,
            args.manifest,
            args.report,
            args.timeout,
        ),
        ensure_ascii=False,
        indent=2,
    ))


if __name__ == "__main__":
    main()
