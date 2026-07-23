"""25개 식별자 공백 기업의 SEC 표지 원문을 중단·재개 가능하게 수집한다."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import shutil
import time
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import requests
from lxml import html

from herd.sec_master_index import resolve_user_agent


ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = Path(__file__).with_suffix(".json")
OUTPUT_ROOT = ROOT / "data/reference/sec"
REPORT = ROOT / "data/reports/sec_targeted_cover_corpus_v2.json"
ANCHORS = ROOT / "data/reports/sec_targeted_cover_anchors_v2.csv"
CATALOG = ROOT / "data/reports/sec_targeted_cover_filing_catalog_v2.csv"
ACCESSION = re.compile(r"^\d{10}-\d{2}-\d{6}$")
SYMBOL = re.compile(r"^[A-Z0-9][A-Z0-9./-]{0,19}$")


class SecTargetedCoverV2Error(RuntimeError):
    pass


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _rooted(relative: str) -> Path:
    path = (ROOT / relative).resolve()
    if not path.is_relative_to(ROOT.resolve()):
        raise SecTargetedCoverV2Error(f"path escapes repository: {relative}")
    return path


def _read_csv(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def _write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pending = path.with_suffix(path.suffix + ".new")
    with pending.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=fieldnames,
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)
    pending.replace(path)


def _atomic_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pending = path.with_suffix(path.suffix + ".new")
    pending.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    pending.replace(path)


def _verify_protocol(protocol: dict) -> tuple[dict, list[dict]]:
    if protocol["status"] != "LOCKED_BEFORE_PRIMARY_SOURCE_COLLECTION":
        raise SecTargetedCoverV2Error("V2 cover protocol is not locked")
    for locked in protocol["locked_inputs"]:
        if sha256(_rooted(locked["path"])) != locked["sha256"]:
            raise SecTargetedCoverV2Error(
                f"locked input changed: {locked['path']}"
            )
    queue_protocol = json.loads(_rooted(next(
        row["path"] for row in protocol["locked_inputs"]
        if row["role"] == "QUEUE_PROTOCOL"
    )).read_text(encoding="utf-8"))
    queue = _read_csv(_rooted(next(
        row["path"] for row in protocol["locked_inputs"]
        if row["role"] == "TARGET_QUEUE"
    )))
    if len(queue) != queue_protocol["selection"]["target_entity_count"]:
        raise SecTargetedCoverV2Error("target queue count mismatch")
    return queue_protocol, queue


def _target_by_cik(queue: list[dict]) -> dict[str, dict]:
    targets: dict[str, dict] = {}
    for row in queue:
        for cik in row["collection_ciks"].split("|"):
            if cik in targets:
                raise SecTargetedCoverV2Error(
                    f"collection CIK assigned twice: {cik}"
                )
            targets[cik] = {
                "entity": row["company_name"],
                "reference_ticker": row["reference_ticker"],
                "reference_cik": row["reference_cik"],
                "cik": cik,
                "accepted_symbols": row["accepted_symbols"].split("|"),
                "classification": row["classification"],
            }
    return targets


def submission_rows(payload: dict) -> list[dict]:
    recent = payload.get("filings", {}).get("recent", payload)
    required = (
        "accessionNumber",
        "filingDate",
        "acceptanceDateTime",
        "form",
        "primaryDocument",
    )
    count = len(recent.get("accessionNumber", []))
    if any(len(recent.get(field, [])) != count for field in required):
        raise SecTargetedCoverV2Error("incomplete SEC submissions columns")
    return [
        {
            "accession_number": recent["accessionNumber"][index],
            "filing_date": recent["filingDate"][index],
            "accepted_at": recent["acceptanceDateTime"][index],
            "form": recent["form"][index],
            "primary_document": recent["primaryDocument"][index],
        }
        for index in range(count)
    ]


def extract_tagged_trading_symbols(content: bytes) -> list[str]:
    symbols = set()
    try:
        document = html.fromstring(content)
    except (ValueError, html.etree.ParserError):
        return []
    elements = document.xpath(
        "//*[@name] | "
        "//*[translate(local-name(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', "
        "'abcdefghijklmnopqrstuvwxyz')='tradingsymbol']"
    )
    for element in elements:
        name = str(element.get("name", ""))
        if name and not name.lower().endswith("tradingsymbol"):
            continue
        raw = " ".join(element.text_content().split()).upper()
        for value in re.split(r"[,;]", raw):
            candidate = value.strip()
            if SYMBOL.fullmatch(candidate):
                symbols.add(candidate)
    return sorted(symbols)


class SecClient:
    def __init__(self, config: dict, user_agent: str):
        if "@" not in user_agent:
            raise SecTargetedCoverV2Error(
                "descriptive SEC user agent is required"
            )
        self.config = config
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": user_agent,
            "Accept-Encoding": "gzip, deflate",
        })
        self.next_request_at = 0.0

    def get(self, url: str) -> bytes:
        for attempt in range(self.config["maximum_attempts"]):
            wait = self.next_request_at - time.monotonic()
            if wait > 0:
                time.sleep(wait)
            self.next_request_at = (
                time.monotonic() + 1.0 / self.config["requests_per_second"]
            )
            response = self.session.get(
                url,
                timeout=self.config["request_timeout_seconds"],
            )
            if response.status_code < 400:
                return response.content
            if (
                response.status_code not in self.config["retry_statuses"]
                or attempt + 1 == self.config["maximum_attempts"]
            ):
                response.raise_for_status()
            retry_after = response.headers.get("Retry-After")
            delay = (
                float(retry_after)
                if retry_after and retry_after.isdigit()
                else min(
                    self.config["initial_backoff_seconds"] * (2 ** attempt),
                    self.config["maximum_backoff_seconds"],
                )
            )
            time.sleep(delay)
        raise SecTargetedCoverV2Error("unreachable SEC retry state")


def _source_artifact(
    path: Path,
    url: str,
    kind: str,
    *,
    snapshot_root: Path,
    **metadata: Any,
) -> dict:
    return {
        "path": path.relative_to(snapshot_root).as_posix(),
        "sha256": sha256(path),
        "bytes": path.stat().st_size,
        "url": url,
        "kind": kind,
        **metadata,
    }


def _discover_catalog(
    protocol: dict,
    queue_protocol: dict,
    targets: dict[str, dict],
    partial: Path,
    client: SecClient,
) -> tuple[list[dict], list[dict]]:
    submissions = partial / "submissions"
    submissions.mkdir(parents=True, exist_ok=True)
    artifacts = []
    rows = []
    forms = set(queue_protocol["collection_policy"]["eligible_forms"])
    start = protocol["period"]["start"]
    end = protocol["period"]["end"]
    urls = protocol["official_sources"]

    for position, (cik, target) in enumerate(sorted(targets.items()), start=1):
        base_url = urls["submissions"].format(cik=cik)
        base_path = submissions / f"CIK{cik}.json"
        if not base_path.exists():
            base_path.write_bytes(client.get(base_url))
        base = json.loads(base_path.read_text(encoding="utf-8"))
        payloads = [(base_path, base_url, base)]
        for item in base.get("filings", {}).get("files", []):
            if item.get("filingTo", "") < start or item.get("filingFrom", "") > end:
                continue
            history_url = urls["submission_history"].format(name=item["name"])
            history_path = submissions / f"CIK{cik}-{item['name']}"
            if not history_path.exists():
                history_path.write_bytes(client.get(history_url))
            payloads.append((
                history_path,
                history_url,
                json.loads(history_path.read_text(encoding="utf-8")),
            ))
        seen = set()
        for path, url, payload in payloads:
            artifacts.append(_source_artifact(
                path,
                url,
                "SUBMISSIONS",
                snapshot_root=partial,
                cik=cik,
            ))
            for filing in submission_rows(payload):
                accession = filing["accession_number"]
                if (
                    accession in seen
                    or filing["form"] not in forms
                    or not start <= filing["filing_date"] <= end
                    or not ACCESSION.fullmatch(accession)
                    or not filing["accepted_at"]
                    or not filing["primary_document"]
                ):
                    continue
                seen.add(accession)
                rows.append({
                    **target,
                    **filing,
                })
        print(
            f"discovered CIKs: {position}/{len(targets)} "
            f"(eligible filings: {len(rows)})",
            flush=True,
        )
    return sorted(
        rows,
        key=lambda row: (
            row["accepted_at"],
            row["cik"],
            row["accession_number"],
        ),
    ), artifacts


FILING_FIELDS = [
    "entity",
    "reference_ticker",
    "reference_cik",
    "cik",
    "classification",
    "accession_number",
    "form",
    "filing_date",
    "accepted_at",
    "primary_document",
    "source_url",
    "source_sha256",
    "source_bytes",
    "tagged_symbols",
    "accepted_symbols",
    "evidence_status",
]
ANCHOR_FIELDS = [
    "entity",
    "reference_ticker",
    "reference_cik",
    "cik",
    "classification",
    "reported_symbol",
    "canonical_symbol",
    "filing_date",
    "accepted_at",
    "accession_number",
    "form",
    "source_url",
    "source_sha256",
]


def collect(
    protocol_path: Path = PROTOCOL,
    output_root: Path = OUTPUT_ROOT,
    env_file: Path = ROOT / ".env",
) -> Path:
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    queue_protocol, queue = _verify_protocol(protocol)
    targets = _target_by_cik(queue)
    snapshot_id = protocol["collection"]["snapshot_id"]
    final = output_root / snapshot_id
    if final.exists():
        return final
    partial = output_root / f".{snapshot_id}.partial"
    partial.mkdir(parents=True, exist_ok=True)
    client = SecClient(
        protocol["collection"],
        resolve_user_agent(env_file),
    )
    catalog_path = partial / "eligible_catalog.json"
    submission_artifacts_path = partial / "submission_artifacts.json"
    if catalog_path.exists() and submission_artifacts_path.exists():
        discovered = json.loads(catalog_path.read_text(encoding="utf-8"))
        submission_artifacts = json.loads(
            submission_artifacts_path.read_text(encoding="utf-8")
        )
    else:
        discovered, submission_artifacts = _discover_catalog(
            protocol,
            queue_protocol,
            targets,
            partial,
            client,
        )
        _atomic_json(catalog_path, discovered)
        _atomic_json(submission_artifacts_path, submission_artifacts)

    partial_catalog = partial / "filing_catalog.partial.csv"
    existing = _read_csv(partial_catalog) if partial_catalog.exists() else []
    completed = {row["accession_number"] for row in existing}
    filing_rows = list(existing)
    primary = partial / "primary"
    primary.mkdir(parents=True, exist_ok=True)
    failures: list[dict] = []
    urls = protocol["official_sources"]

    for position, filing in enumerate(discovered, start=1):
        if filing["accession_number"] in completed:
            continue
        compact = filing["accession_number"].replace("-", "")
        url = urls["primary_document"].format(
            cik=int(filing["cik"]),
            accession=compact,
            document=filing["primary_document"],
        )
        try:
            content = client.get(url)
            digest = sha256_bytes(content)
            path = primary / filing["cik"] / f"{digest}.html"
            path.parent.mkdir(parents=True, exist_ok=True)
            if not path.exists():
                path.write_bytes(content)
            tagged = extract_tagged_trading_symbols(content)
            accepted = sorted(
                set(tagged) & set(filing["accepted_symbols"])
            )
            filing_rows.append({
                key: value for key, value in {
                    **filing,
                    "source_url": url,
                    "source_sha256": digest,
                    "source_bytes": len(content),
                    "tagged_symbols": "|".join(tagged),
                    "accepted_symbols": "|".join(accepted),
                    "evidence_status": (
                        "TAGGED_TARGET_SYMBOL_VERIFIED"
                        if accepted
                        else "NO_ACCEPTED_TAGGED_TARGET_SYMBOL"
                    ),
                }.items()
                if key in FILING_FIELDS
            })
            completed.add(filing["accession_number"])
        except Exception as error:
            failures.append({
                "accession_number": filing["accession_number"],
                "error": type(error).__name__,
                "message": str(error)[:300],
            })
        if (
            position % protocol["collection"]["checkpoint_every_filings"] == 0
            or failures
        ):
            _write_csv(
                partial_catalog,
                sorted(filing_rows, key=lambda row: row["accepted_at"]),
                FILING_FIELDS,
            )
            _atomic_json(partial / "failures.json", failures)
        if position % 100 == 0:
            print(
                f"collected primary filings: {len(completed)}/{len(discovered)}",
                flush=True,
            )

    _write_csv(
        partial_catalog,
        sorted(filing_rows, key=lambda row: row["accepted_at"]),
        FILING_FIELDS,
    )
    _atomic_json(partial / "failures.json", failures)
    if failures or len(completed) != len(discovered):
        raise SecTargetedCoverV2Error(
            f"collection incomplete: {len(completed)}/{len(discovered)}, "
            f"failures={len(failures)}"
        )

    filing_rows.sort(key=lambda row: (
        row["accepted_at"],
        row["cik"],
        row["accession_number"],
    ))
    anchors = []
    for row in filing_rows:
        for symbol in filter(None, row["accepted_symbols"].split("|")):
            anchors.append({
                "entity": row["entity"],
                "reference_ticker": row["reference_ticker"],
                "reference_cik": row["reference_cik"],
                "cik": row["cik"],
                "classification": row["classification"],
                "reported_symbol": symbol,
                "canonical_symbol": symbol.replace(".", "").replace("-", ""),
                "filing_date": row["filing_date"],
                "accepted_at": row["accepted_at"],
                "accession_number": row["accession_number"],
                "form": row["form"],
                "source_url": row["source_url"],
                "source_sha256": row["source_sha256"],
            })
    anchors.sort(key=lambda row: (
        row["accepted_at"],
        row["cik"],
        row["accession_number"],
        row["reported_symbol"],
    ))
    _write_csv(partial / "filing_catalog.csv", filing_rows, FILING_FIELDS)
    _write_csv(partial / "anchors.csv", anchors, ANCHOR_FIELDS)

    artifacts = []
    for item in submission_artifacts:
        relative = Path(item["path"])
        artifact_path = partial / relative
        artifacts.append({
            **item,
            "sha256": sha256(artifact_path),
            "bytes": artifact_path.stat().st_size,
        })
    source_by_hash = {
        row["source_sha256"]: row for row in filing_rows
    }
    for path in sorted(primary.glob("*/*.html")):
        digest = path.stem
        source = source_by_hash[digest]
        artifacts.append(_source_artifact(
            path,
            source["source_url"],
            "PRIMARY_FILING",
            snapshot_root=partial,
            cik=source["cik"],
            accession_number=source["accession_number"],
        ))
    manifest = {
        "format_version": "SEC_TARGETED_COVER_CORPUS_V2",
        "snapshot_id": snapshot_id,
        "created_at_utc": datetime.now(UTC).isoformat(),
        "protocol_sha256": sha256(protocol_path),
        "target_entity_count": len(queue),
        "target_cik_count": len(targets),
        "filing_count": len(filing_rows),
        "filings_with_accepted_tagged_symbols": sum(
            row["evidence_status"] == "TAGGED_TARGET_SYMBOL_VERIFIED"
            for row in filing_rows
        ),
        "anchor_count": len(anchors),
        "artifact_count": len(artifacts),
        "filing_catalog_sha256": sha256(partial / "filing_catalog.csv"),
        "anchors_sha256": sha256(partial / "anchors.csv"),
        "failures": [],
        "artifacts": artifacts,
        "price_outcomes_opened": False,
        "direction_hypothesis_preregistered": False,
        "operational_action_ratio": 0.0,
    }
    _atomic_json(partial / "manifest.json", manifest)
    catalog_path.unlink(missing_ok=True)
    submission_artifacts_path.unlink(missing_ok=True)
    partial_catalog.unlink(missing_ok=True)
    (partial / "failures.json").unlink(missing_ok=True)
    output_root.mkdir(parents=True, exist_ok=True)
    partial.replace(final)
    return final


def verify_and_publish(
    protocol_path: Path = PROTOCOL,
    snapshot: Path | None = None,
    anchors_path: Path = ANCHORS,
    catalog_path: Path = CATALOG,
    report_path: Path = REPORT,
) -> dict:
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    _verify_protocol(protocol)
    snapshot = snapshot or (
        OUTPUT_ROOT / protocol["collection"]["snapshot_id"]
    )
    manifest_path = snapshot / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest["protocol_sha256"] != sha256(protocol_path):
        raise SecTargetedCoverV2Error("snapshot protocol lineage mismatch")
    bad_artifacts = []
    for artifact in manifest["artifacts"]:
        path = (snapshot / artifact["path"]).resolve()
        if (
            not path.is_relative_to(snapshot.resolve())
            or not path.is_file()
            or path.stat().st_size != artifact["bytes"]
            or sha256(path) != artifact["sha256"]
        ):
            bad_artifacts.append(artifact["path"])
    if bad_artifacts:
        raise SecTargetedCoverV2Error(
            f"snapshot artifact verification failed: {bad_artifacts[:3]}"
        )
    if manifest["failures"]:
        raise SecTargetedCoverV2Error("snapshot has unresolved failures")
    shutil.copyfile(snapshot / "anchors.csv", anchors_path)
    shutil.copyfile(snapshot / "filing_catalog.csv", catalog_path)
    if sha256(anchors_path) != manifest["anchors_sha256"]:
        raise SecTargetedCoverV2Error("published anchors hash mismatch")
    if sha256(catalog_path) != manifest["filing_catalog_sha256"]:
        raise SecTargetedCoverV2Error("published catalog hash mismatch")

    estimated_minimum = protocol["completion_gate"][
        "estimated_filing_count_minimum"
    ]
    report = {
        "report_version": "SEC_TARGETED_COVER_CORPUS_V2",
        "status": "HASH_LOCKED_ELIGIBLE_SOURCE_EXHAUSTED",
        "protocol_sha256": sha256(protocol_path),
        "snapshot_id": manifest["snapshot_id"],
        "snapshot_path": snapshot.relative_to(ROOT).as_posix(),
        "snapshot_manifest_sha256": sha256(manifest_path),
        "target_entity_count": manifest["target_entity_count"],
        "target_cik_count": manifest["target_cik_count"],
        "filing_count": manifest["filing_count"],
        "filings_with_accepted_tagged_symbols": (
            manifest["filings_with_accepted_tagged_symbols"]
        ),
        "anchor_count": manifest["anchor_count"],
        "artifact_count": manifest["artifact_count"],
        "estimated_minimum_reached": manifest["filing_count"] >= estimated_minimum,
        "volume_estimate_is_not_gate": True,
        "eligible_source_exhausted": True,
        "unresolved_failures": 0,
        "all_artifacts_verified": True,
        "anchors_path": anchors_path.relative_to(ROOT).as_posix(),
        "anchors_sha256": sha256(anchors_path),
        "filing_catalog_path": catalog_path.relative_to(ROOT).as_posix(),
        "filing_catalog_sha256": sha256(catalog_path),
        "plain_text_regex_used_as_evidence": False,
        "current_submissions_ticker_array_used_as_evidence": False,
        "price_outcomes_opened": False,
        "direction_hypothesis_preregistered": False,
        "herd_formula_change_allowed": False,
        "blind_holdout_access": False,
        "operational_action_ratio": 0.0,
        "next_priority": "BUILD_LIFECYCLE_AWARE_TIME_VALID_LEDGER_V5",
    }
    _atomic_json(report_path, report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, default=PROTOCOL)
    parser.add_argument("--output-root", type=Path, default=OUTPUT_ROOT)
    parser.add_argument("--env-file", type=Path, default=ROOT / ".env")
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    snapshot = (
        args.output_root
        / json.loads(args.protocol.read_text(encoding="utf-8"))[
            "collection"
        ]["snapshot_id"]
    )
    if not args.verify_only:
        snapshot = collect(args.protocol, args.output_root, args.env_file)
    print(json.dumps(
        verify_and_publish(args.protocol, snapshot),
        ensure_ascii=False,
        indent=2,
    ))


if __name__ == "__main__":
    main()
