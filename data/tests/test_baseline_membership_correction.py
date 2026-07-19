import hashlib
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from herd.baseline_membership_correction import (
    BaselineCorrectionError,
    verify_baseline_corrections,
)


class BaselineMembershipCorrectionTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.evidence_dir = Path(self.temporary.name)
        content = (
            b"<html>S&amp;P 500 constituent HCP Inc. "
            b"Post spin-off HCP will remain in the S&amp;P 500</html>"
        )
        self.digest = hashlib.sha256(content).hexdigest()
        (self.evidence_dir / f"{self.digest}.html").write_bytes(content)
        self.url = "https://press.spglobal.com/2016-10-24-HCP"
        self.claim = {
            "as_of": "2016-07-18",
            "ticker": "HCP",
            "action": "ADD",
            "evidence_date": "2016-10-24",
            "source_url": self.url,
            "required_terms": (
                "S&P 500 constituent HCP Inc.||"
                "Post spin-off HCP will remain in the S&P 500"
            ),
        }
        self.release = {
            "published_date": "2016-10-24",
            "source_url": self.url,
            "status": "DIRECT_OFFICIAL_SOURCE_ARCHIVED",
            "source_sha256": self.digest,
        }

    def tearDown(self):
        self.temporary.cleanup()

    def test_verifies_hash_language_and_no_intervening_event(self):
        rows, audit = verify_baseline_corrections(
            [self.claim], [self.release], self.evidence_dir, []
        )
        self.assertEqual("HCP", rows[0]["ticker"])
        self.assertEqual("DIAGNOSTIC_BASELINE_ONLY", rows[0]["promotion_scope"])
        self.assertEqual(1, audit["verified_corrections"])

    def test_blocks_backcast_across_membership_event(self):
        with self.assertRaises(BaselineCorrectionError):
            verify_baseline_corrections(
                [self.claim],
                [self.release],
                self.evidence_dir,
                [{
                    "effective_date": "2016-09-01",
                    "action": "ADD",
                    "ticker": "HCP",
                }],
            )


if __name__ == "__main__":
    unittest.main()
