import unittest
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory

from herd.sec_master_index import (
    SecMasterIndexError,
    parse_master_index,
    quarter_range,
    resolve_user_agent,
)


class SecMasterIndexTest(unittest.TestCase):
    def test_parses_official_master_index_rows(self):
        content = (
            "Description\nCIK|Company Name|Form Type|Date Filed|Filename\n"
            "----------------------------------------------------------\n"
            "320193|APPLE INC|10-K|2024-11-01|edgar/data/320193/a.txt\n"
        ).encode()
        rows = parse_master_index(content)
        self.assertEqual("0000320193", rows[0]["cik"])
        self.assertEqual("2024-11-01", rows[0]["filed_date"])

    def test_builds_inclusive_quarter_range(self):
        self.assertEqual(
            [(2023, 4), (2024, 1), (2024, 2)],
            quarter_range(date(2023, 12, 1), date(2024, 4, 1)),
        )

    def test_resolves_user_agent_without_exposing_secret(self):
        with TemporaryDirectory() as directory:
            env = Path(directory) / ".env"
            env.write_text("HERDSIGNAL_OWNER_EMAIL=owner@example.com\n")
            self.assertEqual(
                "HerdSignal research owner@example.com", resolve_user_agent(env)
            )

    def test_rejects_missing_contact(self):
        with TemporaryDirectory() as directory:
            env = Path(directory) / ".env"
            env.write_text("SEC_USER_AGENT=anonymous bot\n")
            with self.assertRaises(SecMasterIndexError):
                resolve_user_agent(env)


if __name__ == "__main__":
    unittest.main()
