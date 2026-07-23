"""해시 고정된 표적 SEC cover corpus를 검증하고 추적 산출물로 공개한다."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = Path(__file__).with_name("sec_targeted_cover_ticker_cik_v1.json")
SNAPSHOT = (
    ROOT
    / "data/reference/sec/sec-targeted-cover-v1-20210601-20260630-20260723"
)
ANCHORS = ROOT / "data/reports/sec_targeted_cover_anchors_v1.csv"
REPORT = ROOT / "data/reports/sec_targeted_cover_corpus_v1.json"


class SecTargetedCoverCorpusError(RuntimeError):
    pass


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_csv(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def _allowed_targets(protocol: dict) -> dict[tuple[str, str], set[str]]:
    allowed = {}
    for target in protocol["targets"]:
        symbols = set(target["accepted_canonical_symbols"])
        for cik in target["ciks"]:
            allowed[(target["entity"], cik["cik"])] = symbols
    return allowed


def _verify_artifacts(snapshot: Path, manifest: dict) -> dict:
    missing = []
    bad_hash = []
    bad_size = []
    for artifact in manifest["artifacts"]:
        path = (snapshot / artifact["path"]).resolve()
        if not path.is_relative_to(snapshot.resolve()):
            raise SecTargetedCoverCorpusError(
                f"artifact escapes snapshot: {artifact['path']}"
            )
        if not path.is_file():
            missing.append(artifact["path"])
            continue
        if path.stat().st_size != artifact["bytes"]:
            bad_size.append(artifact["path"])
        if sha256(path) != artifact["sha256"]:
            bad_hash.append(artifact["path"])
    return {
        "artifact_count": len(manifest["artifacts"]),
        "missing_artifacts": missing,
        "bad_size_artifacts": bad_size,
        "bad_hash_artifacts": bad_hash,
        "all_artifacts_verified": not missing and not bad_size and not bad_hash,
    }


def _validate_rows(
    protocol: dict,
    manifest: dict,
    filing_rows: list[dict],
    anchor_rows: list[dict],
) -> dict:
    allowed = _allowed_targets(protocol)
    eligible_forms = set(protocol["eligible_forms"])
    start = protocol["period"]["start"]
    end = protocol["period"]["end"]
    filing_by_accession = {
        (row["cik"], row["accession_number"]): row for row in filing_rows
    }
    errors = []
    accessions_by_group: dict[tuple[str, str], set[str]] = defaultdict(set)
    dates_by_group: dict[tuple[str, str], list[str]] = defaultdict(list)

    for row in anchor_rows:
        key = (row["entity"], row["cik"])
        filing = filing_by_accession.get((row["cik"], row["accession_number"]))
        if key not in allowed:
            errors.append(f"unknown target: {key}")
            continue
        if row["canonical_symbol"] not in allowed[key]:
            errors.append(
                f"symbol outside locked allowlist: {key}:{row['canonical_symbol']}"
            )
        if row["form"] not in eligible_forms:
            errors.append(f"ineligible form: {row['form']}")
        if not start <= row["filing_date"] <= end:
            errors.append(f"filing outside locked period: {row['filing_date']}")
        if filing is None:
            errors.append(
                f"anchor missing filing catalog row: {row['accession_number']}"
            )
        elif (
            filing["source_sha256"] != row["source_sha256"]
            or filing["accepted_at"] != row["accepted_at"]
            or filing["form"] != row["form"]
        ):
            errors.append(
                f"anchor/filing metadata mismatch: {row['accession_number']}"
            )
        group = (row["canonical_symbol"], row["cik"])
        accessions_by_group[group].add(row["accession_number"])
        dates_by_group[group].append(row["filing_date"])

    if len(filing_rows) != manifest["filing_count"]:
        errors.append("filing catalog count mismatch")
    if len(anchor_rows) != manifest["anchor_count"]:
        errors.append("anchor count mismatch")
    accepted_filings = sum(
        row["evidence_status"] == "TAGGED_TARGET_SYMBOL_VERIFIED"
        for row in filing_rows
    )
    if accepted_filings != manifest["filings_with_accepted_tagged_symbols"]:
        errors.append("accepted filing count mismatch")

    spans = []
    for (symbol, cik), dates in sorted(dates_by_group.items()):
        spans.append({
            "canonical_symbol": symbol,
            "cik": cik,
            "distinct_accessions": len(accessions_by_group[(symbol, cik)]),
            "first_anchor_date": min(dates),
            "last_anchor_date": max(dates),
        })
    return {
        "errors": errors,
        "all_rows_verified": not errors,
        "filing_count": len(filing_rows),
        "accepted_tagged_filing_count": accepted_filings,
        "anchor_count": len(anchor_rows),
        "entity_count": len({row["entity"] for row in anchor_rows}),
        "cik_count": len({row["cik"] for row in anchor_rows}),
        "canonical_symbols": sorted({
            row["canonical_symbol"] for row in anchor_rows
        }),
        "anchor_spans": spans,
    }


def verify_and_publish(
    protocol_path: Path = PROTOCOL,
    snapshot: Path = SNAPSHOT,
    anchors_path: Path = ANCHORS,
    report_path: Path = REPORT,
) -> dict:
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    if protocol["status"] != "LOCKED_BEFORE_TARGETED_COLLECTION":
        raise SecTargetedCoverCorpusError("targeted protocol is not locked")
    manifest_path = snapshot / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest["format_version"] != "SEC_TARGETED_COVER_CORPUS_V1":
        raise SecTargetedCoverCorpusError("unexpected snapshot format")
    if manifest["protocol_sha256"] != sha256(protocol_path):
        raise SecTargetedCoverCorpusError("snapshot protocol lineage mismatch")

    integrity = _verify_artifacts(snapshot, manifest)
    if not integrity["all_artifacts_verified"]:
        raise SecTargetedCoverCorpusError("snapshot artifact verification failed")
    raw_anchors = snapshot / "anchors.csv"
    raw_filings = snapshot / "filing_catalog.csv"
    if sha256(raw_anchors) != manifest["anchors_sha256"]:
        raise SecTargetedCoverCorpusError("snapshot anchor hash mismatch")
    if sha256(raw_filings) != manifest["filing_catalog_sha256"]:
        raise SecTargetedCoverCorpusError("snapshot filing catalog hash mismatch")

    row_audit = _validate_rows(
        protocol,
        manifest,
        _read_csv(raw_filings),
        _read_csv(raw_anchors),
    )
    if not row_audit["all_rows_verified"]:
        raise SecTargetedCoverCorpusError(
            f"snapshot row verification failed: {row_audit['errors'][:3]}"
        )

    anchors_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(raw_anchors, anchors_path)
    report = {
        "report_version": "SEC_TARGETED_COVER_CORPUS_V1",
        "status": "HASH_LOCKED_TAGGED_COVER_ANCHORS_READY",
        "research_tier": protocol["research_tier"],
        "protocol_path": protocol_path.relative_to(ROOT).as_posix(),
        "protocol_sha256": sha256(protocol_path),
        "snapshot_id": manifest["snapshot_id"],
        "snapshot_path": snapshot.relative_to(ROOT).as_posix(),
        "snapshot_manifest_sha256": sha256(manifest_path),
        "integrity": integrity,
        **{key: value for key, value in row_audit.items() if key != "errors"},
        "anchors_path": anchors_path.relative_to(ROOT).as_posix(),
        "anchors_sha256": sha256(anchors_path),
        "evidence_semantics": "SEC_PRIMARY_COVER_DEI_TRADING_SYMBOL_AS_FILED",
        "plain_text_regex_used_as_evidence": False,
        "current_submissions_ticker_array_used_as_evidence": False,
        "current_ticker_backfill_performed": False,
        "price_outcomes_opened": False,
        "direction_hypothesis_preregistered": False,
        "herd_formula_change_allowed": False,
        "blind_holdout_access": False,
        "operational_action_authority": False,
        "operational_action_ratio": 0.0,
        "next_priority": (
            "BUILD_TIME_VALID_TICKER_CIK_LEDGER_V3_WITHOUT_EXTRAPOLATION"
        ),
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, default=PROTOCOL)
    parser.add_argument("--snapshot", type=Path, default=SNAPSHOT)
    parser.add_argument("--anchors", type=Path, default=ANCHORS)
    parser.add_argument("--report", type=Path, default=REPORT)
    args = parser.parse_args()
    result = verify_and_publish(
        args.protocol,
        args.snapshot,
        args.anchors,
        args.report,
    )
    print(json.dumps({
        "status": result["status"],
        "filing_count": result["filing_count"],
        "anchor_count": result["anchor_count"],
        "canonical_symbols": result["canonical_symbols"],
        "next_priority": result["next_priority"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
