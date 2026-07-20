"""동결된 PIT 진단 자료에서 구성 불확실성 경계 시나리오를 생성한다."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
import uuid
from datetime import date, datetime, timezone
from pathlib import Path

from herd.daily_constituent_replay import (
    DIAGNOSTIC_EVENT_STATUSES,
    VERIFIED_STATUSES,
    apply_baseline_corrections,
    load_baseline_from_intervals,
    replay_events,
)
from herd.pit_diagnostic_snapshot import verify_snapshot

FORMAT_VERSION = "herd-pit-uncertainty-scenarios-v1"
SCENARIO_CURRENT = "CURRENT_DIAGNOSTIC"
SCENARIO_VERIFIED = "VERIFIED_ONLY"
SCENARIO_CONTINUITY = "ASSUME_CONTINUITY"
SCENARIOS = (
    SCENARIO_CURRENT,
    SCENARIO_VERIFIED,
    SCENARIO_CONTINUITY,
)
EXCLUSION_WINDOW_OBSERVATIONS = 63


class PitUncertaintyScenarioError(RuntimeError):
    pass


def _read_csv(path: Path) -> list[dict]:
    with Path(path).open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical_json(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def _assumption_key(row: dict) -> tuple[str, str]:
    return row["candidate_effective_date"], row["ticker"].upper()


def _validate_assumptions(
    blockers: list[dict],
    assumptions: list[dict],
) -> dict[tuple[str, str], dict]:
    blocker_keys = {
        (row["candidate_effective_date"], row["ticker"].upper())
        for row in blockers
    }
    by_key = {_assumption_key(row): row for row in assumptions}
    if len(by_key) != len(assumptions) or set(by_key) != blocker_keys:
        raise PitUncertaintyScenarioError(
            "assumptions must cover every blocker exactly once"
        )
    for row in assumptions:
        if (
            row.get("review_status") != "RESEARCH_SCENARIO_ONLY"
            or row.get("promotion_allowed") != "false"
        ):
            raise PitUncertaintyScenarioError(
                "assumption is not locked to research-only use"
            )
        if row.get("baseline_policy") not in {
            "USE_FROZEN_BASELINE",
            "ASSUME_OLD_MEMBER_FROM_BASELINE",
        }:
            raise PitUncertaintyScenarioError("unsupported baseline policy")
        date.fromisoformat(row["assumed_index_effective_date"])
    return by_key


def _scenario_rows(
    ledger: list[dict],
    assumptions: dict[tuple[str, str], dict],
) -> tuple[list[dict], list[dict], list[str]]:
    verified = [
        row for row in ledger if row["event_status"] in VERIFIED_STATUSES
    ]
    diagnostic = [
        row
        for row in ledger
        if row["event_status"] in DIAGNOSTIC_EVENT_STATUSES
    ]
    existing = {
        (row["candidate_effective_date"], row["ticker"].upper())
        for row in diagnostic
    }
    synthetic = []
    baseline_additions = []
    for key, assumption in assumptions.items():
        if assumption["baseline_policy"] == "ASSUME_OLD_MEMBER_FROM_BASELINE":
            baseline_additions.append(assumption["old_ticker"].upper())
        if key in existing:
            continue
        synthetic.append({
            "candidate_effective_date": assumption[
                "candidate_effective_date"
            ],
            "effective_date": assumption["assumed_index_effective_date"],
            "index_effective_date": assumption[
                "assumed_index_effective_date"
            ],
            "action": "SUCCESSION",
            "ticker": assumption["ticker"].upper(),
            "old_ticker": assumption["old_ticker"].upper(),
            "event_type": "CORPORATE_SUCCESSION",
            "event_status": "DIAGNOSTIC_CORPORATE_CONTINUITY",
            "event_sequence": "25",
            "evidence_basis": "RESEARCH_BOUNDARY_ASSUMPTION",
            "promotion_allowed": "false",
        })
    return verified, [*diagnostic, *synthetic], sorted(baseline_additions)


def _replay_scenario(
    name: str,
    baseline: set[str],
    ledger: list[dict],
    *,
    diagnostic: bool,
) -> tuple[list[dict], dict]:
    snapshots, audit = replay_events(
        baseline,
        ledger,
        allow_diagnostic=diagnostic,
    )
    if audit["errors"]:
        raise PitUncertaintyScenarioError(
            f"{name} replay failed: {audit['error_rows'][:3]}"
        )
    return snapshots, audit


def build_scenarios(
    snapshot_path: Path,
    assumptions_path: Path,
    output_dir: Path,
    *,
    created_at: datetime | None = None,
) -> dict:
    snapshot = Path(snapshot_path)
    snapshot_manifest = verify_snapshot(snapshot)
    assumptions_file = Path(assumptions_path)
    assumptions = _read_csv(assumptions_file)
    blockers = _read_csv(snapshot / "blocker_backlog.csv")
    assumptions_by_key = _validate_assumptions(blockers, assumptions)
    ledger = _read_csv(snapshot / "integrated_event_ledger.csv")
    period = snapshot_manifest["source"]["period"]
    baseline_as_of = date.fromisoformat(period["baseline_as_of"])
    frozen_inputs = snapshot_manifest["source"]["frozen_inputs"]
    baseline = load_baseline_from_intervals(
        snapshot / frozen_inputs["baseline_intervals"],
        baseline_as_of,
    )
    baseline, correction_audit = apply_baseline_corrections(
        baseline,
        _read_csv(snapshot / frozen_inputs["baseline_corrections"]),
        as_of=baseline_as_of,
    )
    verified, assumed, baseline_additions = _scenario_rows(
        ledger, assumptions_by_key
    )
    scenario_inputs = {
        SCENARIO_CURRENT: (baseline, ledger, True),
        SCENARIO_VERIFIED: (baseline, verified, False),
        SCENARIO_CONTINUITY: (
            baseline | set(baseline_additions),
            [*verified, *assumed],
            True,
        ),
    }

    destination = Path(output_dir)
    if destination.exists():
        raise PitUncertaintyScenarioError(
            f"output directory already exists: {destination}"
        )
    temporary = destination.parent / (
        f".{destination.name}.tmp-{uuid.uuid4().hex}"
    )
    temporary.mkdir(parents=True)
    try:
        audits = {}
        baseline_rows = []
        snapshot_rows = []
        for name in SCENARIOS:
            scenario_baseline, scenario_ledger, diagnostic = scenario_inputs[
                name
            ]
            snapshots, audit = _replay_scenario(
                name,
                scenario_baseline,
                scenario_ledger,
                diagnostic=diagnostic,
            )
            audits[name] = audit
            baseline_rows.extend(
                {"scenario": name, "ticker": ticker}
                for ticker in sorted(scenario_baseline)
            )
            snapshot_rows.extend({
                "scenario": name,
                "effective_date": row["effective_date"],
                "before_count": row["before_count"],
                "after_count": row["after_count"],
                "added": "|".join(row["added"]),
                "removed": "|".join(row["removed"]),
            } for row in snapshots)

        exclusions = []
        for row in assumptions:
            for ticker in {
                row["ticker"].upper(),
                row["old_ticker"].upper(),
            }:
                exclusions.append({
                    "candidate_effective_date": row[
                        "candidate_effective_date"
                    ],
                    "ticker": ticker,
                    "center_date": row["assumed_index_effective_date"],
                    "observations_before": EXCLUSION_WINDOW_OBSERVATIONS,
                    "observations_after": EXCLUSION_WINDOW_OBSERVATIONS,
                    "reason": "UNRESOLVED_CONSTITUENT_CONTINUITY",
                })
        exclusions.sort(key=lambda row: (row["center_date"], row["ticker"]))

        _write_csv(
            temporary / "scenario_baselines.csv",
            baseline_rows,
            ["scenario", "ticker"],
        )
        _write_csv(
            temporary / "scenario_membership_changes.csv",
            snapshot_rows,
            [
                "scenario",
                "effective_date",
                "before_count",
                "after_count",
                "added",
                "removed",
            ],
        )
        _write_csv(
            temporary / "exclusion_windows.csv",
            exclusions,
            [
                "candidate_effective_date",
                "ticker",
                "center_date",
                "observations_before",
                "observations_after",
                "reason",
            ],
        )
        artifacts = {
            path.name: {
                "bytes": path.stat().st_size,
                "sha256": _sha256(path),
            }
            for path in sorted(temporary.iterdir())
        }
        body = {
            "format_version": FORMAT_VERSION,
            "created_at": (
                created_at or datetime.now(timezone.utc)
            ).astimezone(timezone.utc).isoformat(),
            "source_snapshot": {
                "snapshot_id": snapshot_manifest["snapshot_id"],
                "snapshot_sha256": snapshot_manifest["snapshot_sha256"],
            },
            "period": period,
            "assumptions_sha256": _sha256(assumptions_file),
            "scenario_order": list(SCENARIOS),
            "scenario_semantics": {
                SCENARIO_CURRENT: (
                    "verified events plus current diagnostic successions"
                ),
                SCENARIO_VERIFIED: "verified events only; uncertain successions omitted",
                SCENARIO_CONTINUITY: (
                    "all unresolved successions assumed continuous, including "
                    "the missing predecessor at baseline"
                ),
            },
            "audits": audits,
            "baseline_corrections": correction_audit,
            "exclusion_policy": {
                "observations_before": EXCLUSION_WINDOW_OBSERVATIONS,
                "observations_after": EXCLUSION_WINDOW_OBSERVATIONS,
                "application": "PER_TICKER_TRADING_OBSERVATIONS",
            },
            "policy": {
                "research_only": True,
                "promotion_allowed": False,
                "survivorship_safe": False,
            },
            "artifacts": artifacts,
        }
        manifest = {
            **body,
            "run_sha256": hashlib.sha256(_canonical_json(body)).hexdigest(),
        }
        (temporary / "manifest.json").write_text(
            json.dumps(
                manifest, ensure_ascii=False, indent=2, sort_keys=True
            ) + "\n",
            encoding="utf-8",
        )
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary.rename(destination)
        return manifest
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("snapshot", type=Path)
    parser.add_argument("assumptions", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    manifest = build_scenarios(
        args.snapshot,
        args.assumptions,
        args.output,
    )
    print(json.dumps(manifest["audits"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
