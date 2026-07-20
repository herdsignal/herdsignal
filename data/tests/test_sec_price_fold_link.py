import csv
import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from herd.sec_price_fold_link import build_links, collection_queue


class SecPriceFoldLinkTest(unittest.TestCase):
    def _corpus(self, root: Path) -> Path:
        raw = root / "raw"
        raw.mkdir(parents=True)
        (raw / "CIK0000000001-submissions.json").write_text(
            json.dumps({
                "filings": {"recent": {
                    "accessionNumber": ["a1"],
                    "acceptanceDateTime": ["2020-02-01T21:00:00Z"],
                }}
            }),
            encoding="utf-8",
        )
        (raw / "CIK0000000001-companyfacts.json").write_text(
            json.dumps({
                "cik": 1,
                "entityName": "AAA",
                "facts": {"us-gaap": {"NetIncomeLoss": {
                    "label": "Net income",
                    "units": {"USD": [{
                        "start": "2019-01-01",
                        "end": "2019-12-31",
                        "val": 10,
                        "accn": "a1",
                        "form": "10-K",
                        "filed": "2020-02-01",
                    }]},
                }}},
            }),
            encoding="utf-8",
        )
        return root

    def test_links_only_facts_accepted_before_fold(self):
        with TemporaryDirectory() as directory:
            corpus = self._corpus(Path(directory))
            rows, audit = build_links(
                {
                    "snapshot_id": "prices",
                    "completed_tickers": ["AAA", "BBB", "SPY"],
                },
                [
                    {"ticker": "AAA", "cik": "1"},
                    {"ticker": "BBB", "cik": "2"},
                ],
                corpus,
                [
                    {
                        "fold_id": "F01",
                        "train_start": "2019-01-01",
                        "test_start": "2020-01-01",
                        "test_end": "2020-12-31",
                    },
                    {
                        "fold_id": "F02",
                        "train_start": "2019-01-01",
                        "test_start": "2021-01-01",
                        "test_end": "2021-12-31",
                    },
                ],
            )

        by_key = {(row["ticker"], row["fold_id"]): row for row in rows}
        self.assertEqual(
            by_key[("AAA", "F01")]["status"],
            "NO_FACTS_BEFORE_FOLD",
        )
        self.assertEqual(
            by_key[("AAA", "F02")]["status"],
            "PIT_FACTS_READY",
        )
        self.assertEqual(
            by_key[("BBB", "F02")]["status"],
            "SUBMISSIONS_MISSING",
        )
        self.assertEqual(
            by_key[("SPY", "F02")]["status"],
            "NOT_APPLICABLE_ETF",
        )
        self.assertFalse(audit["research_ready"])
        self.assertEqual(
            collection_queue(rows),
            [{
                "ticker": "BBB",
                "cik": "0000000002",
                "cik_link_status": "UNIQUE_CIK_NAME_CANDIDATE",
                "collection_reason": "SUBMISSIONS_MISSING",
            }],
        )

    def test_ambiguous_ticker_cik_fails_closed(self):
        with TemporaryDirectory() as directory:
            rows, _ = build_links(
                {
                    "snapshot_id": "prices",
                    "completed_tickers": ["AAA"],
                },
                [
                    {"ticker": "AAA", "cik": "1"},
                    {"ticker": "AAA", "cik": "2"},
                ],
                Path(directory),
                [{
                    "fold_id": "F01",
                    "train_start": "2020-01-01",
                    "test_start": "2021-01-01",
                    "test_end": "2021-12-31",
                }],
            )

        self.assertEqual(rows[0]["status"], "AMBIGUOUS_CURRENT_CIK")


if __name__ == "__main__":
    unittest.main()
