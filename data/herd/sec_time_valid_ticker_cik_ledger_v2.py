"""SEC as-filed ticker 관측과 원문 전환 근거로 보수적인 CIK 구간을 만든다."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
import zipfile
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = Path(__file__).with_name("sec_time_valid_ticker_cik_ledger_v2.json")
LEDGER = ROOT / "data/reports/sec_time_valid_ticker_cik_intervals_v2.csv"
REPORT = ROOT / "data/reports/sec_time_valid_ticker_cik_ledger_v2.json"
REQUIRED_COLUMNS = {
    "ACCESSION_NUMBER",
    "FILING_DATE",
    "DOCUMENT_TYPE",
    "ISSUERCIK",
    "ISSUERTRADINGSYMBOL",
}
PLACEHOLDERS = {"", "-", "--", "N/A", "NA", "NONE", "NOT APPLICABLE"}
SIMPLE_SYMBOL = re.compile(r"[A-Z0-9][A-Z0-9./-]{0,19}")


class SecTickerCikLedgerError(RuntimeError):
    pass


@dataclass(frozen=True)
class Anchor:
    cik: str
    reported_symbol: str
    canonical_symbol: str
    filing_date: date
    accession: str
    form: str
    source_quarter: str


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def root_path(relative: str) -> Path:
    path = (ROOT / relative).resolve()
    if not path.is_relative_to(ROOT):
        raise SecTickerCikLedgerError(f"path escapes repository: {relative}")
    return path


def canonical_symbol(symbol: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", symbol.upper())


def extract_reported_symbols(value: str) -> list[str]:
    """SEC issuerTradingSymbol의 명시적 단일·쉼표 병렬 표기만 분리한다."""
    text = " ".join(str(value or "").strip().upper().split())
    text = re.sub(r"^(?:NYSE|NASDAQ|AMEX|OTCQX|OTCQB)\s*:\s*", "", text)
    text = text.strip("()[] ")
    if text in PLACEHOLDERS:
        return []
    candidates = re.split(r"\s*(?:,|;|\bAND\b)\s*", text)
    symbols = []
    for candidate in candidates:
        symbol = candidate.strip("()[] ")
        if symbol in PLACEHOLDERS or not SIMPLE_SYMBOL.fullmatch(symbol):
            continue
        symbols.append(symbol)
    return sorted(set(symbols))


def _read_csv(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def _verify_locked_inputs(protocol_path: Path, protocol: dict) -> dict:
    checked = []
    for item in (
        protocol["official_sources"]
        + protocol["locked_universes"]
        + protocol["locked_identity_inputs"]
    ):
        relative = item.get("local_manifest") or item.get("local_path") or item["path"]
        path = root_path(relative)
        actual = sha256(path)
        if actual != item["sha256"]:
            raise SecTickerCikLedgerError(f"locked input changed: {relative}")
        checked.append({"path": relative, "sha256": actual})
    gate = protocol["finra_shadow_gate"]
    for key in ("source_protocol", "source_manifest"):
        path = root_path(gate[key])
        if sha256(path) != gate[f"{key}_sha256"]:
            raise SecTickerCikLedgerError(f"locked FINRA input changed: {gate[key]}")
    return {"verified_file_count": len(checked) + 2, "files": checked}


def _target_ciks(protocol: dict) -> set[str]:
    ciks: set[str] = set()
    for item in protocol["locked_universes"]:
        for row in _read_csv(root_path(item["path"])):
            value = row.get("cik", "")
            if value:
                ciks.add(value.zfill(10))
    for item in protocol["locked_identity_inputs"]:
        for row in _read_csv(root_path(item["path"])):
            value = row.get("cik", "")
            if value:
                ciks.add(value.zfill(10))
    return ciks


def _parse_filing_date(value: str) -> date:
    try:
        return datetime.strptime(value.strip(), "%d-%b-%Y").date()
    except ValueError as error:
        raise SecTickerCikLedgerError(f"invalid SEC filing date: {value}") from error


def collect_anchors(protocol: dict) -> tuple[list[Anchor], dict]:
    source = protocol["official_sources"][0]
    snapshot = root_path(source["local_manifest"]).parent
    manifest = json.loads((snapshot / "manifest.json").read_text(encoding="utf-8"))
    expected_hashes = {row["quarter"]: row["sha256"] for row in manifest["quarters"]}
    target_ciks = _target_ciks(protocol)
    start = date.fromisoformat(protocol["interval_policy"]["target_start"])
    end = date.fromisoformat(protocol["interval_policy"]["target_end"])
    allowed_forms = set(protocol["evidence_policy"]["allowed_forms"])
    anchors: list[Anchor] = []
    rejected = defaultdict(int)
    selected_quarters = 0

    for quarter, expected_hash in expected_hashes.items():
        year, number = int(quarter[:4]), int(quarter[-1])
        quarter_end = date(year, number * 3, 1)
        if quarter_end < start.replace(day=1) or date(year, (number - 1) * 3 + 1, 1) > end:
            continue
        raw_path = snapshot / "raw" / f"{year}q{number}_form345.zip"
        if sha256(raw_path) != expected_hash:
            raise SecTickerCikLedgerError(f"raw SEC ZIP hash mismatch: {quarter}")
        selected_quarters += 1
        with zipfile.ZipFile(raw_path) as archive, archive.open("SUBMISSION.tsv") as raw:
            reader = csv.DictReader(
                io.TextIOWrapper(raw, encoding="utf-8-sig"),
                delimiter="\t",
            )
            if not REQUIRED_COLUMNS.issubset(reader.fieldnames or []):
                raise SecTickerCikLedgerError(f"SEC schema drift: {quarter}")
            for row in reader:
                cik = row["ISSUERCIK"].strip().zfill(10)
                if cik not in target_ciks:
                    continue
                form = row["DOCUMENT_TYPE"].strip()
                if form not in allowed_forms:
                    rejected["form"] += 1
                    continue
                filing_date = _parse_filing_date(row["FILING_DATE"])
                if not start <= filing_date <= end:
                    rejected["outside_window"] += 1
                    continue
                symbols = extract_reported_symbols(row["ISSUERTRADINGSYMBOL"])
                if not symbols:
                    rejected["invalid_or_blank_symbol"] += 1
                    continue
                for symbol in symbols:
                    anchors.append(Anchor(
                        cik=cik,
                        reported_symbol=symbol,
                        canonical_symbol=canonical_symbol(symbol),
                        filing_date=filing_date,
                        accession=row["ACCESSION_NUMBER"].strip(),
                        form=form,
                        source_quarter=quarter,
                    ))
    anchors.sort(
        key=lambda item: (
            item.canonical_symbol,
            item.cik,
            item.filing_date,
            item.accession,
            item.reported_symbol,
        )
    )
    return anchors, {
        "target_cik_count": len(target_ciks),
        "selected_quarters": selected_quarters,
        "anchor_count": len(anchors),
        "anchored_cik_count": len({item.cik for item in anchors}),
        "anchored_canonical_symbol_count": len({
            item.canonical_symbol for item in anchors
        }),
        "rejected_rows": dict(sorted(rejected.items())),
    }


def _split_anchor_components(
    anchors: list[Anchor],
    max_gap_days: int,
) -> list[list[Anchor]]:
    components: list[list[Anchor]] = []
    current: list[Anchor] = []
    for anchor in anchors:
        if current and (anchor.filing_date - current[-1].filing_date).days > max_gap_days:
            components.append(current)
            current = []
        current.append(anchor)
    if current:
        components.append(current)
    return components


def _anchor_hash(anchors: list[Anchor]) -> str:
    payload = "\n".join(
        "|".join((
            item.cik,
            item.reported_symbol,
            item.filing_date.isoformat(),
            item.accession,
            item.form,
            item.source_quarter,
        ))
        for item in anchors
    )
    return hashlib.sha256(payload.encode()).hexdigest()


def _verified_transitions(protocol: dict) -> list[dict]:
    source = next(
        item for item in protocol["official_sources"]
        if item["role"] == "EXACT_TRANSITION_BOUNDARY"
    )
    rows = _read_csv(root_path(source["local_path"]))
    transitions = {}
    for row in rows:
        if row["identity_status"] != source["required_status"]:
            continue
        effective = row["resolved_effective_date"]
        if not effective:
            continue
        key = (
            row["candidate_cik"].zfill(10),
            canonical_symbol(row["old_ticker"]),
            canonical_symbol(row["new_ticker"]),
            effective,
        )
        transitions[key] = {
            "cik": key[0],
            "old_canonical_symbol": key[1],
            "new_canonical_symbol": key[2],
            "effective_date": key[3],
            "evidence_accessions": row["evidence_accessions"],
            "source": "SEC_EDGAR_PRIMARY_TRANSITION",
        }
    return sorted(
        transitions.values(),
        key=lambda row: (
            row["effective_date"],
            row["cik"],
            row["old_canonical_symbol"],
            row["new_canonical_symbol"],
        ),
    )


def _observation_intervals(anchors: list[Anchor], protocol: dict) -> list[dict]:
    policy = protocol["interval_policy"]
    grouped: dict[tuple[str, str], list[Anchor]] = defaultdict(list)
    for anchor in anchors:
        grouped[(anchor.canonical_symbol, anchor.cik)].append(anchor)
    intervals = []
    for (symbol, cik), items in sorted(grouped.items()):
        unique = {
            (item.filing_date, item.accession, item.reported_symbol): item
            for item in items
        }
        ordered = sorted(
            unique.values(),
            key=lambda item: (item.filing_date, item.accession, item.reported_symbol),
        )
        for component in _split_anchor_components(
            ordered, policy["max_gap_between_same_cik_symbol_anchors_days"]
        ):
            if len(component) < policy["minimum_anchor_count_per_interval"]:
                continue
            intervals.append({
                "canonical_symbol": symbol,
                "reported_symbols": "|".join(sorted({
                    item.reported_symbol for item in component
                })),
                "cik": cik,
                "valid_from": component[0].filing_date.isoformat(),
                "valid_to": component[-1].filing_date.isoformat(),
                "anchor_count": len(component),
                "first_accession": component[0].accession,
                "last_accession": component[-1].accession,
                "source_quarters": "|".join(sorted({
                    item.source_quarter for item in component
                })),
                "anchor_sha256": _anchor_hash(component),
                "boundary_sources": "SEC_FORM345_AS_FILED_OBSERVATION_SPAN",
                "status": "CANDIDATE",
            })
    return intervals


def _apply_transition_boundaries(intervals: list[dict], transitions: list[dict]) -> int:
    changes = 0
    for transition in transitions:
        if transition["old_canonical_symbol"] == transition["new_canonical_symbol"]:
            continue
        effective = date.fromisoformat(transition["effective_date"])
        old_candidates = [
            row for row in intervals
            if row["cik"] == transition["cik"]
            and row["canonical_symbol"] == transition["old_canonical_symbol"]
            and date.fromisoformat(row["valid_from"]) <= effective
        ]
        new_candidates = [
            row for row in intervals
            if row["cik"] == transition["cik"]
            and row["canonical_symbol"] == transition["new_canonical_symbol"]
            and date.fromisoformat(row["valid_to"]) >= effective
        ]
        if not old_candidates or not new_candidates:
            continue
        old = max(old_candidates, key=lambda row: row["valid_to"])
        new = min(new_candidates, key=lambda row: row["valid_from"])
        old_end = (effective - timedelta(days=1)).isoformat()
        if old["valid_to"] < old_end:
            old["valid_to"] = old_end
            changes += 1
        if new["valid_from"] > effective.isoformat():
            new["valid_from"] = effective.isoformat()
            changes += 1
        marker = (
            f"SEC_EDGAR_PRIMARY_TRANSITION:{transition['effective_date']}:"
            f"{transition['old_canonical_symbol']}->{transition['new_canonical_symbol']}"
        )
        old["boundary_sources"] += f"|{marker}"
        new["boundary_sources"] += f"|{marker}"
    return changes


def _locked_identity_intervals(protocol: dict) -> list[dict]:
    policy = protocol["interval_policy"]
    start, end = policy["target_start"], policy["target_end"]
    result = []
    for item in protocol["locked_identity_inputs"]:
        for row in _read_csv(root_path(item["path"])):
            if "status" in row:
                if not row["status"].startswith(("VERIFIED_", "OUTSIDE_CURRENT_")):
                    continue
                source = row["status"]
            else:
                if row.get("verification_status") != "VERIFIED":
                    continue
                source = "VERIFIED_TICKER_ALIAS_LEDGER"
            valid_from = max(start, row["valid_from"])
            valid_to = min(end, row.get("valid_to") or end)
            if valid_from > valid_to:
                continue
            result.append({
                "canonical_symbol": canonical_symbol(row["ticker"]),
                "reported_symbols": row["ticker"].upper(),
                "cik": row["cik"].zfill(10),
                "valid_from": valid_from,
                "valid_to": valid_to,
                "anchor_count": 0,
                "first_accession": "",
                "last_accession": "",
                "source_quarters": "",
                "anchor_sha256": "",
                "boundary_sources": source,
                "status": "CANDIDATE",
            })
    return result


def _overlaps(left: dict, right: dict) -> bool:
    return left["valid_from"] <= right["valid_to"] and right["valid_from"] <= left["valid_to"]


def _mark_conflicts(intervals: list[dict]) -> int:
    by_symbol: dict[str, list[dict]] = defaultdict(list)
    for row in intervals:
        by_symbol[row["canonical_symbol"]].append(row)
    conflict_ids: set[int] = set()
    for rows in by_symbol.values():
        for index, left in enumerate(rows):
            for right in rows[index + 1:]:
                if left["cik"] != right["cik"] and _overlaps(left, right):
                    conflict_ids.update((id(left), id(right)))
    for row in intervals:
        row["status"] = (
            "CONFLICT_EXCLUDED" if id(row) in conflict_ids else "TIME_VALID_CIK_VERIFIED"
        )
    return len(conflict_ids)


def _write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        raise SecTickerCikLedgerError(f"refusing to write empty ledger: {path}")
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def generate(
    protocol_path: Path = PROTOCOL,
    ledger_path: Path = LEDGER,
    report_path: Path = REPORT,
) -> dict:
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    if protocol["status"] != "LOCKED_BEFORE_INTERVAL_GENERATION":
        raise SecTickerCikLedgerError("protocol is not locked")
    integrity = _verify_locked_inputs(protocol_path, protocol)
    anchors, anchor_audit = collect_anchors(protocol)
    intervals = _observation_intervals(anchors, protocol)
    transitions = _verified_transitions(protocol)
    boundary_extensions = _apply_transition_boundaries(intervals, transitions)
    intervals.extend(_locked_identity_intervals(protocol))
    intervals.sort(
        key=lambda row: (
            row["canonical_symbol"],
            row["valid_from"],
            row["valid_to"],
            row["cik"],
            row["boundary_sources"],
        )
    )
    conflict_count = _mark_conflicts(intervals)
    _write_csv(ledger_path, intervals)
    verified = [
        row for row in intervals if row["status"] == "TIME_VALID_CIK_VERIFIED"
    ]
    report = {
        "report_version": "SEC_TIME_VALID_TICKER_CIK_LEDGER_V2",
        "status": "TIME_VALID_INTERVAL_LEDGER_BUILT",
        "protocol_sha256": sha256(protocol_path),
        "integrity": integrity,
        "source_semantics": (
            "SEC_FLATTENED_AS_FILED_FORM345_OBSERVATION_WITH_PRIMARY_EDGAR_TRANSITIONS"
        ),
        "source_is_not_full_filing_substitute": True,
        "anchor_audit": anchor_audit,
        "verified_primary_transition_count": len(transitions),
        "transition_boundary_extensions": boundary_extensions,
        "candidate_interval_count": len(intervals),
        "verified_interval_count": len(verified),
        "conflict_excluded_interval_count": conflict_count,
        "verified_canonical_symbol_count": len({
            row["canonical_symbol"] for row in verified
        }),
        "verified_cik_count": len({row["cik"] for row in verified}),
        "ledger_path": ledger_path.relative_to(ROOT).as_posix(),
        "ledger_sha256": sha256(ledger_path),
        "ledger_consumption_rule": "USE_TIME_VALID_CIK_VERIFIED_ROWS_ONLY",
        "current_ticker_backfill_performed": False,
        "price_outcomes_opened": False,
        "direction_hypothesis_preregistered": False,
        "herd_formula_change_allowed": False,
        "blind_holdout_access": False,
        "operational_action_authority": False,
        "operational_action_ratio": 0.0,
        "finra_authority": "PROSPECTIVE_SHADOW_OBSERVATION_ONLY",
        "next_priority": "RECALCULATE_FINRA_TIME_VALID_CIK_COVERAGE_WITH_LEDGER_V2",
    }
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, default=PROTOCOL)
    parser.add_argument("--ledger", type=Path, default=LEDGER)
    parser.add_argument("--report", type=Path, default=REPORT)
    args = parser.parse_args()
    print(json.dumps(
        generate(args.protocol, args.ledger, args.report),
        ensure_ascii=False,
        indent=2,
    ))


if __name__ == "__main__":
    main()
