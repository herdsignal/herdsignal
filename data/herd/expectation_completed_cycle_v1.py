"""승인된 익절과 재진입 증거가 모두 있을 때만 5% 완결 사이클을 평가한다."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


PROTOCOL = Path(__file__).with_suffix(".json")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def cycle_uplift(sell_price: float, buy_price: float, end_price: float,
                 ratio: float, sell_cost_bps: float, buy_cost_bps: float) -> float:
    """동일 주식 수 B&H 대비 매도 후 재매수한 전체 포트폴리오 수익 차이."""
    if min(sell_price, buy_price, end_price) <= 0 or not 0 < ratio <= 1:
        raise ValueError("prices and ratio must be positive")
    cash = ratio * sell_price * (1.0 - sell_cost_bps / 10_000.0)
    repurchased_shares = cash / (buy_price * (1.0 + buy_cost_bps / 10_000.0))
    return (repurchased_shares - ratio) * end_price / sell_price


def build_decision(protocol: dict, gate: dict, reentry: dict | None) -> dict:
    if reentry is None:
        raise FileNotFoundError("reentry evidence registry is required")
    admitted_reentry = list(reentry.get("admitted_reentry_evidence", []))
    blockers = []
    if not gate.get("eligible", False):
        blockers.append("COMBINATION_GATE_BLOCKED")
    if not admitted_reentry:
        blockers.append("NO_ADMITTED_REENTRY_EVIDENCE")
    eligible = not blockers
    return {
        "report_version": "herd-expectation-completed-cycle-v1",
        "decision": "READY_FOR_OOS_CYCLE_EVALUATION" if eligible else "DEPENDENCY_BLOCKED",
        "eligible": eligible,
        "blockers": blockers,
        "trim_ratio": protocol["trim_ratio"] if eligible else 0.0,
        "evaluated_cycles": 0,
        "completed_cycles": 0,
        "operational_action_authority": False,
        "operational_action_ratio": 0.0,
        "benchmark": protocol["benchmark"],
        "note": (
            "Dependencies passed; event pairing must be generated without opening blind holdout."
            if eligible else
            "No synthetic sell or reentry dates were created because required evidence is absent."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    gate_path = Path(protocol["combination_gate"])
    gate = json.loads(gate_path.read_text(encoding="utf-8"))
    reentry_path = Path(protocol["reentry_evidence_registry"])
    if not reentry_path.exists():
        raise FileNotFoundError(f"missing reentry evidence registry: {reentry_path}")
    reentry = json.loads(reentry_path.read_text(encoding="utf-8"))
    result = build_decision(protocol, gate, reentry)
    result.update({
        "protocol_sha256": _sha256(PROTOCOL),
        "combination_gate_sha256": _sha256(gate_path),
        "reentry_registry_sha256": _sha256(reentry_path),
    })
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
