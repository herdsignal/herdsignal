"""연구 후보와 예측 목표의 권한 행렬을 인벤토리와 대조한다."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

import pandas as pd

from herd.indicator_inventory_v2 import load_and_audit


MATRIX_PATH = Path(__file__).with_name("evidence_target_matrix_v1.json")


def load_and_validate(path: Path = MATRIX_PATH) -> tuple[dict, dict]:
    matrix = json.loads(path.read_text(encoding="utf-8"))
    if matrix.get("matrix_version") != "HERD_EVIDENCE_TARGET_MATRIX_V1" \
            or matrix.get("status") != "LOCKED_BEFORE_NEW_FORMULA_RESULTS":
        raise ValueError("target matrix is not locked")
    inventory, _ = load_and_audit()
    expected = {item["id"] for item in inventory["indicators"] if item["layer"] == "RESEARCH_CANDIDATE"}
    rows = matrix["rows"]
    actual = {row["indicator_id"] for row in rows}
    if actual != expected or len(actual) != len(rows):
        raise ValueError(f"target matrix coverage mismatch: missing={expected-actual}, extra={actual-expected}")
    targets = set(matrix["targets"])
    states = set(matrix["states"])
    state_counts = Counter()
    for row in rows:
        if set(row) - {"indicator_id"} != targets:
            raise ValueError(f"target columns mismatch: {row['indicator_id']}")
        for target in targets:
            if row[target] not in states:
                raise ValueError(f"invalid state: {row['indicator_id']} {target}")
            state_counts[row[target]] += 1
    if not all(matrix["transfer_rules"].values()):
        raise ValueError("evidence transfer protection was weakened")
    return matrix, {
        "report_version": "herd-evidence-target-matrix-v1-audit",
        "research_candidates": len(rows), "targets": len(targets),
        "cells": len(rows) * len(targets), "state_counts": dict(sorted(state_counts.items())),
        "coverage_complete": True, "cross_target_transfer_allowed": False,
        "direction_evidence_admitted": []
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    matrix, report = load_and_validate()
    args.csv.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(matrix["rows"]).to_csv(args.csv, index=False)
    args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
