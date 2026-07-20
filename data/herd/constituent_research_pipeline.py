"""S&P 500 PIT 검증 단계를 순서대로 실행하고 회귀를 차단한다."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
import uuid
from datetime import date, datetime, timezone
from pathlib import Path

from herd.constituent_blocker_backlog import build_blocker_backlog
from herd.corporate_continuity_reconciliation import (
    load_sec_corpus,
    load_spglobal_corpus,
    verify_and_reconcile,
)
from herd.daily_constituent_replay import (
    apply_baseline_corrections,
    load_baseline_from_intervals,
    replay_events,
)
from herd.identity_transition_reconciliation import (
    reconcile_identity_transitions,
)
from herd.integrated_event_ledger import build_integrated_ledger
from herd.official_candidate_reconciliation import reconcile_candidates
from herd.residual_event_classification import (
    RESOLVED_STATUSES,
    classify_residual_events,
)


class ConstituentResearchPipelineError(RuntimeError):
    pass


REQUIRED_INPUTS = {
    "candidate_events",
    "table_events",
    "prose_events",
    "suggestions",
    "semantic_events",
    "reviewed_date_corrections",
    "identity_evidence",
    "continuity_claims",
    "sp_continuity_corpus",
    "sec_continuity_corpus",
    "cik_events",
    "form25_candidates",
    "form25_classification",
    "merger_classification",
    "reconstruction_anomalies",
    "baseline_intervals",
    "baseline_corrections",
}
VERIFIED_LEDGER_STATUSES = {
    "VERIFIED_OFFICIAL_EVENT",
    "OFFICIAL_EVENT_WITH_SEC_ACTION_EVIDENCE",
    "VERIFIED_IDENTITY_CHANGE",
    "VERIFIED_CORPORATE_CONTINUITY",
}


def read_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(
    path: Path,
    rows: list[dict],
    *,
    empty_fields: tuple[str, ...] | None = None,
) -> None:
    if not rows and empty_fields is None:
        raise ConstituentResearchPipelineError(f"empty pipeline output: {path.name}")
    fields: list[str] = list(empty_fields or ())
    for row in rows:
        for field in row:
            if field not in fields:
                fields.append(field)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def hash_path(path: Path) -> str:
    digest = hashlib.sha256()
    files = [path] if path.is_file() else sorted(
        item for item in path.rglob("*") if item.is_file()
    )
    if not files:
        raise ConstituentResearchPipelineError(f"input has no files: {path}")
    for item in files:
        relative = item.name if path.is_file() else item.relative_to(path).as_posix()
        digest.update(relative.encode())
        digest.update(b"\0")
        digest.update(hashlib.sha256(item.read_bytes()).digest())
    return digest.hexdigest()


def normalize_candidates(
    rows: list[dict],
    *,
    start: date,
    end: date,
) -> list[dict]:
    candidates = []
    for row in rows:
        effective = row.get("effective_date") or row.get("candidate_effective_date")
        action = row.get("action") or row.get("event")
        ticker = row.get("ticker", "").upper()
        if not effective or action not in {"ADD", "REMOVE"} or not ticker:
            continue
        event_date = date.fromisoformat(effective)
        if start <= event_date <= end:
            candidates.append({
                "effective_date": effective,
                "action": action,
                "ticker": ticker,
            })
    keys = {
        (row["effective_date"], row["action"], row["ticker"])
        for row in candidates
    }
    if len(keys) != len(candidates):
        raise ConstituentResearchPipelineError("duplicate normalized candidate event")
    return candidates


def candidate_key(row: dict) -> tuple[str, str, str]:
    return (
        row["candidate_effective_date"],
        row["action"].upper(),
        row["ticker"].upper(),
    )


def regression_failures(
    *,
    reconciliation: list[dict],
    ledger_audit: dict,
    replay_audit: dict,
    previous_reconciliation: list[dict] | None = None,
    previous_replay_audit: dict | None = None,
) -> list[str]:
    failures = []
    if replay_audit["errors"]:
        failures.append(
            "replay errors: "
            f"{replay_audit['errors']} {replay_audit.get('error_rows', [])[:5]}"
        )
    if previous_reconciliation is not None:
        current = {candidate_key(row): row["status"] for row in reconciliation}
        regressed = sorted(
            candidate_key(row)
            for row in previous_reconciliation
            if row["status"] in RESOLVED_STATUSES
            and current.get(candidate_key(row)) not in RESOLVED_STATUSES
        )
        if regressed:
            failures.append(f"resolved candidates regressed: {regressed[:10]}")
    if previous_replay_audit is not None:
        previous_verified = previous_replay_audit["verified_events"]
        previous_blocked = previous_replay_audit["blocked_events"]
        if replay_audit["verified_events"] < previous_verified:
            failures.append(
                "verified events decreased: "
                f"{previous_verified}->{replay_audit['verified_events']}"
            )
        if replay_audit["blocked_events"] > previous_blocked:
            failures.append(
                "blocked events increased: "
                f"{previous_blocked}->{replay_audit['blocked_events']}"
            )
    if ledger_audit["verified_official_events"] != replay_audit["verified_events"]:
        failures.append("ledger and replay verified event counts differ")
    return failures


def resolve_paths(config_path: Path, config: dict) -> dict[str, Path]:
    root = config_path.parent
    resolved = {}
    missing = REQUIRED_INPUTS - config.get("inputs", {}).keys()
    if missing:
        raise ConstituentResearchPipelineError(
            f"pipeline config missing inputs: {sorted(missing)}"
        )
    for name, raw_path in config["inputs"].items():
        path = Path(raw_path)
        resolved[name] = path if path.is_absolute() else (root / path).resolve()
        if not resolved[name].exists():
            raise ConstituentResearchPipelineError(
                f"pipeline input does not exist: {name}={resolved[name]}"
            )
    return resolved


def run_pipeline(config_path: Path, output_dir: Path) -> dict:
    config_path = config_path.resolve()
    config = json.loads(config_path.read_text(encoding="utf-8"))
    inputs = resolve_paths(config_path, config)
    output_dir = output_dir.resolve()
    if output_dir.exists():
        raise ConstituentResearchPipelineError(
            f"output directory already exists: {output_dir}"
        )
    temp = output_dir.parent / f".{output_dir.name}.tmp-{uuid.uuid4().hex}"
    temp.mkdir(parents=True)
    try:
        period_start = date.fromisoformat(config["period"]["start"])
        period_end = date.fromisoformat(config["period"]["end"])
        baseline_as_of = date.fromisoformat(config["period"]["baseline_as_of"])
        candidates = normalize_candidates(
            read_csv(inputs["candidate_events"]),
            start=period_start,
            end=period_end,
        )
        official_rows, official_audit = reconcile_candidates(
            candidates,
            read_csv(inputs["table_events"]),
            read_csv(inputs["prose_events"]),
            read_csv(inputs["suggestions"]),
            read_csv(inputs["semantic_events"]),
            read_csv(inputs["reviewed_date_corrections"]),
        )
        identity_rows, identity_events, identity_audit = (
            reconcile_identity_transitions(
                official_rows,
                read_csv(inputs["identity_evidence"]),
            )
        )
        reconciliation, continuity_events, continuity_audit = verify_and_reconcile(
            identity_rows,
            read_csv(inputs["continuity_claims"]),
            load_spglobal_corpus(inputs["sp_continuity_corpus"]),
            load_sec_corpus(inputs["sec_continuity_corpus"]),
        )
        ledger, ledger_audit = build_integrated_ledger(
            reconciliation,
            read_csv(inputs["cik_events"]),
            read_csv(inputs["form25_candidates"]),
            read_csv(inputs["form25_classification"]),
            read_csv(inputs["merger_classification"]),
            identity_events,
            read_csv(inputs["reconstruction_anomalies"]),
            continuity_events,
        )
        baseline = load_baseline_from_intervals(
            inputs["baseline_intervals"], baseline_as_of
        )
        baseline, correction_audit = apply_baseline_corrections(
            baseline,
            read_csv(inputs["baseline_corrections"]),
            as_of=baseline_as_of,
        )
        snapshots, replay_audit = replay_events(
            baseline,
            ledger,
            allow_diagnostic=True,
        )
        replay_audit.update(correction_audit)
        if correction_audit.get("baseline_corrections"):
            replay_audit["diagnostic_only"] = True
            replay_audit["replay_complete"] = False
        residual, residual_audit = classify_residual_events(
            reconciliation,
            read_csv(inputs["identity_evidence"]),
        )
        backlog, backlog_audit = build_blocker_backlog(
            ledger,
            residual,
            identity_evidence=read_csv(inputs["identity_evidence"]),
        )

        previous_reconciliation = (
            read_csv(inputs["previous_reconciliation"])
            if "previous_reconciliation" in inputs else None
        )
        previous_replay_audit = None
        if "previous_replay" in inputs:
            previous_replay_audit = json.loads(
                inputs["previous_replay"].read_text(encoding="utf-8")
            )["audit"]
        failures = regression_failures(
            reconciliation=reconciliation,
            ledger_audit=ledger_audit,
            replay_audit=replay_audit,
            previous_reconciliation=previous_reconciliation,
            previous_replay_audit=previous_replay_audit,
        )
        if failures:
            raise ConstituentResearchPipelineError("; ".join(failures))

        outputs = {
            "official_reconciliation.csv": official_rows,
            "identity_reconciliation.csv": identity_rows,
            "identity_transitions.csv": identity_events,
            "reconciliation.csv": reconciliation,
            "corporate_continuity.csv": continuity_events,
            "integrated_event_ledger.csv": ledger,
            "residual_classification.csv": residual,
            "blocker_backlog.csv": backlog,
        }
        empty_output_fields = {
            "residual_classification.csv": (
                "candidate_effective_date",
                "action",
                "ticker",
                "reconciliation_status",
                "residual_category",
                "required_evidence",
                "promotion_allowed",
                "review_status",
            ),
            "blocker_backlog.csv": (
                "candidate_effective_date",
                "action",
                "ticker",
                "event_status",
                "residual_category",
                "workstream",
                "priority",
                "paired_opposite_candidates",
                "required_evidence",
                "promotion_allowed",
            ),
        }
        for name, rows in outputs.items():
            write_csv(
                temp / name,
                rows,
                empty_fields=empty_output_fields.get(name),
            )
        (temp / "replay.json").write_text(
            json.dumps(
                {"audit": replay_audit, "snapshots": snapshots},
                ensure_ascii=False,
                indent=2,
            ) + "\n",
            encoding="utf-8",
        )
        audits = {
            "official": official_audit,
            "identity": identity_audit,
            "continuity": continuity_audit,
            "ledger": ledger_audit,
            "replay": replay_audit,
            "residual": residual_audit,
            "backlog": backlog_audit,
        }
        manifest = {
            "format_version": "herd-constituent-research-pipeline-v1",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "config_sha256": hash_path(config_path),
            "period": config["period"],
            "inputs": {
                name: {
                    "path": str(path),
                    "sha256": hash_path(path),
                }
                for name, path in sorted(inputs.items())
            },
            "audits": audits,
            "gates": {
                "regression_failures": [],
                "replay_errors": replay_audit["errors"],
                "blocked_events": replay_audit["blocked_events"],
                "replay_complete": replay_audit["replay_complete"],
                "survivorship_safe": (
                    replay_audit["replay_complete"]
                    and not replay_audit["diagnostic_only"]
                ),
            },
        }
        (temp / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        manifest["outputs"] = {
            item.name: hash_path(item)
            for item in sorted(temp.iterdir())
            if item.name != "manifest.json"
        }
        (temp / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        output_dir.parent.mkdir(parents=True, exist_ok=True)
        temp.rename(output_dir)
        return manifest
    except Exception:
        shutil.rmtree(temp, ignore_errors=True)
        raise


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config", type=Path)
    parser.add_argument("output_dir", type=Path)
    args = parser.parse_args()
    manifest = run_pipeline(args.config, args.output_dir)
    print(json.dumps(manifest["gates"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
