"""검수된 V2 atomic fact만 동일 의미·기간의 연속 전망 수정쌍으로 연결한다."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from herd.sec_guidance_atomic_bindings_v1 import _sha256
from herd.sec_guidance_atomic_pairs_v1 import build


PROTOCOL = Path(__file__).with_suffix(".json")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pairs", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    pairs, report = build(protocol)
    pairs.to_csv(args.pairs, index=False, float_format="%.12g", lineterminator="\n")
    report["protocol_sha256"] = _sha256(PROTOCOL)
    report["pairs_sha256"] = _sha256(args.pairs)
    args.report.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
