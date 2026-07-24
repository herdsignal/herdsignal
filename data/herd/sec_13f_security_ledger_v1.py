"""13F의 CUSIP/FIGI를 연구 종목의 SEC CIK와 시점 안전하게 연결한다."""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import io
import json
import re
import unicodedata
import zipfile
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = ROOT / "data/herd/sec_13f_crowding_protocol_v1.json"
BULK_SNAPSHOT = (
    ROOT / "data/reference/sec/sec-13f-bulk-2013q2-2026m05-v1"
)
UNIVERSE = ROOT / "data/reports/independent_universe_v1.csv"
IDENTITIES = ROOT / "data/reports/sec_13f_target_identities_v1.csv"
INTERVALS = ROOT / "data/reports/sec_13f_security_intervals_v1.csv"
REVIEW = ROOT / "data/reports/sec_13f_security_mapping_review_v1.csv"
REPORT = ROOT / "data/reports/sec_13f_security_ledger_v1.json"
BULK_REPORT = ROOT / "data/reports/sec_13f_bulk_v1.json"

_CORPORATE_TOKEN_EQUIVALENTS = {
    "COMPANY": "CO",
    "COMPANIES": "CO",
    "COS": "CO",
    "CORPORATION": "CORP",
    "INCORPORATED": "INC",
    "INTERNATIONAL": "INTL",
    "LIMITED": "LTD",
    "HOLDING": "HLDG",
    "HOLDINGS": "HLDG",
    "MATLS": "MATERIALS",
    "GEN": "GENERAL",
    "RLTY": "REALTY",
    "INVT": "INVESTMENT",
    "LABS": "LABORATORIES",
    "TRANSPORTATION": "TRANSPORT",
    "TR": "TRUST",
    "PWR": "POWER",
    "SYS": "SYSTEMS",
}
_NON_IDENTITY_TOKENS = {
    "CO",
    "CORP",
    "INC",
    "IN",
    "LTD",
    "HLDG",
    "PLC",
    "DE",
    "DEL",
    "DELAWARE",
    "NEW",
}
_CLASS_RULES = {
    "0001652044": {
        "A": "GOOGL",
        "C": "GOOG",
    }
}
_CUSIP_CLASS_RULES = {
    "0001652044": {
        "02079K305": "GOOGL",
        "02079K107": "GOOG",
    }
}
_DATE_FORMATS = ("%d-%b-%Y", "%Y-%m-%d")
_SCAN_RULE_VERSION = "SEC_13F_NAME_MATCH_SCAN_V4"


class Sec13fSecurityLedgerError(RuntimeError):
    """입력·식별자·클래스 원장이 fail-closed 조건을 위반했을 때 발생한다."""


@dataclass(frozen=True)
class Target:
    ticker: str
    cik: str
    company: str


@dataclass
class SecurityObservation:
    cik: str
    ticker: str
    cusip: str
    figi: str
    issuer_name: str
    title_of_class: str
    first_period: date
    last_period: date
    periods: set[date]
    accessions: set[str]
    period_rows: dict[date, int]
    period_accessions: dict[date, set[str]]
    rows: int = 0
    exact_name_rows: int = 0
    identifier_propagated_rows: int = 0


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalize_issuer_name(value: str) -> str:
    ascii_value = unicodedata.normalize("NFKD", value).encode(
        "ascii", "ignore"
    ).decode("ascii")
    tokens = re.findall(r"[A-Z0-9]+", ascii_value.upper())
    normalized = [
        _CORPORATE_TOKEN_EQUIVALENTS.get(token, token)
        for token in tokens
        if token != "THE"
    ]
    normalized = [
        token for token in normalized if token not in _NON_IDENTITY_TOKENS
    ]
    collapsed: list[str] = []
    index = 0
    while index < len(normalized):
        if (
            normalized[index] == "J"
            and index + 1 < len(normalized)
            and normalized[index + 1] == "B"
        ):
            collapsed.append("JB")
            index += 2
            continue
        collapsed.append(normalized[index])
        index += 1
    normalized = collapsed
    return " ".join(normalized)


def issuer_token_signature(value: str) -> str:
    tokens = [
        token
        for token in normalize_issuer_name(value).split()
        if token != "SERVICES"
    ]
    return " ".join(sorted(tokens))


def is_valid_cusip(value: str) -> bool:
    normalized = value.strip().upper()
    if not re.fullmatch(r"[0-9A-Z*@#]{9}", normalized):
        return False
    if len(set(normalized)) == 1:
        return False

    def numeric(character: str) -> int:
        if character.isdigit():
            return int(character)
        if character.isalpha():
            return ord(character) - ord("A") + 10
        return {"*": 36, "@": 37, "#": 38}[character]

    total = 0
    for index, character in enumerate(normalized[:8]):
        number = numeric(character) * (2 if index % 2 else 1)
        total += number // 10 + number % 10
    return normalized[8].isdigit() and (10 - total % 10) % 10 == int(
        normalized[8]
    )


def _parse_date(value: str) -> date:
    for format_ in _DATE_FORMATS:
        try:
            return datetime.strptime(value.strip(), format_).date()
        except ValueError:
            continue
    raise Sec13fSecurityLedgerError(f"unsupported date: {value}")


def _read_universe(path: Path) -> list[Target]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    targets = [
        Target(
            ticker=row["ticker"].strip().upper(),
            cik=row["cik"].strip().zfill(10),
            company=row["company"].strip(),
        )
        for row in rows
        if row["eligible"] == "True"
        or "ORIGINAL_51_OVERLAP" in row["rejection_reasons"]
    ]
    if len(targets) < 400 or len({row.ticker for row in targets}) != len(targets):
        raise Sec13fSecurityLedgerError("research ticker universe is incomplete")
    return sorted(targets, key=lambda row: row.ticker)


def _submission_files(root: Path) -> dict[str, list[Path]]:
    grouped: dict[str, list[Path]] = defaultdict(list)
    for path in root.rglob("CIK*-submissions.json"):
        match = re.fullmatch(r"CIK(\d{10})-submissions\.json", path.name)
        if match:
            grouped[match.group(1)].append(path)
    return grouped


def _submission_identity(
    cik: str,
    paths: Iterable[Path],
) -> tuple[set[str], set[str], list[str]]:
    names: set[str] = set()
    tickers: set[str] = set()
    sources: list[str] = []
    for path in sorted(paths):
        payload = json.loads(path.read_text(encoding="utf-8"))
        if str(payload.get("cik", "")).zfill(10) != cik:
            raise Sec13fSecurityLedgerError(
                f"submission CIK mismatch: {path}"
            )
        if payload.get("name"):
            names.add(str(payload["name"]).strip())
        for item in payload.get("formerNames", []):
            if item.get("name"):
                names.add(str(item["name"]).strip())
        tickers.update(
            str(item).strip().upper()
            for item in payload.get("tickers", [])
            if str(item).strip()
        )
        sources.append(
            f"{path.relative_to(ROOT).as_posix()}#{sha256(path)}"
        )
    return names, tickers, sources


def build_target_identities(
    universe_path: Path = UNIVERSE,
    sec_root: Path = ROOT / "data/reference/sec",
) -> tuple[list[dict[str, str]], list[Target]]:
    targets = _read_universe(universe_path)
    by_cik: dict[str, list[Target]] = defaultdict(list)
    for target in targets:
        by_cik[target.cik].append(target)
    submissions = _submission_files(sec_root)
    rows: list[dict[str, str]] = []
    for cik, cik_targets in sorted(by_cik.items()):
        paths = submissions.get(cik, [])
        if not paths:
            raise Sec13fSecurityLedgerError(
                f"official SEC submission identity missing: {cik}"
            )
        names, sec_tickers, sources = _submission_identity(cik, paths)
        names.update(target.company for target in cik_targets)
        universe_tickers = {target.ticker for target in cik_targets}
        if not universe_tickers.issubset(sec_tickers):
            missing = sorted(universe_tickers - sec_tickers)
            raise Sec13fSecurityLedgerError(
                f"SEC ticker identity missing for {cik}: {missing}"
            )
        for name in sorted(names):
            rows.append(
                {
                    "cik": cik,
                    "universe_tickers": "|".join(sorted(universe_tickers)),
                    "official_sec_tickers": "|".join(sorted(sec_tickers)),
                    "issuer_alias": name,
                    "normalized_alias": normalize_issuer_name(name),
                    "token_signature": issuer_token_signature(name),
                    "source_files": "|".join(sources),
                    "source_authority": "SEC_SUBMISSIONS_JSON",
                }
            )
    return rows, targets


def _write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _zip_member(archive: zipfile.ZipFile, name: str) -> str:
    candidates = {
        Path(item).name.upper(): item for item in archive.namelist()
    }
    try:
        return candidates[name.upper()]
    except KeyError as error:
        raise Sec13fSecurityLedgerError(
            f"13F ZIP member missing: {name}"
        ) from error


def _tsv_rows(archive: zipfile.ZipFile, name: str) -> Iterable[dict[str, str]]:
    member = _zip_member(archive, name)
    with archive.open(member) as raw:
        text = io.TextIOWrapper(raw, encoding="utf-8-sig", newline="")
        yield from csv.DictReader(text, delimiter="\t")


def _tsv_chunks(
    archive: zipfile.ZipFile,
    name: str,
    columns: list[str],
    *,
    chunk_size: int = 250_000,
):
    import pandas as pd

    member = _zip_member(archive, name)
    with archive.open(member) as raw:
        yield from pd.read_csv(
            raw,
            sep="\t",
            usecols=columns,
            dtype=str,
            keep_default_na=False,
            chunksize=chunk_size,
        )


def _normalize_issuer_series(series):
    # 수천만 holding 행에 정규식을 반복하지 않고, chunk 안의 고유 회사명에만
    # Python 정규화를 한 번 적용한다.
    values = series.astype(str)
    mapping = {
        value: normalize_issuer_name(value)
        for value in values.drop_duplicates()
    }
    return values.map(mapping)


def _submission_periods(archive: zipfile.ZipFile) -> dict[str, date]:
    periods: dict[str, date] = {}
    for row in _tsv_rows(archive, "SUBMISSION.tsv"):
        accession = row["ACCESSION_NUMBER"].strip()
        if not accession:
            continue
        period = _parse_date(row["PERIODOFREPORT"])
        previous = periods.setdefault(accession, period)
        if previous != period:
            raise Sec13fSecurityLedgerError(
                f"accession has conflicting report periods: {accession}"
            )
    return periods


def _security_id(row: dict[str, str]) -> tuple[str, str]:
    cusip = re.sub(r"[^A-Z0-9]", "", row.get("CUSIP", "").upper())
    figi = re.sub(r"[^A-Z0-9]", "", row.get("FIGI", "").upper())
    if not is_valid_cusip(cusip):
        cusip = ""
    if figi and len(figi) != 12:
        figi = ""
    return cusip, figi


def _class_letter(title: str) -> str:
    normalized = normalize_issuer_name(title)
    match = re.search(r"(?:CL|CLASS)\s+([A-Z])(?:\s|$)", normalized)
    return match.group(1) if match else ""


def is_primary_equity_title(title: str) -> bool:
    normalized = " ".join(re.findall(r"[A-Z0-9]+", title.upper()))
    forbidden = (
        "PREF",
        "PFD",
        "WTS",
        "WARRANT",
        "NOTE",
        "BOND",
        "CONVERT",
        "ETF",
        "FUND",
        "MUT",
        "UNIT",
        "DEBT",
        "ETN",
        "SDCV",
        "INCOME",
        "INDEX",
    )
    if any(token in normalized for token in forbidden):
        return False
    if re.fullmatch(r"CL [A-Z]", normalized):
        return True
    return bool(
        re.search(
            r"\b(COM|COMMON|CMN|COMM|STOCK|STK|SHS|ORD)\b"
            r"|CAP STK|SH BEN INT",
            normalized,
        )
    )


def _ticker_for(
    cik: str,
    title: str,
    target_tickers_by_cik: dict[str, set[str]],
    cusip: str = "",
) -> tuple[str, str]:
    tickers = target_tickers_by_cik[cik]
    if len(tickers) == 1:
        return next(iter(tickers)), "SINGLE_TARGET_TICKER_FOR_CIK"
    cusip_ticker = _CUSIP_CLASS_RULES.get(cik, {}).get(cusip, "")
    if cusip_ticker in tickers:
        return cusip_ticker, "LOCKED_SHARE_CLASS_CUSIP"
    class_letter = _class_letter(title)
    title_ticker = _CLASS_RULES.get(cik, {}).get(class_letter, "")
    if title_ticker in tickers and not cusip:
        return title_ticker, f"LOCKED_SHARE_CLASS_{class_letter}"
    return "", "AMBIGUOUS_SHARE_CLASS"


def _exact_alias_index(identity_rows: list[dict[str, str]]) -> dict[str, str]:
    candidates: dict[str, set[str]] = defaultdict(set)
    for row in identity_rows:
        if row["normalized_alias"]:
            candidates[row["normalized_alias"]].add(row["cik"])
    return {
        alias: next(iter(ciks))
        for alias, ciks in candidates.items()
        if len(ciks) == 1
    }


def _signature_alias_index(
    identity_rows: list[dict[str, str]],
) -> dict[str, str]:
    candidates: dict[str, set[str]] = defaultdict(set)
    for row in identity_rows:
        signature = row["token_signature"]
        if signature:
            candidates[signature].add(row["cik"])
    return {
        signature: next(iter(ciks))
        for signature, ciks in candidates.items()
        if len(ciks) == 1
    }


def _scan_observations(
    archives: list[Path],
    aliases: dict[str, str],
    cusip_owners: dict[str, str],
    figi_owners: dict[str, str],
    target_tickers_by_cik: dict[str, set[str]],
    signature_aliases: dict[str, str] | None = None,
) -> tuple[dict[tuple[str, str, str, str], SecurityObservation], dict[str, int]]:
    observations: dict[
        tuple[str, str, str, str], SecurityObservation
    ] = {}
    diagnostics: dict[str, int] = defaultdict(int)
    signature_aliases = signature_aliases or {}
    columns = [
        "ACCESSION_NUMBER",
        "NAMEOFISSUER",
        "TITLEOFCLASS",
        "CUSIP",
        "FIGI",
        "SSHPRNAMTTYPE",
        "PUTCALL",
    ]
    for index, path in enumerate(archives, start=1):
        with zipfile.ZipFile(path) as archive:
            periods = _submission_periods(archive)
            for chunk in _tsv_chunks(archive, "INFOTABLE.tsv", columns):
                common = (
                    chunk["PUTCALL"].str.strip().eq("")
                    & chunk["SSHPRNAMTTYPE"].str.strip().str.upper().eq("SH")
                )
                selected = chunk.loc[common].copy()
                selected["NORMALIZED_ALIAS"] = _normalize_issuer_series(
                    selected["NAMEOFISSUER"]
                )
                selected["EXACT_CIK"] = selected["NORMALIZED_ALIAS"].map(
                    aliases
                ).fillna("")
                signature_mapping = {
                    value: issuer_token_signature(str(value))
                    for value in selected["NAMEOFISSUER"].drop_duplicates()
                }
                selected["SIGNATURE"] = selected["NAMEOFISSUER"].map(
                    signature_mapping
                )
                selected["SIGNATURE_CIK"] = selected["SIGNATURE"].map(
                    signature_aliases
                ).fillna("")
                normalized_cusip = (
                    selected["CUSIP"]
                    .str.upper()
                    .str.replace(r"[^A-Z0-9]", "", regex=True)
                )
                normalized_figi = (
                    selected["FIGI"]
                    .str.upper()
                    .str.replace(r"[^A-Z0-9]", "", regex=True)
                )
                selected["IDENTIFIER_CIK"] = normalized_cusip.map(
                    cusip_owners
                ).fillna("")
                missing = selected["IDENTIFIER_CIK"].eq("")
                selected.loc[missing, "IDENTIFIER_CIK"] = normalized_figi[
                    missing
                ].map(figi_owners).fillna("")
                conflicts = (
                    selected["EXACT_CIK"].ne("")
                    & selected["IDENTIFIER_CIK"].ne("")
                    & selected["EXACT_CIK"].ne(selected["IDENTIFIER_CIK"])
                )
                conflict_count = int(conflicts.sum())
                if conflict_count:
                    diagnostics["NAME_IDENTIFIER_CONFLICT"] += conflict_count
                selected = selected.loc[~conflicts].copy()
                selected["TARGET_CIK"] = selected["EXACT_CIK"].where(
                    selected["EXACT_CIK"].ne(""),
                    selected["SIGNATURE_CIK"].where(
                        selected["SIGNATURE_CIK"].ne(""),
                        selected["IDENTIFIER_CIK"],
                    ),
                )
                selected = selected.loc[
                    selected["TARGET_CIK"].isin(target_tickers_by_cik)
                ]
                for row in selected.to_dict("records"):
                    cik = str(row["TARGET_CIK"])
                    resolution = (
                        "EXACT_SEC_ISSUER_ALIAS"
                        if row["EXACT_CIK"]
                        else (
                            "UNIQUE_TOKEN_SIGNATURE"
                            if row["SIGNATURE_CIK"]
                            else "UNIQUE_IDENTIFIER_PROPAGATION"
                        )
                    )
                    accession = str(row["ACCESSION_NUMBER"]).strip()
                    period = periods.get(accession)
                    if period is None:
                        diagnostics["MISSING_REPORT_PERIOD"] += 1
                        continue
                    cusip, figi = _security_id(row)
                    if not cusip:
                        diagnostics["INVALID_CUSIP"] += 1
                        continue
                    title = str(row.get("TITLEOFCLASS", "")).strip()
                    ticker, class_resolution = _ticker_for(
                        cik, title, target_tickers_by_cik, cusip
                    )
                    if not ticker:
                        diagnostics[class_resolution] += 1
                        continue
                    key = (cik, ticker, cusip, figi)
                    observation = observations.get(key)
                    if observation is None:
                        observation = SecurityObservation(
                            cik=cik,
                            ticker=ticker,
                            cusip=cusip,
                            figi=figi,
                            issuer_name=str(
                                row.get("NAMEOFISSUER", "")
                            ).strip(),
                            title_of_class=title,
                            first_period=period,
                            last_period=period,
                        periods=set(),
                        accessions=set(),
                        period_rows={},
                        period_accessions={},
                        )
                        observations[key] = observation
                    observation.first_period = min(
                        observation.first_period, period
                    )
                    observation.last_period = max(
                        observation.last_period, period
                    )
                    observation.periods.add(period)
                    observation.accessions.add(accession)
                    observation.period_rows[period] = (
                        observation.period_rows.get(period, 0) + 1
                    )
                    observation.period_accessions.setdefault(
                        period, set()
                    ).add(accession)
                    observation.rows += 1
                    if resolution in {
                        "EXACT_SEC_ISSUER_ALIAS",
                        "UNIQUE_TOKEN_SIGNATURE",
                    }:
                        observation.exact_name_rows += 1
                    else:
                        observation.identifier_propagated_rows += 1
        print(
            f"[13F ledger] {index}/{len(archives)} {path.name}",
            flush=True,
        )
    return observations, diagnostics


def _quarter_range(start: date, end: date) -> int:
    return (end.year - start.year) * 4 + (end.month - 1) // 3 - (
        start.month - 1
    ) // 3 + 1


def _dominant_owner(
    counts: dict[str, int],
    *,
    minimum_rows: int = 20,
    minimum_fraction: float = 0.95,
    minimum_ratio: float = 10.0,
) -> str:
    ordered = sorted(counts.items(), key=lambda item: item[1], reverse=True)
    if not ordered:
        return ""
    if len(ordered) == 1:
        return ordered[0][0]
    (owner, top), (_, second) = ordered[:2]
    total = sum(counts.values())
    if (
        top >= minimum_rows
        and top / total >= minimum_fraction
        and top / max(second, 1) >= minimum_ratio
    ):
        return owner
    return ""


def _resolve_identifier_conflicts(
    observations: dict[tuple[str, str, str, str], SecurityObservation],
) -> tuple[
    dict[tuple[str, str, str, str], SecurityObservation],
    dict[str, int],
]:
    cusip_counts: dict[str, dict[str, int]] = defaultdict(
        lambda: defaultdict(int)
    )
    figi_counts: dict[str, dict[str, int]] = defaultdict(
        lambda: defaultdict(int)
    )
    for observation in observations.values():
        cusip_counts[observation.cusip][observation.cik] += len(
            observation.accessions
        )
        if observation.figi:
            figi_counts[observation.figi][observation.cik] += len(
                observation.accessions
            )
    cusip_owners = {
        identifier: _dominant_owner(dict(counts))
        for identifier, counts in cusip_counts.items()
    }
    figi_owners = {
        identifier: _dominant_owner(dict(counts))
        for identifier, counts in figi_counts.items()
    }
    admitted = {
        key: observation
        for key, observation in observations.items()
        if cusip_owners.get(observation.cusip) == observation.cik
    }
    diagnostics = {
        "identifier_conflicts_resolved_by_dominance": sum(
            1
            for counts in (*cusip_counts.values(), *figi_counts.values())
            if len(counts) > 1 and _dominant_owner(dict(counts))
        ),
        "identifier_conflicts_excluded_as_ambiguous": sum(
            1
            for counts in (*cusip_counts.values(), *figi_counts.values())
            if len(counts) > 1 and not _dominant_owner(dict(counts))
        ),
    }
    return admitted, diagnostics


def _reclassify_locked_share_classes(
    observations: dict[tuple[str, str, str, str], SecurityObservation],
    target_tickers_by_cik: dict[str, set[str]],
) -> dict[tuple[str, str, str, str], SecurityObservation]:
    reclassified = {}
    for index, observation in enumerate(observations.values()):
        ticker, _ = _ticker_for(
            observation.cik,
            observation.title_of_class,
            target_tickers_by_cik,
            observation.cusip,
        )
        if not ticker:
            continue
        observation.ticker = ticker
        key = (
            observation.cik,
            ticker,
            observation.cusip,
            observation.figi,
        )
        if key in reclassified:
            key = (*key, f"DUPLICATE_AFTER_CLASS_REVIEW_{index}")
        reclassified[key] = observation
    return reclassified


def _merge_figi_variants(
    observations: dict[tuple[str, str, str, str], SecurityObservation],
) -> dict[tuple[str, str, str, str], SecurityObservation]:
    grouped: dict[
        tuple[str, str, str], list[SecurityObservation]
    ] = defaultdict(list)
    for observation in observations.values():
        grouped[
            (observation.cik, observation.ticker, observation.cusip)
        ].append(observation)
    merged = {}
    for (cik, ticker, cusip), values in grouped.items():
        sample = max(values, key=lambda row: row.rows)
        figis = {row.figi for row in values if row.figi}
        figi = next(iter(figis)) if len(figis) == 1 else ""
        period_accessions: dict[date, set[str]] = defaultdict(set)
        period_rows: dict[date, int] = defaultdict(int)
        for value in values:
            for period, accessions in value.period_accessions.items():
                period_accessions[period].update(accessions)
            for period, rows in value.period_rows.items():
                period_rows[period] += rows
        observation = SecurityObservation(
            cik=cik,
            ticker=ticker,
            cusip=cusip,
            figi=figi,
            issuer_name=sample.issuer_name,
            title_of_class=sample.title_of_class,
            first_period=min(row.first_period for row in values),
            last_period=max(row.last_period for row in values),
            periods=set().union(*(row.periods for row in values)),
            accessions=set().union(*(row.accessions for row in values)),
            period_rows=dict(period_rows),
            period_accessions=dict(period_accessions),
            rows=sum(row.rows for row in values),
            exact_name_rows=sum(row.exact_name_rows for row in values),
            identifier_propagated_rows=sum(
                row.identifier_propagated_rows for row in values
            ),
        )
        merged[(cik, ticker, cusip, figi)] = observation
    return merged


def _select_primary_equity_observations(
    observations: dict[tuple[str, str, str, str], SecurityObservation],
) -> dict[tuple[str, str, str, str], SecurityObservation]:
    eligible = {
        key: observation
        for key, observation in observations.items()
        if is_primary_equity_title(observation.title_of_class)
    }
    by_ticker_period: dict[
        tuple[str, date], list[tuple[tuple[str, str, str, str], int]]
    ] = defaultdict(list)
    for key, observation in eligible.items():
        for period, accessions in observation.period_accessions.items():
            by_ticker_period[(observation.ticker, period)].append(
                (key, len(accessions))
            )
    selected: set[tuple[str, str, str, str]] = set()
    total_rows = {key: observation.rows for key, observation in eligible.items()}
    for candidates in by_ticker_period.values():
        winner = max(
            candidates,
            key=lambda item: (
                item[1],
                total_rows[item[0]],
                item[0][2],
            ),
        )[0]
        selected.add(winner)
    return {key: eligible[key] for key in selected}


def _interval_rows(
    observations: dict[tuple[str, str, str, str], SecurityObservation],
) -> list[dict[str, object]]:
    rows = []
    for observation in sorted(
        observations.values(),
        key=lambda row: (row.ticker, row.first_period, row.cusip, row.figi),
    ):
        expected = _quarter_range(
            observation.first_period, observation.last_period
        )
        rows.append(
            {
                "ticker": observation.ticker,
                "cik": observation.cik,
                "cusip": observation.cusip,
                "figi": observation.figi,
                "issuer_name_sample": observation.issuer_name,
                "title_of_class_sample": observation.title_of_class,
                "valid_from_report_period": observation.first_period.isoformat(),
                "valid_to_report_period": observation.last_period.isoformat(),
                "observed_quarters": len(observation.periods),
                "interval_quarters": expected,
                "quarter_coverage": round(len(observation.periods) / expected, 6),
                "accession_count": len(observation.accessions),
                "holding_row_count": observation.rows,
                "exact_name_rows": observation.exact_name_rows,
                "identifier_propagated_rows": (
                    observation.identifier_propagated_rows
                ),
                "availability": (
                    "NEXT_TRADING_SESSION_AFTER_FILING_DATE_"
                    "UNTIL_ACCEPTANCE_DATETIME_ENRICHED"
                ),
                "status": "TARGET_SECURITY_IDENTIFIER_MAPPED",
            }
        )
    return rows


def _ticker_coverage(
    targets: list[Target],
    observations: dict[tuple[str, str, str, str], SecurityObservation],
) -> list[dict[str, object]]:
    mapped: dict[str, list[SecurityObservation]] = defaultdict(list)
    for observation in observations.values():
        mapped[observation.ticker].append(observation)
    rows = []
    for target in targets:
        values = mapped.get(target.ticker, [])
        periods = (
            set().union(*(row.periods for row in values))
            if values
            else set()
        )
        observed = len(periods)
        interval = (
            _quarter_range(min(periods), max(periods)) if periods else 0
        )
        rows.append(
            {
                "ticker": target.ticker,
                "cik": target.cik,
                "company": target.company,
                "mapped_security_intervals": len(values),
                "observed_security_quarters": observed,
                "interval_quarters": interval,
                "interval_coverage": round(observed / interval, 6)
                if interval
                else 0.0,
                "status": "MAPPED" if values else "UNMAPPED_TARGET",
            }
        )
    return rows


def _scan_cache_key(
    manifest_path: Path,
    universe_path: Path,
    identity_rows: list[dict[str, str]],
) -> str:
    payload = {
        "scan_rule_version": _SCAN_RULE_VERSION,
        "manifest_sha256": sha256(manifest_path),
        "universe_sha256": sha256(universe_path),
        "identity_rows_sha256": hashlib.sha256(
            json.dumps(
                identity_rows,
                ensure_ascii=False,
                sort_keys=True,
            ).encode()
        ).hexdigest(),
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True).encode()
    ).hexdigest()


def _load_or_scan_observations(
    *,
    bulk_snapshot: Path,
    manifest_path: Path,
    universe_path: Path,
    identity_rows: list[dict[str, str]],
    archives: list[Path],
    aliases: dict[str, str],
    signature_aliases: dict[str, str],
    target_tickers_by_cik: dict[str, set[str]],
) -> tuple[
    dict[tuple[str, str, str, str], SecurityObservation],
    dict[str, int],
]:
    cache_dir = bulk_snapshot / "derived"
    cache_path = cache_dir / "security-name-match-scan-v1.json.gz"
    key_path = cache_dir / "security-name-match-scan-v1.sha256"
    expected_key = _scan_cache_key(
        manifest_path, universe_path, identity_rows
    )
    if (
        cache_path.is_file()
        and key_path.is_file()
        and key_path.read_text(encoding="utf-8").strip() == expected_key
    ):
        with gzip.open(cache_path, "rt", encoding="utf-8") as handle:
            payload = json.load(handle)
        observations = {}
        for item in payload["observations"]:
            key = tuple(item["key"])
            observation = SecurityObservation(
                cik=item["cik"],
                ticker=item["ticker"],
                cusip=item["cusip"],
                figi=item["figi"],
                issuer_name=item["issuer_name"],
                title_of_class=item["title_of_class"],
                first_period=date.fromisoformat(item["first_period"]),
                last_period=date.fromisoformat(item["last_period"]),
                periods={
                    date.fromisoformat(value) for value in item["periods"]
                },
                accessions=set(item["accessions"]),
                period_rows={
                    date.fromisoformat(period): rows
                    for period, rows in item["period_rows"].items()
                },
                period_accessions={
                    date.fromisoformat(period): set(accessions)
                    for period, accessions in item[
                        "period_accessions"
                    ].items()
                },
                rows=item["rows"],
                exact_name_rows=item["exact_name_rows"],
                identifier_propagated_rows=item[
                    "identifier_propagated_rows"
                ],
            )
            observations[key] = observation
        diagnostics = payload["diagnostics"]
        return observations, diagnostics
    observations, diagnostics = _scan_observations(
        archives,
        aliases,
        {},
        {},
        target_tickers_by_cik,
        signature_aliases,
    )
    cache_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "observations": [
            {
                "key": list(key),
                "cik": observation.cik,
                "ticker": observation.ticker,
                "cusip": observation.cusip,
                "figi": observation.figi,
                "issuer_name": observation.issuer_name,
                "title_of_class": observation.title_of_class,
                "first_period": observation.first_period.isoformat(),
                "last_period": observation.last_period.isoformat(),
                "periods": sorted(
                    period.isoformat() for period in observation.periods
                ),
                "accessions": sorted(observation.accessions),
                "period_rows": {
                    period.isoformat(): rows
                    for period, rows in sorted(
                        observation.period_rows.items()
                    )
                },
                "period_accessions": {
                    period.isoformat(): sorted(accessions)
                    for period, accessions in sorted(
                        observation.period_accessions.items()
                    )
                },
                "rows": observation.rows,
                "exact_name_rows": observation.exact_name_rows,
                "identifier_propagated_rows": (
                    observation.identifier_propagated_rows
                ),
            }
            for key, observation in observations.items()
        ],
        "diagnostics": dict(diagnostics),
    }
    temporary = cache_path.with_suffix(".json.gz.tmp")
    with gzip.open(temporary, "wt", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False)
    temporary.replace(cache_path)
    key_path.write_text(expected_key + "\n", encoding="utf-8")
    return observations, diagnostics


def generate(
    *,
    bulk_snapshot: Path = BULK_SNAPSHOT,
    universe_path: Path = UNIVERSE,
    identities_path: Path = IDENTITIES,
    intervals_path: Path = INTERVALS,
    review_path: Path = REVIEW,
    report_path: Path = REPORT,
) -> dict[str, object]:
    contract = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    gates = contract["collection_gates"]
    if contract["feature_firewall"]["role"] != "SLOW_CROWDING_CONTEXT_ONLY":
        raise Sec13fSecurityLedgerError("13F role changed")
    bulk_report = json.loads(BULK_REPORT.read_text(encoding="utf-8"))
    manifest_path = bulk_snapshot / "manifest.json"
    if (
        bulk_report.get("status") != "OFFICIAL_13F_RAW_CORPUS_HASH_LOCKED"
        or sha256(manifest_path) != bulk_report.get("manifest_sha256")
    ):
        raise Sec13fSecurityLedgerError(
            "verified 13F bulk stage receipt does not match manifest"
        )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for item in manifest["archives"]:
        path = bulk_snapshot / item["path"]
        if not path.is_file() or path.stat().st_size != item["bytes"]:
            raise Sec13fSecurityLedgerError(
                f"13F archive missing or size changed: {item['filename']}"
            )
    identity_rows, targets = build_target_identities(universe_path)
    _write_csv(
        identities_path,
        identity_rows,
        [
            "cik",
            "universe_tickers",
            "official_sec_tickers",
            "issuer_alias",
            "normalized_alias",
            "token_signature",
            "source_files",
            "source_authority",
        ],
    )
    aliases = _exact_alias_index(identity_rows)
    signature_aliases = _signature_alias_index(identity_rows)
    target_tickers_by_cik: dict[str, set[str]] = defaultdict(set)
    for target in targets:
        target_tickers_by_cik[target.cik].add(target.ticker)
    archives = [
        bulk_snapshot / item["path"] for item in manifest["archives"]
    ]
    observations, diagnostics = _load_or_scan_observations(
        bulk_snapshot=bulk_snapshot,
        manifest_path=manifest_path,
        universe_path=universe_path,
        identity_rows=identity_rows,
        archives=archives,
        aliases=aliases,
        signature_aliases=signature_aliases,
        target_tickers_by_cik=target_tickers_by_cik,
    )
    observations, conflict_diagnostics = _resolve_identifier_conflicts(
        _reclassify_locked_share_classes(
            observations, target_tickers_by_cik
        )
    )
    observations = _select_primary_equity_observations(
        _merge_figi_variants(observations)
    )
    interval_rows = _interval_rows(observations)
    coverage_rows = _ticker_coverage(targets, observations)
    _write_csv(
        intervals_path,
        interval_rows,
        [
            "ticker",
            "cik",
            "cusip",
            "figi",
            "issuer_name_sample",
            "title_of_class_sample",
            "valid_from_report_period",
            "valid_to_report_period",
            "observed_quarters",
            "interval_quarters",
            "quarter_coverage",
            "accession_count",
            "holding_row_count",
            "exact_name_rows",
            "identifier_propagated_rows",
            "availability",
            "status",
        ],
    )
    _write_csv(
        review_path,
        coverage_rows,
        [
            "ticker",
            "cik",
            "company",
            "mapped_security_intervals",
            "observed_security_quarters",
            "interval_quarters",
            "interval_coverage",
            "status",
        ],
    )
    mapped_tickers = {
        row["ticker"] for row in coverage_rows if row["status"] == "MAPPED"
    }
    evaluable_tickers = {
        row["ticker"]
        for row in coverage_rows
        if float(row["interval_coverage"])
        >= gates["minimum_per_ticker_mapping_fraction_for_evaluation"]
    }
    total_observed = sum(
        int(row["observed_security_quarters"]) for row in coverage_rows
    )
    total_interval = sum(
        int(row["interval_quarters"]) for row in coverage_rows
    )
    overall_fraction = total_observed / total_interval if total_interval else 0.0
    gate_results = {
        "minimum_mapped_research_tickers": len(mapped_tickers)
        >= gates["minimum_mapped_research_tickers"],
        "minimum_overall_ticker_quarter_mapping_fraction": overall_fraction
        >= gates["minimum_overall_ticker_quarter_mapping_fraction"],
        "minimum_per_ticker_mapping_fraction_for_evaluation": len(
            evaluable_tickers
        )
        >= gates["minimum_mapped_research_tickers"],
        "zero_identifier_collisions_admitted": not any(
            len({
                row.cik
                for row in observations.values()
                if row.cusip == observation.cusip
                or (
                    observation.figi
                    and row.figi == observation.figi
                )
            })
            > 1
            for observation in observations.values()
        ),
    }
    report = {
        "report_version": "SEC_13F_SECURITY_LEDGER_V1",
        "status": (
            "SECURITY_IDENTIFIER_LEDGER_GATE_PASSED"
            if all(gate_results.values())
            else "SECURITY_IDENTIFIER_LEDGER_GATE_FAILED"
        ),
        "source_snapshot_id": manifest["snapshot_id"],
        "source_manifest_sha256": sha256(bulk_snapshot / "manifest.json"),
        "protocol_sha256": sha256(PROTOCOL),
        "universe_sha256": sha256(universe_path),
        "identity_ledger": {
            "path": identities_path.relative_to(ROOT).as_posix(),
            "sha256": sha256(identities_path),
            "rows": len(identity_rows),
            "distinct_ciks": len({row["cik"] for row in identity_rows}),
            "distinct_tickers": len(targets),
        },
        "security_interval_ledger": {
            "path": intervals_path.relative_to(ROOT).as_posix(),
            "sha256": sha256(intervals_path),
            "rows": len(interval_rows),
            "distinct_cusips": len({
                str(row["cusip"]) for row in interval_rows
            }),
            "distinct_figis": len({
                str(row["figi"]) for row in interval_rows if row["figi"]
            }),
        },
        "coverage_review": {
            "path": review_path.relative_to(ROOT).as_posix(),
            "sha256": sha256(review_path),
            "target_tickers": len(targets),
            "target_ciks": len({row.cik for row in targets}),
            "mapped_tickers": len(mapped_tickers),
            "evaluable_tickers": len(evaluable_tickers),
            "overall_interval_coverage": round(overall_fraction, 6),
            "unmapped_tickers": sorted({
                str(row["ticker"])
                for row in coverage_rows
                if row["status"] != "MAPPED"
            }),
        },
        "diagnostics": {
            **dict(sorted(diagnostics.items())),
            **conflict_diagnostics,
            "primary_equity_security_intervals": len(observations),
        },
        "mapping_policy": {
            "mode": (
                "EXACT_OFFICIAL_SEC_CURRENT_OR_FORMER_NAME_"
                "OR_UNIQUE_DETERMINISTIC_TOKEN_SIGNATURE"
            ),
            "fuzzy_name_matching_allowed": False,
            "identifier_backfill_without_name_match_allowed": False,
            "unmatched_rows": "EXCLUDED_AND_RESERVED_FOR_SEPARATE_SOURCE_REVIEW",
            "security_selection": (
                "PRIMARY_EQUITY_TITLE_AND_MAXIMUM_DISTINCT_FILING_ROWS_"
                "PER_TICKER_REPORT_PERIOD"
            ),
            "identifier_conflict_rule": (
                "DOMINANT_CIK_AT_LEAST_95_PERCENT_AND_10X_RUNNER_UP"
            ),
        },
        "share_class_policy": {
            "multi_ticker_ciks": {
                cik: sorted(tickers)
                for cik, tickers in target_tickers_by_cik.items()
                if len(tickers) > 1
            },
            "locked_rules": _CLASS_RULES,
            "locked_cusip_rules": _CUSIP_CLASS_RULES,
            "ambiguous_classes_excluded": True,
        },
        "gate_results": gate_results,
        "price_outcomes_opened": False,
        "direction_hypothesis_executed": False,
        "exact_acceptance_datetime_ready": False,
        "operational_action_ratio": 0.0,
        "blind_holdout_access": False,
        "next_step": (
            "ENRICH_RELEVANT_ACCESSION_ACCEPTANCE_DATETIMES"
            if all(gate_results.values())
            else "RESOLVE_SECURITY_IDENTIFIER_COVERAGE"
        ),
    }
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return report


def verify_outputs(report_path: Path = REPORT) -> dict[str, object]:
    report = json.loads(report_path.read_text(encoding="utf-8"))
    if report.get("report_version") != "SEC_13F_SECURITY_LEDGER_V1":
        raise Sec13fSecurityLedgerError("unexpected report version")
    for key in ("identity_ledger", "security_interval_ledger", "coverage_review"):
        item = report[key]
        path = ROOT / item["path"]
        if not path.is_file() or sha256(path) != item["sha256"]:
            raise Sec13fSecurityLedgerError(f"output hash changed: {item['path']}")
    if report["price_outcomes_opened"] or report["blind_holdout_access"]:
        raise Sec13fSecurityLedgerError("research firewall changed")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    report = verify_outputs() if args.verify_only else generate()
    print(json.dumps(report, ensure_ascii=False))
    return 0 if report["status"].endswith("PASSED") else 1


if __name__ == "__main__":
    raise SystemExit(main())
