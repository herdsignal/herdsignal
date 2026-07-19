"""Form 25 원문의 상장폐지 대상 증권 종류를 보수적으로 분류한다."""

from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path

COMMON_EQUITY = re.compile(
    r"(common stock|common shares|ordinary shares|class [a-z] common)", re.IGNORECASE
)
OTHER_SECURITY = re.compile(
    r"(note[s]?\s+due|debenture|bond|preferred stock|warrant|depositary share)",
    re.IGNORECASE,
)


def classify_form25(content: bytes) -> dict:
    text = content.decode("latin-1", errors="replace")
    common = sorted({match.group(0) for match in COMMON_EQUITY.finditer(text)})
    other = sorted({match.group(0) for match in OTHER_SECURITY.finditer(text)})
    if common and other:
        status = "COMMON_EQUITY_INCLUDED_WITH_OTHER_SECURITIES"
    elif common:
        status = "COMMON_EQUITY_FORM25_EVIDENCE"
    elif other:
        status = "OTHER_SECURITY_FORM25"
    else:
        status = "SECURITY_CLASS_NOT_PARSED"
    return {
        "status": status,
        "common_markers": common,
        "other_markers": other,
        "requires_review": True,
    }


def classify_corpus(corpus_dir: Path) -> tuple[list[dict], dict]:
    corpus = Path(corpus_dir)
    with (corpus / "index.csv").open(encoding="utf-8", newline="") as handle:
        index = list(csv.DictReader(handle))
    rows = []
    counts = {}
    for item in index:
        result = classify_form25((corpus / item["path"]).read_bytes())
        counts[result["status"]] = counts.get(result["status"], 0) + 1
        rows.append({
            **item,
            "classification_status": result["status"],
            "common_markers": "|".join(result["common_markers"]),
            "other_markers": "|".join(result["other_markers"]),
            "review_status": "REQUIRES_HUMAN_REVIEW",
        })
    return rows, {"documents": len(rows), "statuses": counts, "complete": False}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("corpus_dir", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    rows, audit = classify_corpus(args.corpus_dir)
    with args.output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(json.dumps(audit, ensure_ascii=False))


if __name__ == "__main__":
    main()
