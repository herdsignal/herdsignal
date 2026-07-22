"""새 60개 기업 corpus에 V3를 적용해 완전히 독립적인 정확도 표본을 만든다."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from herd.sec_guidance_block_extraction_v1 import load_aliases
from herd.sec_guidance_structure_parser_v2 import build
from herd.sec_guidance_structure_parser_v3 import PROTOCOL, parse_block_v3


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidates", type=Path, required=True)
    parser.add_argument("--review", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    corpus = Path(protocol["expansion_corpus"])
    manifest = json.loads((corpus / "manifest.json").read_text(encoding="utf-8"))
    if manifest["filings_requested"] != manifest["filings_collected"] or manifest["failures"]:
        raise ValueError("expansion corpus is incomplete")
    candidates, review, report = build(
        corpus,
        load_aliases(Path(protocol["alias_registry"])),
        protocol,
        parse_candidate=parse_block_v3,
        excluded_review_paths=protocol["development_reviews"],
        review_prefix="SG3X",
        report_version="herd-sec-guidance-structure-expansion-v3",
        minimum_review_rows=protocol["review_gate"]["minimum_stratified_rows"],
    )
    candidates.to_csv(args.candidates, index=False, float_format="%.12g", lineterminator="\n")
    review.to_csv(args.review, index=False, float_format="%.12g", lineterminator="\n")
    report.update({
        "corpus_manifest_sha256": hashlib.sha256((corpus / "manifest.json").read_bytes()).hexdigest(),
        "corpus_index_sha256": hashlib.sha256((corpus / "index.csv").read_bytes()).hexdigest(),
        "original_universe_overlap": 0,
        "next_decision": (
            "COMPLETE_FRESH_V3_SOURCE_REVIEW"
            if report["review_sample_gate_ready"]
            else "EXPAND_FRESH_V3_REVIEW_SAMPLE"
        ),
    })
    report["v3_candidates"] = report.pop("v2_candidates")
    report["v3_candidate_tickers"] = report.pop("v2_candidate_tickers")
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
