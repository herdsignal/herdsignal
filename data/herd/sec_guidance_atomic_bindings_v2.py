"""원문 검수 V2를 통과한 SEC 가이던스만 불변 atomic fact 원장에 합친다."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from herd.sec_guidance_atomic_bindings_v1 import _sha256, build


PROTOCOL = Path(__file__).with_suffix(".json")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bindings", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    bindings, report = build(protocol)
    bindings.to_csv(
        args.bindings, index=False, float_format="%.12g", lineterminator="\n"
    )
    report["protocol_sha256"] = _sha256(PROTOCOL)
    report["bindings_sha256"] = _sha256(args.bindings)
    args.report.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
