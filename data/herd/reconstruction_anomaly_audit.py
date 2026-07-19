"""공개 재구성본의 폐쇄 루프·표기 진동을 공식 사건 원장 밖으로 격리한다."""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

RECONSTRUCTION_ANOMALY = "PUBLIC_RECONSTRUCTION_ANOMALY"


class ReconstructionAnomalyAuditError(RuntimeError):
    pass


def _normalized_ticker(ticker: str) -> str:
    ticker = re.sub(r"\s*\(PREVIOUSLY[^)]*\)\s*", "", ticker.upper())
    return re.sub(r"[^A-Z0-9]", "", ticker)


def audit_reconstruction_anomalies(
    classified_events: list[dict],
    identity_transitions: list[dict],
    *,
    maximum_loop_days: int = 7,
) -> tuple[list[dict], dict]:
    verified_tickers = {
        ticker.upper()
        for row in identity_transitions
        for ticker in (row["old_ticker"], row["new_ticker"])
    }
    by_ticker = defaultdict(list)
    for row in classified_events:
        if row["residual_category"] == RECONSTRUCTION_ANOMALY:
            by_ticker[_normalized_ticker(row["ticker"])].append(row)
    groups = {}
    for normalized, rows in by_ticker.items():
        ordered = sorted(rows, key=lambda row: row["candidate_effective_date"])
        cluster = []
        cluster_index = 0
        for row in ordered:
            row_date = date.fromisoformat(row["candidate_effective_date"])
            if cluster and (
                row_date
                - date.fromisoformat(cluster[-1]["candidate_effective_date"])
            ).days > maximum_loop_days:
                groups[(normalized, cluster_index)] = cluster
                cluster = []
                cluster_index += 1
            cluster.append(row)
        if cluster:
            groups[(normalized, cluster_index)] = cluster
    results = []
    for (normalized, _cluster_index), rows in groups.items():
        dates = [date.fromisoformat(row["candidate_effective_date"]) for row in rows]
        actions = Counter(row["action"].upper() for row in rows)
        net_effect = actions["ADD"] - actions["REMOVE"]
        span_days = (max(dates) - min(dates)).days
        original_tickers = {row["ticker"].upper() for row in rows}
        formatting_only = len(original_tickers) > 1
        has_official_conflict = any(
            row["reconciliation_status"] in {
                "CANDIDATE_ACTION_CONFLICTS_WITH_OFFICIAL_PROSE",
                "DISTANT_SAME_TICKER_EVENT_REQUIRES_IDENTITY_REVIEW",
            }
            for row in rows
        )
        has_verified_identity_context = bool(original_tickers & verified_tickers)
        evidence_sufficient = (
            net_effect == 0
            and span_days <= maximum_loop_days
            and (
                formatting_only
                or has_official_conflict
                or has_verified_identity_context
            )
        )
        if formatting_only:
            anomaly_type = "TICKER_FORMAT_OSCILLATION"
        elif has_verified_identity_context:
            anomaly_type = "STALE_TICKER_CLOSED_LOOP"
        elif has_official_conflict:
            anomaly_type = "OFFICIAL_SEMANTICS_CONFLICT_CLOSED_LOOP"
        else:
            anomaly_type = "UNSUPPORTED_CLOSED_LOOP"
        for row in rows:
            results.append({
                "candidate_effective_date": row["candidate_effective_date"],
                "action": row["action"].upper(),
                "ticker": row["ticker"].upper(),
                "normalized_ticker": normalized,
                "anomaly_type": anomaly_type,
                "group_adds": actions["ADD"],
                "group_removes": actions["REMOVE"],
                "group_net_effect": net_effect,
                "group_span_days": span_days,
                "supporting_identity_context": has_verified_identity_context,
                "supporting_official_conflict": has_official_conflict,
                "exclude_from_official_ledger": evidence_sufficient,
                "review_status": (
                    "QUARANTINED_SOURCE_ARTIFACT"
                    if evidence_sufficient else "REQUIRES_HUMAN_REVIEW"
                ),
            })
    excluded = sum(row["exclude_from_official_ledger"] for row in results)
    return sorted(results, key=lambda row: (
        row["candidate_effective_date"], row["action"], row["ticker"]
    )), {
        "anomaly_candidate_rows": len(results),
        "anomaly_groups": len(groups),
        "quarantined_rows": excluded,
        "open_review_rows": len(results) - excluded,
        "composition_effect_of_quarantine": 0 if excluded == len(results) else None,
        "survivorship_safe": False,
    }


def read_csv(path: Path) -> list[dict]:
    with Path(path).open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        raise ReconstructionAnomalyAuditError("no reconstruction anomalies")
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with Path(path).open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("classified_events", type=Path)
    parser.add_argument("identity_transitions", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    rows, audit = audit_reconstruction_anomalies(
        read_csv(args.classified_events), read_csv(args.identity_transitions)
    )
    write_csv(args.output, rows)
    print(json.dumps(audit, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
