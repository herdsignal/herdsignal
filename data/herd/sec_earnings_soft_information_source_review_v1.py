"""잠긴 SEC 실적 문구 표본의 원문 검수 정확도 게이트를 계산한다."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import pandas as pd

from herd.sec_earnings_soft_information_measurement_v1 import (
    PROTOCOL_PATH,
    ROOT,
    _load_protocol,
)


QUEUE_PATH = ROOT / "data/reports/sec_earnings_soft_information_source_review_v1.csv"
REPORT_PATH = ROOT / "data/reports/sec_earnings_soft_information_source_review_gate_v1.json"
VERSION = "HERD_SEC_EARNINGS_SOFT_INFORMATION_SOURCE_REVIEW_V1"
IDENTITY_FIELDS = (
    "review_id",
    "review_hash",
    "atomic_fact_id",
    "cik",
    "accession_number",
    "source_sha256",
    "block_path",
    "sentence_index",
    "sentence_sha256",
    "topic",
    "topic_matches",
    "cue_families",
    "cue_matches",
)
PROVENANCE_FIELDS = ("reviewer_id", "reviewed_at_utc", "review_method")


class SoftInformationReviewError(ValueError):
    """검수 표본의 동일성·판정·출처가 훼손됐을 때 발생한다."""


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def wilson_lower(successes: int, total: int, z: float = 1.959963984540054) -> float | None:
    if total == 0:
        return None
    proportion = successes / total
    denominator = 1 + z * z / total
    center = proportion + z * z / (2 * total)
    margin = z * math.sqrt(
        proportion * (1 - proportion) / total + z * z / (4 * total * total)
    )
    return (center - margin) / denominator


def merge_decisions(queue: pd.DataFrame, decisions: pd.DataFrame) -> pd.DataFrame:
    for name, frame in (("queue", queue), ("decisions", decisions)):
        missing = set(IDENTITY_FIELDS) - set(frame.columns)
        if missing:
            raise SoftInformationReviewError(f"{name} missing identity fields: {sorted(missing)}")
        if frame["review_id"].duplicated().any():
            raise SoftInformationReviewError(f"{name} contains duplicate review IDs")
    if set(queue["review_id"]) != set(decisions["review_id"]):
        raise SoftInformationReviewError("decision IDs must exactly match the locked queue")
    ordered = decisions.set_index("review_id").loc[queue["review_id"]].reset_index()
    for field in IDENTITY_FIELDS:
        if field == "review_id":
            continue
        if not queue[field].equals(ordered[field]):
            raise SoftInformationReviewError(f"immutable review identity changed: {field}")
    merged = queue.copy()
    for field in ("review_decision", "review_notes", *PROVENANCE_FIELDS):
        if field not in ordered:
            raise SoftInformationReviewError(f"decisions missing field: {field}")
        merged[field] = ordered[field].to_numpy()
    return merged


def evaluate(review: pd.DataFrame, protocol: dict[str, Any]) -> dict[str, Any]:
    gate = protocol["reviewGate"]
    decisions = set(review["review_decision"].fillna("PENDING"))
    unknown = decisions - set(gate["allowedDecisions"])
    if unknown:
        raise SoftInformationReviewError(f"unknown review decisions: {sorted(unknown)}")
    completed = review["review_decision"].ne("PENDING")
    needs_note = review["review_decision"].isin({"INVALID", "AMBIGUOUS"})
    if (needs_note & review["review_notes"].str.strip().eq("")).any():
        raise SoftInformationReviewError("INVALID and AMBIGUOUS require review notes")
    for field in PROVENANCE_FIELDS:
        if (completed & review[field].str.strip().eq("")).any():
            raise SoftInformationReviewError(f"completed decisions require {field}")
    methods = set(review.loc[completed, "review_method"])
    unexpected_methods = methods - set(gate["allowedReviewMethods"])
    if unexpected_methods:
        raise SoftInformationReviewError(
            f"unexpected review methods: {sorted(unexpected_methods)}"
        )
    decided = review.loc[completed]
    valid = int(decided["review_decision"].eq("VALID").sum())
    lower = wilson_lower(valid, len(decided))
    complete = (
        len(review) >= gate["minimumRows"]
        and len(decided) == len(review)
        and review["cik"].nunique() >= gate["minimumIssuers"]
        and review["topic"].nunique() >= gate["minimumTopics"]
        and review["era"].nunique() >= gate["minimumEras"]
    )
    passed = bool(
        complete and lower is not None and lower >= gate["minimumWilson95LowerBound"]
    )
    decided_with_reason = decided.assign(
        error_reason=decided["review_notes"].str.split(":", n=1).str[0]
    )
    error_reason_counts = (
        decided_with_reason.loc[
            decided_with_reason["review_decision"].ne("VALID"), "error_reason"
        ]
        .replace("", "UNCLASSIFIED")
        .value_counts()
        .sort_index()
        .to_dict()
    )
    topic_review: dict[str, dict[str, Any]] = {}
    for topic, rows in decided.groupby("topic", sort=True):
        topic_valid = int(rows["review_decision"].eq("VALID").sum())
        topic_review[str(topic)] = {
            "rows": len(rows),
            "validRows": topic_valid,
            "invalidRows": int(rows["review_decision"].eq("INVALID").sum()),
            "ambiguousRows": int(rows["review_decision"].eq("AMBIGUOUS").sum()),
            "precision": topic_valid / len(rows),
        }
    if passed:
        next_gate = protocol["nextGateOnReviewPass"]
    elif complete:
        next_gate = protocol["nextGateOnReviewFailure"]
    else:
        next_gate = protocol["nextGateWhilePending"]
    return {
        "reportVersion": VERSION,
        "status": "SOURCE_REVIEW_PASSED" if passed else (
            "SOURCE_REVIEW_FAILED" if complete else "SOURCE_REVIEW_PENDING"
        ),
        "reviewRows": len(review),
        "reviewedRows": len(decided),
        "issuers": int(review["cik"].nunique()),
        "topics": int(review["topic"].nunique()),
        "eras": int(review["era"].nunique()),
        "validRows": valid,
        "invalidRows": int(decided["review_decision"].eq("INVALID").sum()),
        "ambiguousRows": int(decided["review_decision"].eq("AMBIGUOUS").sum()),
        "sourcePrecision": valid / len(decided) if len(decided) else None,
        "wilson95LowerBound": lower,
        "reviewComplete": complete,
        "reviewGatePassed": passed,
        "minimumWilson95LowerBound": gate["minimumWilson95LowerBound"],
        "wilsonGapToPass": (
            max(0.0, gate["minimumWilson95LowerBound"] - lower)
            if lower is not None else None
        ),
        "errorReasonCounts": error_reason_counts,
        "topicReview": topic_review,
        "priceOrReturnOutcomesOpened": False,
        "directionHypothesisPreregistered": False,
        "operationalAction": "HOLD",
        "operationalActionRatio": 0.0,
        "nextGate": next_gate,
    }


def adjudicate(
    queue_path: Path,
    decisions_path: Path,
    output_path: Path,
    report_path: Path,
) -> dict[str, Any]:
    protocol = _load_protocol(PROTOCOL_PATH)
    queue = pd.read_csv(queue_path, dtype=str, keep_default_na=False)
    decisions = pd.read_csv(decisions_path, dtype=str, keep_default_na=False)
    merged = merge_decisions(queue, decisions)
    report = evaluate(merged, protocol)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    merged.to_csv(output_path, index=False)
    report.update({
        "lockedQueueSha256": _sha256(queue_path),
        "submittedDecisionsSha256": _sha256(decisions_path),
        "adjudicatedSha256": _sha256(output_path),
    })
    report_path.write_text(json.dumps(report, indent=2) + "\n")
    return report


def write_pending_report(
    queue_path: Path = QUEUE_PATH,
    report_path: Path = REPORT_PATH,
) -> dict[str, Any]:
    protocol = _load_protocol(PROTOCOL_PATH)
    review = pd.read_csv(queue_path, dtype=str, keep_default_na=False)
    report = evaluate(review, protocol)
    report["lockedQueueSha256"] = _sha256(queue_path)
    report_path.write_text(json.dumps(report, indent=2) + "\n")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--queue", type=Path, default=QUEUE_PATH)
    parser.add_argument("--decisions", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--report", type=Path, default=REPORT_PATH)
    args = parser.parse_args()
    if args.decisions:
        if args.output is None:
            raise SystemExit("--output is required with --decisions")
        result = adjudicate(args.queue, args.decisions, args.output, args.report)
    else:
        result = write_pending_report(args.queue, args.report)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
