"""S&P 공식 회사명을 EDGAR master index의 영구 CIK 후보에 연결한다."""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import defaultdict
from pathlib import Path

try:
    from herd.sec_master_index import HEADER
except ModuleNotFoundError:  # 직접 스크립트 실행
    from sec_master_index import HEADER

SUFFIXES = {
    "INC", "INCORPORATED", "CORP", "CORPORATION", "CO", "COMPANY", "PLC",
    "LTD", "LIMITED", "LLC",
}


class SecCikLinkerError(RuntimeError):
    pass


def canonical_name(value: str, *, remove_suffixes: bool = False) -> str:
    normalized = value.upper().replace("&", " AND ")
    tokens = re.findall(r"[A-Z0-9]+", normalized)
    if remove_suffixes:
        while tokens and tokens[-1] in SUFFIXES:
            tokens.pop()
    return " ".join(tokens)


def iter_master_rows(path: Path):
    with Path(path).open(encoding="latin-1") as handle:
        found_header = False
        for raw in handle:
            line = raw.strip()
            if not found_header:
                found_header = line == HEADER
                continue
            if not line or set(line) == {"-"}:
                continue
            parts = line.split("|")
            if len(parts) != 5:
                raise SecCikLinkerError(f"invalid master row in {path.name}")
            yield parts
    if not found_header:
        raise SecCikLinkerError(f"missing master header: {path.name}")


def build_name_index(master_snapshot: Path, target_names: set[str]) -> dict:
    exact_targets = {canonical_name(name) for name in target_names}
    base_targets = {canonical_name(name, remove_suffixes=True) for name in target_names}
    matches = defaultdict(lambda: defaultdict(lambda: {
        "sec_names": set(), "first_filed": None, "last_filed": None, "forms": set(),
    }))
    for path in sorted((Path(master_snapshot) / "raw").glob("*-master.idx")):
        for cik, company, form, filed, _ in iter_master_rows(path):
            exact = canonical_name(company)
            base = canonical_name(company, remove_suffixes=True)
            keys = []
            if exact in exact_targets:
                keys.append(("EXACT", exact))
            if base in base_targets:
                keys.append(("BASE", base))
            for mode, key in keys:
                item = matches[(mode, key)][f"{int(cik):010d}"]
                item["sec_names"].add(company)
                item["forms"].add(form)
                item["first_filed"] = min(filter(None, [item["first_filed"], filed]))
                item["last_filed"] = max(filter(None, [item["last_filed"], filed]))
    return matches


def link_events(events: list[dict], matches: dict) -> tuple[list[dict], dict]:
    linked = []
    for event in events:
        name = event["company_name"]
        exact = matches.get(("EXACT", canonical_name(name)), {})
        base = matches.get(("BASE", canonical_name(name, remove_suffixes=True)), {})
        candidates = exact or base
        mode = "EXACT_NAME" if exact else "SUFFIX_NORMALIZED_NAME"
        if len(candidates) == 1:
            cik, detail = next(iter(candidates.items()))
            status = "UNIQUE_CIK_NAME_CANDIDATE"
        elif len(candidates) > 1:
            cik, detail = "", None
            status = "AMBIGUOUS_CIK_NAME_CANDIDATE"
        else:
            cik, detail = "", None
            status = "NO_CIK_NAME_CANDIDATE"
        linked.append({
            **event,
            "cik": cik,
            "cik_link_status": status,
            "name_match_method": mode if candidates else "",
            "candidate_cik_count": len(candidates),
            "sec_names": "|".join(sorted(detail["sec_names"])) if detail else "",
            "sec_first_filed": detail["first_filed"] if detail else "",
            "sec_last_filed": detail["last_filed"] if detail else "",
        })
    counts = {}
    for row in linked:
        counts[row["cik_link_status"]] = counts.get(row["cik_link_status"], 0) + 1
    return linked, {
        "events": len(linked),
        "statuses": counts,
        "complete": bool(linked) and all(
            row["cik_link_status"] == "UNIQUE_CIK_NAME_CANDIDATE" for row in linked
        ),
    }


def read_csv(path: Path) -> list[dict]:
    with Path(path).open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        raise SecCikLinkerError("no linked events")
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with Path(path).open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("events", type=Path)
    parser.add_argument("master_snapshot", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    events = read_csv(args.events)
    names = {row["company_name"] for row in events if row.get("company_name")}
    matches = build_name_index(args.master_snapshot, names)
    rows, audit = link_events(events, matches)
    write_csv(args.output, rows)
    print(json.dumps(audit, ensure_ascii=False))


if __name__ == "__main__":
    main()
