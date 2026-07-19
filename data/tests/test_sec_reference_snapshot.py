import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from herd.sec_reference_snapshot import (
    SecReferenceError,
    create_mapping_snapshot,
    extract_submission_evidence,
    normalize_ticker_mapping,
)


class SecReferenceSnapshotTest(unittest.TestCase):
    def test_current_mapping_is_not_treated_as_point_in_time(self):
        payload = {
            "fields": ["cik", "name", "ticker", "exchange"],
            "data": [[320193, "Apple Inc.", "AAPL", "Nasdaq"]],
        }
        rows = normalize_ticker_mapping(payload)
        self.assertEqual(rows[0]["cik"], "0000320193")
        self.assertEqual(rows[0]["validity"], "CURRENT_ASSOCIATION_ONLY")

    def test_extracts_delisting_and_merger_candidates_without_overclassification(self):
        payload = {
            "cik": "320193",
            "name": "Test Inc",
            "formerNames": [{"name": "Old Test", "from": "2010-01-01", "to": "2015-01-01"}],
            "filings": {
                "recent": {
                    "accessionNumber": ["1", "2", "3"],
                    "filingDate": ["2024-01-01"] * 3,
                    "acceptanceDateTime": ["2024-01-01T12:00:00.000Z"] * 3,
                    "form": ["25-NSE", "8-K", "10-Q"],
                    "primaryDocument": ["a.htm", "b.htm", "c.htm"],
                    "items": ["", "2.01", ""],
                }
            },
        }
        names, evidence = extract_submission_evidence(payload)
        self.assertEqual(len(names), 1)
        self.assertEqual([row["evidence_type"] for row in evidence],
                         ["DELISTING_NOTICE", "CORPORATE_ACTION_CANDIDATE"])
        self.assertTrue(all(row["classification_status"] == "REQUIRES_DOCUMENT_REVIEW" for row in evidence))

    def test_rejects_unexpected_sec_schema(self):
        with self.assertRaises(SecReferenceError):
            normalize_ticker_mapping({"fields": ["ticker"], "data": []})

    def test_creates_fail_closed_mapping_snapshot(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.json"
            source.write_text(
                '{"fields":["cik","name","ticker","exchange"],'
                '"data":[[320193,"Apple Inc.","AAPL","Nasdaq"]]}',
                encoding="utf-8",
            )
            snapshot = create_mapping_snapshot("sec-001", source, root=root / "out")
            import json
            manifest = json.loads((snapshot / "manifest.json").read_text())
            self.assertFalse(manifest["point_in_time_ready"])


if __name__ == "__main__":
    unittest.main()
