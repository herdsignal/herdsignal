"""잠긴 SEC 가이던스 atomic 후보를 원문 판정과 결합해 정확도 게이트를 계산한다."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import math
from pathlib import Path

import pandas as pd


CONFIG = Path(__file__).with_suffix(".json")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _wilson_lower(successes: int, trials: int, z: float = 1.959963984540054) -> float:
    if trials <= 0:
        return 0.0
    proportion = successes / trials
    denominator = 1 + z * z / trials
    centre = proportion + z * z / (2 * trials)
    margin = z * math.sqrt(
        proportion * (1 - proportion) / trials + z * z / (4 * trials * trials)
    )
    return (centre - margin) / denominator


def adjudicate(config: dict) -> tuple[pd.DataFrame, dict]:
    template_path = Path(config["review_template"])
    if _sha256(template_path) != config["review_template_sha256"]:
        raise ValueError("atomic census review template changed after lock")
    template = pd.read_csv(template_path, dtype={"review_id": str, "cik": str})
    labels_path = Path(config["labels"])
    labels = pd.read_csv(labels_path, dtype={"review_id": str})
    if labels["review_id"].duplicated().any():
        raise ValueError("duplicate atomic census review label")
    if set(labels["review_id"]) != set(template["review_id"]):
        raise ValueError("labels must cover the locked atomic census exactly")
    unknown = set(labels["review_decision"]) - set(config["allowed_decisions"])
    if unknown:
        raise ValueError(f"unknown review decisions: {sorted(unknown)}")
    if labels["review_reason"].isna().any() or labels["review_reason"].str.strip().eq("").any():
        raise ValueError("every atomic source decision requires a reason")

    reviewed = template.drop(
        columns=["review_decision", "review_reason", "reviewer", "reviewed_at"]
    ).merge(labels, on="review_id", how="left", validate="one_to_one")
    reviewed["reviewer"] = config["reviewer"]
    reviewed["reviewed_at"] = config["reviewed_at"]
    source_integrity = []
    for row in reviewed.itertuples(index=False):
        with gzip.open(row.source_path, "rb") as source:
            source_integrity.append(hashlib.sha256(source.read()).hexdigest() == row.source_sha256)
    reviewed["source_integrity_passed"] = source_integrity
    if not reviewed["source_integrity_passed"].all():
        raise ValueError("review source bytes changed after candidate lock")

    counts = reviewed["review_decision"].value_counts().to_dict()
    valid = int(counts.get("VALID", 0))
    invalid = int(counts.get("INVALID", 0))
    ambiguous = int(counts.get("AMBIGUOUS", 0))
    denominator = valid + invalid
    precision = valid / denominator if denominator else 0.0
    lower = _wilson_lower(valid, denominator)
    passed = bool(
        lower >= config["minimum_wilson_95_lower_bound"]
        and reviewed["source_integrity_passed"].all()
    )
    report = {
        "report_version": "herd-sec-guidance-atomic-census-v2-source-review",
        "review_rows": len(reviewed),
        "valid_rows": valid,
        "invalid_rows": invalid,
        "ambiguous_rows": ambiguous,
        "determinate_rows": denominator,
        "candidate_precision": precision,
        "wilson_95_lower_bound": lower,
        "minimum_wilson_95_lower_bound": config["minimum_wilson_95_lower_bound"],
        "source_integrity_passed": bool(reviewed["source_integrity_passed"].all()),
        "source_review_gate_passed": passed,
        "price_outcomes_observed": config["price_outcomes_observed"],
        "blind_holdout_access": config["blind_holdout_access"],
        "operational_action_authority": config["operational_action_authority"],
        "next_decision": (
            "BUILD_SOURCE_REVIEWED_ATOMIC_BINDINGS_V2"
            if passed else "STOP_ATOMIC_GUIDANCE_RESEARCH"
        ),
        "template_sha256": _sha256(template_path),
        "labels_sha256": _sha256(labels_path),
    }
    return reviewed, report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reviewed", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    reviewed, report = adjudicate(config)
    reviewed.to_csv(args.reviewed, index=False, float_format="%.12g", lineterminator="\n")
    report["config_sha256"] = _sha256(CONFIG)
    report["reviewed_sha256"] = _sha256(args.reviewed)
    args.report.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
