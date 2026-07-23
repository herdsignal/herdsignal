"""V10 마지막 독립 검증용 신규 기업 모집단을 결과 비관측 상태로 고정한다."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

import pandas as pd


PROTOCOL = Path(__file__).with_suffix(".json")
COMMON_TICKER = re.compile(r"^[A-Z]{1,5}$")
EXCLUDED_NAME = re.compile(
    r"\b(?:ETF|ETN|FUND|TRUST|PORTFOLIO|ACQUISITION|SPAC|WARRANT|RIGHTS?|UNITS?)\b",
    re.I,
)


def select_metadata_universe(protocol: dict) -> tuple[pd.DataFrame, dict]:
    mapping = pd.read_csv(protocol["ticker_mapping"], dtype={"cik": str})
    mapping["ticker"] = mapping["ticker"].fillna("").astype(str).str.upper()
    excluded_tickers = set(
        pd.read_csv(protocol["existing_universe"])["ticker"].astype(str).str.upper()
    )
    excluded_ciks = set(
        pd.read_csv(protocol["existing_universe"], dtype={"cik": str})["cik"]
        .dropna().astype(str).str.replace(r"\.0$", "", regex=True).str.zfill(10)
    )
    for path in protocol["review_ledgers"]:
        review = pd.read_csv(path, dtype={"cik": str})
        excluded_tickers.update(review["ticker"].astype(str).str.upper())
        excluded_ciks.update(
            review["cik"].dropna().astype(str).str.replace(r"\.0$", "", regex=True).str.zfill(10)
        )
    eligible = mapping.loc[
        mapping["exchange"].isin(protocol["exchanges"])
        & mapping["ticker"].map(lambda value: bool(COMMON_TICKER.fullmatch(value)))
        & ~mapping["company_name"].astype(str).str.contains(EXCLUDED_NAME, na=False)
        & ~mapping["ticker"].isin(excluded_tickers)
        & ~mapping["cik"].astype(str).str.zfill(10).isin(excluded_ciks)
    ].copy()
    eligible["selection_priority"] = eligible.apply(
        lambda row: hashlib.sha256(
            f'{protocol["selection_salt"]}:{row["cik"]}:{row["ticker"]}'.encode()
        ).hexdigest(),
        axis=1,
    )
    selected = eligible.sort_values("selection_priority").drop_duplicates("cik").head(
        protocol["metadata_target_tickers"]
    )
    output = selected[["ticker", "cik", "company_name", "exchange", "selection_priority"]].copy()
    output["cik"] = output["cik"].astype(str).str.zfill(10)
    output["cik_link_status"] = "UNIQUE_CIK_NAME_CANDIDATE"
    output = output.sort_values("selection_priority").reset_index(drop=True)
    report = {
        "report_version": "herd-sec-guidance-v10-final-expansion-v1",
        "scope": protocol["scope"],
        "mapping_rows": len(mapping),
        "excluded_tickers": len(excluded_tickers),
        "excluded_ciks": len(excluded_ciks),
        "eligible_unseen_issuers": len(eligible),
        "selected_metadata_tickers": len(output),
        "selected_exchanges": sorted(output["exchange"].unique()),
        "selection_used_guidance_text": False,
        "selection_used_parser_output": False,
        "selection_used_source_review_labels": False,
        "selection_used_price_outcomes": False,
        "operational_action_ratio": 0.0,
    }
    return output, report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--universe", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    protocol = json.loads(PROTOCOL.read_text())
    universe, report = select_metadata_universe(protocol)
    universe.to_csv(args.universe, index=False, lineterminator="\n")
    report["protocol_sha256"] = hashlib.sha256(PROTOCOL.read_bytes()).hexdigest()
    report["universe_sha256"] = hashlib.sha256(args.universe.read_bytes()).hexdigest()
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
