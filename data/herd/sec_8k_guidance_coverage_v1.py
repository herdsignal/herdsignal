"""고정된 8-K 원문에서 가이던스 표준화 가능 범위만 측정한다."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import html
import json
import re
from pathlib import Path

import pandas as pd


GUIDANCE = re.compile(r"\b(guidance|outlook|forecast|we\s+(?:expect|anticipate|project)|company\s+expects)\b", re.I)
RANGE = re.compile(
    r"(?:between\s+[$€£]?\s*[\d,.]+\s*(?:million|billion|%|cents)?\s+and\s+[$€£]?\s*[\d,.]+|"
    r"(?:range\s+of|from)\s+[$€£]?\s*[\d,.]+\s*(?:million|billion|%|cents)?\s+(?:to|through|-)\s+[$€£]?\s*[\d,.]+)", re.I
)
PERIOD = re.compile(
    r"\b(?:FY\s*20\d{2}|fiscal\s+(?:year|20\d{2})|full[- ]year|"
    r"(?:first|second|third|fourth|next)\s+quarter|Q[1-4]\s*20\d{2})\b", re.I
)
METRICS = {
    "REVENUE": re.compile(r"\b(revenue|net sales)\b", re.I),
    "EPS": re.compile(r"\b(earnings per share|diluted EPS|adjusted EPS)\b", re.I),
    "MARGIN": re.compile(r"\b(operating margin|gross margin|EBITDA margin)\b", re.I),
    "OPERATING_INCOME": re.compile(r"\b(operating income|EBITDA)\b", re.I),
    "FREE_CASH_FLOW": re.compile(r"\b(free cash flow|operating cash flow)\b", re.I),
    "CAPEX": re.compile(r"\b(capital expenditures|capex)\b", re.I),
}


def plain_text(content: bytes) -> str:
    decoded = content.decode("utf-8", errors="ignore")
    decoded = re.sub(r"(?is)<script.*?</script>|<style.*?</style>", " ", decoded)
    decoded = re.sub(r"(?s)<[^>]+>", " ", decoded)
    return re.sub(r"\s+", " ", html.unescape(decoded)).strip()


def measure_text(text: str) -> dict:
    guidance_matches = list(GUIDANCE.finditer(text))
    windows = " ".join(text[max(0, match.start() - 500):match.end() + 1500] for match in guidance_matches)
    metrics = sorted(name for name, pattern in METRICS.items() if pattern.search(windows))
    return {
        "guidance_language": bool(guidance_matches),
        "quantitative_range": bool(guidance_matches and RANGE.search(windows)),
        "target_period": bool(guidance_matches and PERIOD.search(windows)),
        "metrics": metrics,
    }


def audit(corpus: Path) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    manifest_path, index_path = corpus / "manifest.json", corpus / "index.csv"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    index = pd.read_csv(index_path, dtype={"cik": str})
    rows = []
    for accession, documents in index.groupby("accession_number", sort=False):
        chunks = []
        for path in documents["path"].drop_duplicates():
            with gzip.open(corpus / path, "rb") as stream:
                chunks.append(plain_text(stream.read()))
        measured = measure_text(" ".join(chunks))
        first = documents.iloc[0]
        rows.append({
            "ticker": first["ticker"], "cik": first["cik"],
            "accession_number": accession, "accepted_at": first["accepted_at"],
            "items": first["items"], "documents": int(len(documents)),
            "guidance_language": measured["guidance_language"],
            "quantitative_range": measured["quantitative_range"],
            "target_period": measured["target_period"],
            "metrics": "|".join(measured["metrics"]),
            "classification_status": (
                "GUIDANCE_COMPARABILITY_PENDING"
                if measured["guidance_language"] else "NO_GUIDANCE_LANGUAGE_DETECTED"
            ),
            "guidance_direction": "NOT_CLASSIFIED",
        })
    filings = pd.DataFrame(rows).sort_values(["accepted_at", "ticker", "accession_number"])
    filings["year"] = pd.to_datetime(filings["accepted_at"], utc=True).dt.year
    coverage = filings.groupby(["ticker", "year"], as_index=False).agg(
        filings=("accession_number", "size"),
        guidance_filings=("guidance_language", "sum"),
        quantitative_range_filings=("quantitative_range", "sum"),
        target_period_filings=("target_period", "sum"),
    )
    report = {
        "report_version": "herd-sec-8k-guidance-coverage-v1",
        "snapshot_id": manifest["snapshot_id"],
        "snapshot_manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
        "filings_requested": manifest["filings_requested"],
        "filings_collected": manifest["filings_collected"],
        "collection_failures": len(manifest["failures"]),
        "filings_audited": len(filings),
        "tickers_audited": int(filings["ticker"].nunique()),
        "guidance_language_filings": int(filings["guidance_language"].sum()),
        "quantitative_range_filings": int(filings["quantitative_range"].sum()),
        "target_period_filings": int(filings["target_period"].sum()),
        "guidance_direction_classified": 0,
        "ready_for_direction_standardization": False,
        "operational_action_ratio": 0.0,
        "limitations": [
            "Lexical coverage is not a guidance direction label.",
            "Issuer-specific non-GAAP metrics and fiscal periods still require normalization.",
            "Prior and current guidance ranges have not yet been paired.",
            "No analyst consensus is inferred."
        ],
    }
    return filings, coverage, report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("corpus", type=Path)
    parser.add_argument("--filings", type=Path, required=True)
    parser.add_argument("--coverage", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    filings, coverage, report = audit(args.corpus)
    args.filings.parent.mkdir(parents=True, exist_ok=True)
    filings.to_csv(args.filings, index=False, lineterminator="\n")
    coverage.to_csv(args.coverage, index=False, lineterminator="\n")
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
