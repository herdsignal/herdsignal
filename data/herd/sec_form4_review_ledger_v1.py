"""워크벤치 판정을 잠긴 Form 4 검수 표본에 안전하게 결합한다."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd


IDENTITY_FIELDS = (
    "atomicTransactionId",
    "reviewHash",
    "issuerCik",
    "accessionNumber",
    "transactionCode",
    "economicClass",
    "sourceSha256",
)
ALLOWED_DECISIONS = {"PENDING", "VALID", "INVALID", "AMBIGUOUS"}


class ReviewLedgerError(RuntimeError):
    pass


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def merge(
    queue_path: Path,
    decisions_path: Path,
    output_path: Path,
    report_path: Path,
) -> dict:
    queue = pd.read_csv(queue_path, keep_default_na=False, dtype=str)
    decisions = pd.read_csv(decisions_path, keep_default_na=False, dtype=str)
    for name, frame in (("queue", queue), ("decisions", decisions)):
        missing = set(IDENTITY_FIELDS) - set(frame.columns)
        if missing:
            raise ReviewLedgerError(f"{name} missing identity fields: {sorted(missing)}")
        if frame["atomicTransactionId"].duplicated().any():
            raise ReviewLedgerError(f"{name} contains duplicate atomic IDs")
    if set(queue["atomicTransactionId"]) != set(decisions["atomicTransactionId"]):
        raise ReviewLedgerError("decision IDs must exactly match the locked queue")
    ordered = decisions.set_index("atomicTransactionId").loc[
        queue["atomicTransactionId"]
    ].reset_index()
    for field in IDENTITY_FIELDS:
        if field == "atomicTransactionId":
            continue
        if not queue[field].equals(ordered[field]):
            raise ReviewLedgerError(f"immutable review identity changed: {field}")
    labels = set(ordered["reviewDecision"])
    if unexpected := labels - ALLOWED_DECISIONS:
        raise ReviewLedgerError(f"unexpected decisions: {sorted(unexpected)}")
    notes = ordered.get(
        "reviewNotes", pd.Series([""] * len(ordered), dtype=str)
    )
    needs_note = ordered["reviewDecision"].isin({"INVALID", "AMBIGUOUS"})
    if (needs_note & notes.str.strip().eq("")).any():
        raise ReviewLedgerError("INVALID and AMBIGUOUS decisions require notes")

    merged = queue.copy()
    merged["reviewDecision"] = ordered["reviewDecision"].to_numpy()
    merged["reviewNotes"] = notes.to_numpy()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    merged.to_csv(output_path, index=False)
    counts = merged["reviewDecision"].value_counts().to_dict()
    report = {
        "report_version": "HERD_SEC_FORM4_REVIEW_LEDGER_V1",
        "status": (
            "REVIEW_LEDGER_COMPLETE"
            if counts.get("PENDING", 0) == 0 else "REVIEW_LEDGER_PENDING"
        ),
        "transactions": len(merged),
        "issuers": int(merged["issuerCik"].nunique()),
        "decision_counts": counts,
        "locked_queue_sha256": _sha256(queue_path),
        "submitted_decisions_sha256": _sha256(decisions_path),
        "adjudicated_output_sha256": _sha256(output_path),
        "identity_fields_verified": list(IDENTITY_FIELDS),
        "price_outcomes_opened": False,
        "direction_hypothesis_allowed": False,
        "operational_action_authority": False,
    }
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("queue", type=Path)
    parser.add_argument("decisions", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report-output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(merge(
        args.queue, args.decisions, args.output, args.report_output
    ), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
