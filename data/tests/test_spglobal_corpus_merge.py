import csv
import hashlib
import tempfile
import unittest
from pathlib import Path

from herd.spglobal_corpus_merge import merge_corpora


class SpglobalCorpusMergeTest(unittest.TestCase):
    def _corpus(self, root, name, releases):
        corpus = root / name
        evidence = corpus / "evidence"
        evidence.mkdir(parents=True)
        rows = []
        for published, url, content in releases:
            digest = hashlib.sha256(content).hexdigest()
            (evidence / f"{digest}.html").write_bytes(content)
            rows.append({
                "published_date": published,
                "title": url,
                "source_url": url,
                "status": "REQUIRES_EVENT_EXTRACTION",
                "source_sha256": digest,
            })
        with (corpus / "release_index.csv").open(
            "w", encoding="utf-8", newline=""
        ) as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
        return corpus

    def test_preserves_release_missing_from_latest_collection(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first = self._corpus(root, "first", [
                ("2020-01-01", "https://example/a", b"a"),
                ("2020-01-02", "https://example/b", b"old-b"),
            ])
            second = self._corpus(root, "second", [
                ("2020-01-02", "https://example/b", b"new-b"),
            ])

            audit = merge_corpora([first, second], root / "merged")

            self.assertEqual(2, audit["release_documents"])
            with (root / "merged" / "release_index.csv").open(
                encoding="utf-8", newline=""
            ) as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(
                {"https://example/a", "https://example/b"},
                {row["source_url"] for row in rows},
            )
            latest = next(
                row for row in rows if row["source_url"] == "https://example/b"
            )
            self.assertEqual("1", latest["source_collection"])


if __name__ == "__main__":
    unittest.main()
