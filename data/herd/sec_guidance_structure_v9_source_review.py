"""잠긴 V9 80건을 SEC 원문으로 판정하고 Wilson 정확도 게이트를 계산한다."""

import argparse
import json
from pathlib import Path

from herd.sec_guidance_block_source_review_v1 import adjudicate


CONFIG = Path(__file__).with_name("sec_guidance_structure_v9_review.json")
PROTOCOL = Path(__file__).with_name("sec_guidance_v9_independent_validation.json")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    config = json.loads(CONFIG.read_text())
    reviewed, report = adjudicate(
        Path(config["review_template"]), Path(config["labels"]), config,
        json.loads(PROTOCOL.read_text()),
    )
    reviewed.to_csv(args.output, index=False, float_format="%.12g", lineterminator="\n")
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
