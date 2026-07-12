"""저장된 Validation v2 리포트의 OOS 실패 진단 실행기."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_DATA_DIR = Path(__file__).resolve().parent.parent
if str(_DATA_DIR) not in sys.path:
    sys.path.insert(0, str(_DATA_DIR))

from herd.validation_diagnostics import write_diagnostics


def main() -> None:
    parser = argparse.ArgumentParser(description="HERD OOS 실패 진단")
    parser.add_argument("--source", default="reports/validation_v2/validation_v2.json")
    parser.add_argument("--output", default="reports/validation_v2")
    args = parser.parse_args()
    json_path, csv_path = write_diagnostics(Path(args.source), Path(args.output))
    print("진단 리포트:", json_path, csv_path)


if __name__ == "__main__": main()

