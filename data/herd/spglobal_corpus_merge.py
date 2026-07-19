"""여러 시점의 S&P 보도자료 corpus를 URL 기준으로 합쳐 수집 누락을 막는다."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
from pathlib import Path


class SpglobalCorpusMergeError(RuntimeError):
    pass


def merge_corpora(corpus_dirs: list[Path], output_dir: Path) -> dict:
    destination = Path(output_dir)
    if destination.exists():
        raise SpglobalCorpusMergeError("output directory already exists")
    evidence_dir = destination / "evidence"
    evidence_dir.mkdir(parents=True)
    selected = {}
    for source_index, corpus in enumerate(corpus_dirs):
        corpus = Path(corpus)
        with (corpus / "release_index.csv").open(
            encoding="utf-8", newline=""
        ) as handle:
            rows = list(csv.DictReader(handle))
        for row in rows:
            matches = list(
                (corpus / "evidence").glob(f"{row['source_sha256']}.*")
            )
            if len(matches) != 1:
                raise SpglobalCorpusMergeError(
                    f"missing evidence for {row['source_url']}"
                )
            digest = hashlib.sha256(matches[0].read_bytes()).hexdigest()
            if digest != row["source_sha256"]:
                raise SpglobalCorpusMergeError(
                    f"evidence hash mismatch for {row['source_url']}"
                )
            selected[row["source_url"]] = (
                {**row, "source_collection": source_index}, matches[0]
            )
    merged = []
    for url in sorted(selected):
        row, source = selected[url]
        target = evidence_dir / f"{row['source_sha256']}{source.suffix}"
        if not target.exists():
            shutil.copyfile(source, target)
        merged.append(row)
    fields = [
        "published_date", "title", "source_url", "status", "source_sha256",
        "source_collection",
    ]
    index_path = destination / "release_index.csv"
    with index_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(sorted(
            merged, key=lambda row: (row["published_date"], row["source_url"])
        ))
    manifest = {
        "format_version": "herd-spglobal-corpus-merge-v1",
        "source_collections": len(corpus_dirs),
        "release_documents": len(merged),
        "index_sha256": hashlib.sha256(index_path.read_bytes()).hexdigest(),
        "selection_rule": "LATEST_COLLECTION_PER_CANONICAL_URL",
    }
    (destination / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inputs", nargs="+", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(
        merge_corpora(args.inputs, args.output),
        ensure_ascii=False, indent=2,
    ))


if __name__ == "__main__":
    main()
