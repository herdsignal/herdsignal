"""독립 80건 SEC 가이던스 구조 파서 V2 원문 판정과 게이트를 고정한다."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from herd.sec_guidance_block_source_review_v1 import adjudicate


CONFIG = Path(__file__).with_name("sec_guidance_structure_review_v2.json")
PROTOCOL = Path(__file__).with_name("sec_guidance_structure_parser_v2.json")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    reviewed, report = adjudicate(
        Path(config["review_template"]),
        Path(config["labels"]),
        config,
        json.loads(PROTOCOL.read_text(encoding="utf-8")),
    )
    reviewed.to_csv(args.output, index=False, float_format="%.12g", lineterminator="\n")
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
