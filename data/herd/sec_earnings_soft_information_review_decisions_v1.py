"""명시적으로 판정한 SEC 실적 문구 검수 원장을 잠긴 큐에 결합한다."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import pandas as pd

from herd.sec_earnings_soft_information_measurement_v1 import ROOT


MANIFEST_PATH = ROOT / "data/herd/sec_earnings_soft_information_review_decisions_v1.json"
QUEUE_PATH = ROOT / "data/reports/sec_earnings_soft_information_source_review_v1.csv"
DECISIONS_PATH = ROOT / "data/reports/sec_earnings_soft_information_review_decisions_v1.csv"


class ReviewDecisionManifestError(ValueError):
    """명시 판정 원장이 잠긴 검수 큐와 일치하지 않을 때 발생한다."""


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_explicit_decisions(path: Path = MANIFEST_PATH) -> tuple[dict[str, Any], dict[str, tuple[str, str]]]:
    manifest = json.loads(path.read_text())
    decisions: dict[str, tuple[str, str]] = {}

    def add(review_id: str, decision: str, note: str) -> None:
        if review_id in decisions:
            raise ReviewDecisionManifestError(f"duplicate explicit decision: {review_id}")
        decisions[review_id] = (decision, note)

    for review_id in manifest["validReviewIds"]:
        add(review_id, "VALID", "")
    for group in manifest["invalidGroups"]:
        for review_id in group["reviewIds"]:
            add(review_id, "INVALID", f'{group["reasonCode"]}: {group["reviewNotes"]}')
    for group in manifest["ambiguousGroups"]:
        for review_id in group["reviewIds"]:
            add(review_id, "AMBIGUOUS", f'{group["reasonCode"]}: {group["reviewNotes"]}')
    return manifest, decisions


def materialize(
    queue_path: Path = QUEUE_PATH,
    manifest_path: Path = MANIFEST_PATH,
    output_path: Path = DECISIONS_PATH,
) -> pd.DataFrame:
    queue = pd.read_csv(queue_path, dtype=str, keep_default_na=False)
    manifest, decisions = load_explicit_decisions(manifest_path)
    if _sha256(queue_path) != manifest["lockedQueueSha256"]:
        raise ReviewDecisionManifestError("locked queue SHA-256 differs from review manifest")
    queue_ids = set(queue["review_id"])
    if set(decisions) != queue_ids:
        missing = sorted(queue_ids - set(decisions))
        extra = sorted(set(decisions) - queue_ids)
        raise ReviewDecisionManifestError(
            f"explicit decisions must cover the queue exactly; missing={missing}, extra={extra}"
        )
    if manifest["priceOrReturnOutcomesOpened"] is not False:
        raise ReviewDecisionManifestError("price/return outcomes must remain closed")
    if manifest["automaticValidLabelsCreated"] is not False:
        raise ReviewDecisionManifestError("automatic VALID labels are forbidden")

    result = queue.copy()
    result["review_decision"] = [decisions[review_id][0] for review_id in result["review_id"]]
    result["review_notes"] = [decisions[review_id][1] for review_id in result["review_id"]]
    result["reviewer_id"] = manifest["reviewerId"]
    result["reviewed_at_utc"] = manifest["reviewedAtUtc"]
    result["review_method"] = manifest["reviewMethod"]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(output_path, index=False)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--queue", type=Path, default=QUEUE_PATH)
    parser.add_argument("--manifest", type=Path, default=MANIFEST_PATH)
    parser.add_argument("--output", type=Path, default=DECISIONS_PATH)
    args = parser.parse_args()
    result = materialize(args.queue, args.manifest, args.output)
    print(json.dumps(result["review_decision"].value_counts().to_dict(), indent=2))


if __name__ == "__main__":
    main()
