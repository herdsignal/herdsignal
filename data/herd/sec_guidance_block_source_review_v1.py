"""잠긴 85건 SEC 블록 원문 판정을 검증하고 별도 adjudicated 원장을 만든다."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd

from herd.sec_guidance_table_review_gate_v1 import evaluate


CONFIG = Path(__file__).with_name("sec_guidance_block_review_labels_v1.json")


def adjudicate(template: Path, labels: Path, config: dict, protocol: dict) -> tuple[pd.DataFrame, dict]:
    digest = hashlib.sha256(template.read_bytes()).hexdigest()
    if digest != config["review_template_sha256"]:
        raise ValueError("Review template hash mismatch; labels cannot be applied to a changed sample")
    review = pd.read_csv(template, dtype={"review_id": str}).copy()
    decisions = pd.read_csv(labels, dtype={"review_id": str})
    if decisions["review_id"].duplicated().any():
        raise ValueError("Duplicate review_id in source-review labels")
    if set(review["review_id"]) != set(decisions["review_id"]):
        raise ValueError("Source-review labels must cover the locked sample exactly")
    unknown = set(decisions["review_decision"]) - set(config["allowed_decisions"])
    if unknown:
        raise ValueError(f"Unknown decisions: {sorted(unknown)}")
    if decisions["review_reason"].isna().any() or decisions["review_reason"].str.strip().eq("").any():
        raise ValueError("Every source-review decision requires a reason")
    adjudicated = review.drop(columns=["review_decision", "review_reason", "reviewer", "reviewed_at"]).merge(
        decisions, on="review_id", how="left", validate="one_to_one",
    )
    adjudicated["reviewer"] = config["reviewer"]
    adjudicated["reviewed_at"] = config["reviewed_at"]
    report = evaluate(adjudicated, protocol)
    report.update({
        "report_version": "herd-sec-guidance-block-source-review-v1",
        "review_template_sha256": digest,
        "labels_sha256": hashlib.sha256(labels.read_bytes()).hexdigest(),
        "price_outcomes_observed": config["price_outcomes_observed"],
    })
    return adjudicated, report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    config = json.loads(CONFIG.read_text())
    protocol_path = Path(__file__).with_name("sec_guidance_block_extraction_v1.json")
    adjudicated, report = adjudicate(
        Path(config["review_template"]), Path(config["labels"]), config,
        json.loads(protocol_path.read_text()),
    )
    adjudicated.to_csv(args.output, index=False, float_format="%.12g", lineterminator="\n")
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
