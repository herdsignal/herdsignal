"""여러 SEC ticker 증거 수집본에서 후보별 최강 증거를 결정적으로 선택한다."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path

STATUS_RANK = {
    "SEC_TRADING_SYMBOL_EVIDENCE_INCOMPLETE": 0,
    "SEC_SAME_CIK_IDENTITY_DATE_UNVERIFIED": 1,
    "SEC_IDENTITY_AND_EFFECTIVE_DATE_VERIFIED": 2,
}


class SecIdentityEvidenceMergeError(RuntimeError):
    pass


def _pair_key(row: dict) -> tuple[str, str, str, str, str]:
    return (
        row.get("candidate_cik", ""),
        row["old_candidate_date"],
        row["new_candidate_date"],
        row["old_ticker"].upper(),
        row["new_ticker"].upper(),
    )


def merge_identity_evidence(collections: list[list[dict]]) -> tuple[list[dict], dict]:
    selected = {}
    for source_index, rows in enumerate(collections):
        for row in rows:
            status = row.get("identity_status", "")
            if status not in STATUS_RANK:
                raise SecIdentityEvidenceMergeError(
                    f"unsupported identity status: {status}"
                )
            candidate = {**row, "_source_index": source_index}
            key = _pair_key(row)
            previous = selected.get(key)
            if previous is None or (
                STATUS_RANK[status],
                bool(row.get("resolved_effective_date")),
                source_index,
            ) > (
                STATUS_RANK[previous["identity_status"]],
                bool(previous.get("resolved_effective_date")),
                previous["_source_index"],
            ):
                selected[key] = candidate
    merged = []
    for key in sorted(selected):
        row = dict(selected[key])
        row.pop("_source_index")
        merged.append(row)
    statuses = Counter(row["identity_status"] for row in merged)
    return merged, {
        "input_collections": len(collections),
        "unique_pair_candidates": len(merged),
        "identity_statuses": dict(sorted(statuses.items())),
        "verified_identity_pairs": statuses[
            "SEC_IDENTITY_AND_EFFECTIVE_DATE_VERIFIED"
        ],
    }


def read_csv(path: Path) -> list[dict]:
    with Path(path).open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        raise SecIdentityEvidenceMergeError("no identity evidence")
    fields = []
    for row in rows:
        for field in row:
            if field not in fields:
                fields.append(field)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with Path(path).open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inputs", nargs="+", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    rows, audit = merge_identity_evidence([read_csv(path) for path in args.inputs])
    write_csv(args.output, rows)
    print(json.dumps(audit, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
