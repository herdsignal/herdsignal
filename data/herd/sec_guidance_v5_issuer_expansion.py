"""V5 독립 검수를 위해 로컬 미검수 기업 풀을 편향 없이 소진한다."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from herd.sec_8k_guidance_corpus_v1 import collect_documents
from herd.sec_guidance_v4_issuer_expansion import select_issuers
from herd.sec_master_index import resolve_user_agent


PROTOCOL = Path(__file__).with_suffix(".json")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--universe", type=Path, required=True)
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--collect-snapshot-id")
    parser.add_argument("--output-root", type=Path, default=Path("data/reference/sec"))
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    args = parser.parse_args()
    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    universe, catalog, report = select_issuers(protocol)
    report["report_version"] = "herd-sec-guidance-v5-issuer-expansion-v1"
    report["local_unseen_pool_exhausted"] = len(universe) < protocol["target_tickers"] or len(universe) == report["eligible_unseen_tickers"]
    report["protocol_sha256"] = hashlib.sha256(PROTOCOL.read_bytes()).hexdigest()
    args.universe.parent.mkdir(parents=True, exist_ok=True)
    universe.to_csv(args.universe, index=False, lineterminator="\n")
    catalog.to_csv(args.catalog, index=False, lineterminator="\n")
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if args.collect_snapshot_id:
        runtime = dict(protocol)
        runtime["universe"] = str(args.universe)
        print(collect_documents(
            catalog, runtime, args.output_root, args.collect_snapshot_id,
            resolve_user_agent(args.env_file),
        ))


if __name__ == "__main__":
    main()
