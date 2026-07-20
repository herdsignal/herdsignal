import unittest

from herd.share_class_normalization import (
    ShareClassNormalizationError,
    normalize_share_class_events,
    split_share_classes,
)


class ShareClassNormalizationTest(unittest.TestCase):
    def test_splits_official_multi_class_expression(self):
        rows, audit = normalize_share_class_events([{
            "effective_date": "2022-06-21",
            "action": "REMOVE",
            "ticker": "UA/UAA",
            "company_name": "Under Armour",
        }])
        self.assertEqual(["UA", "UAA"], [row["ticker"] for row in rows])
        self.assertTrue(all(
            row["source_ticker_expression"] == "UA/UAA" for row in rows
        ))
        self.assertEqual(1, audit["expanded_source_events"])

    def test_rejects_ambiguous_or_duplicate_expression(self):
        for value in ("UA/", "UA/UA", "UA//UAA"):
            with self.subTest(value=value):
                with self.assertRaises(ShareClassNormalizationError):
                    split_share_classes(value)

