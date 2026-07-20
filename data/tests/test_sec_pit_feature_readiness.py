import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from herd.sec_pit_feature_readiness import (
    CORE_CONCEPTS,
    audit_feature_readiness,
)


class SecPitFeatureReadinessTest(unittest.TestCase):
    def test_excluded_accession_does_not_restore_unverified_observations(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            raw = root / "raw"
            raw.mkdir()
            (raw / "CIK0000000001-submissions.json").write_text(
                json.dumps({
                    "filings": {"recent": {
                        "accessionNumber": ["verified"],
                        "acceptanceDateTime": ["2020-02-01T12:00:00Z"],
                    }}
                }),
                encoding="utf-8",
            )
            facts = {}
            for aliases in CORE_CONCEPTS.values():
                concept = sorted(aliases)[0]
                facts[concept] = {
                    "label": concept,
                    "units": {"USD": [{
                        "val": 1,
                        "accn": "verified",
                        "form": "10-K",
                        "filed": "2020-02-01",
                        "end": "2019-12-31",
                    }, {
                        "val": 2,
                        "accn": "missing",
                        "form": "10-K",
                        "filed": "2020-02-02",
                        "end": "2019-12-31",
                    }]},
                }
            (raw / "CIK0000000001-companyfacts.json").write_text(
                json.dumps({
                    "cik": 1,
                    "entityName": "AAA",
                    "facts": {"us-gaap": facts},
                }),
                encoding="utf-8",
            )
            rows, audit = audit_feature_readiness(
                [{
                    "ticker": "AAA",
                    "asset_type": "EQUITY",
                    "cik": "0000000001",
                    "fold_id": "F01",
                    "as_of": "2020-08-01",
                    "status": "MISSING_ACCEPTANCE_LINKS",
                }],
                [root],
            )

        self.assertEqual(rows[0]["strict_fact_rows"], len(CORE_CONCEPTS))
        self.assertEqual(
            rows[0]["feature_status"],
            "BUSINESS_GUARD_READY_WITH_DISCLOSED_EXCLUSIONS",
        )
        self.assertTrue(audit["guard_research_ready"])
        self.assertFalse(audit["strict_corpus_ready"])

