"""14년 가격·ETF·SEC PIT·장기 fold 통합 입력 manifest를 검증한다."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import Any

from herd.public_research_contract import load_public_research_contract


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = Path(__file__).with_name("research_input_manifest_v2.json")
MANIFEST_VERSION = "HERD_RESEARCH_INPUT_V2"


class ResearchInputManifestV2Error(ValueError):
    """고정 입력이 누락되거나 변조됐을 때 발생한다."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _pinned(spec: dict[str, Any], key: str = "path") -> Path:
    path = (REPOSITORY_ROOT / spec[key]).resolve()
    if not path.is_relative_to(REPOSITORY_ROOT) or not path.is_file():
        raise ResearchInputManifestV2Error(f"missing pinned input: {spec[key]}")
    hash_key = "manifest_sha256" if key == "manifest_path" else "sha256"
    if _sha256(path) != spec[hash_key]:
        raise ResearchInputManifestV2Error(f"hash mismatch: {spec[key]}")
    return path


def validate_research_input_manifest_v2(manifest: dict[str, Any]) -> dict[str, Any]:
    load_public_research_contract()
    if (
        manifest.get("manifest_version") != MANIFEST_VERSION
        or manifest.get("status") != "PINNED_PUBLIC_RESEARCH_ONLY"
    ):
        raise ResearchInputManifestV2Error("V2 manifest is not locked")

    period = manifest["research_period"]
    price_spec = manifest["price_snapshot"]
    price = json.loads(_pinned(price_spec, "manifest_path").read_text(encoding="utf-8"))
    completed = set(price.get("completed_tickers", []))
    required_etfs = set(price_spec["required_market_etfs"] + price_spec["required_sector_etfs"])
    files = price.get("files", {})
    columns = set(price_spec["execution_columns"] + price_spec["action_columns"])
    columns.add(price_spec["price_column"])
    if (
        price.get("snapshot_id") != price_spec["snapshot_id"]
        or len(completed) != price_spec["required_tickers"]
        or not required_etfs.issubset(completed)
        or price.get("failures")
        or any(item.get("start") < period["start"] or item.get("end") != period["end"] for item in files.values())
        or price.get("source", {}).get("auto_adjust") is not False
        or price.get("source", {}).get("actions") is not True
    ):
        raise ResearchInputManifestV2Error("price snapshot violates V2 contract")

    sample_path = _pinned(price_spec, "manifest_path").parent / files["SPY"]["path"]
    import gzip
    with gzip.open(sample_path, "rt", encoding="utf-8", newline="") as stream:
        header = set(next(csv.reader(stream)))
    if not columns.issubset(header):
        raise ResearchInputManifestV2Error("price snapshot columns are incomplete")

    fold_spec = manifest["oos_folds"]
    folds = json.loads(_pinned(fold_spec, "manifest_path").read_text(encoding="utf-8"))
    if (
        folds.get("protocol_version") != fold_spec["protocol_version"]
        or folds["files"]["PRICE_TIMING_6M"]["fold_count"] < fold_spec["price_lane_minimum_folds"]
        or folds["files"]["BUSINESS_STATE_12M"]["fold_count"] < fold_spec["business_lane_minimum_folds"]
    ):
        raise ResearchInputManifestV2Error("long OOS folds are insufficient")

    sec_ciks = 0
    for specification in manifest["sec_corpora"]:
        sec = json.loads(_pinned(specification, "manifest_path").read_text(encoding="utf-8"))
        if (
            sec.get("start_date") != period["start"]
            or sec.get("end_date") != period["end"]
            or sec.get("companyfacts_unavailable") != 0
            or sec.get("unavailable_documents")
            or sec.get("user_agent_configured") is not True
        ):
            raise ResearchInputManifestV2Error("SEC corpus is incomplete")
        sec_ciks += int(sec.get("ciks", 0))

    _pinned(manifest["cik_periods"])
    fold_link_path = _pinned(manifest["sec_fold_link"])
    with fold_link_path.open(encoding="utf-8", newline="") as stream:
        fold_rows = [
            row for row in csv.DictReader(stream) if row["asset_type"] == "EQUITY"
        ]
    ready = sum(row["status"] == "PIT_FACTS_READY" for row in fold_rows)
    if len(fold_rows) != manifest["sec_fold_link"]["required_total_rows"] \
            or ready != manifest["sec_fold_link"]["required_ready_rows"]:
        raise ResearchInputManifestV2Error("SEC/fold readiness count changed")

    constituent = json.loads(_pinned(manifest["constituent_evidence"]).read_text(encoding="utf-8"))
    if constituent.get("source_policy", {}).get("free_public_reconstruction_role") \
            != "MODEL_ELIMINATION_AND_SENSITIVITY_ONLY":
        raise ResearchInputManifestV2Error("constituent evidence use is unsafe")

    return {
        "manifest_version": MANIFEST_VERSION,
        "price_tickers": len(completed),
        "benchmark_etfs": len(required_etfs),
        "sec_ciks": sec_ciks,
        "sec_fold_rows_ready": ready,
        "sec_fold_rows_total": len(fold_rows),
        "survivorship_safe": False,
        "promotion_allowed": False,
    }


def load_research_input_manifest_v2(path: Path = MANIFEST_PATH) -> tuple[dict, dict]:
    manifest = json.loads(path.read_text(encoding="utf-8"))
    return manifest, validate_research_input_manifest_v2(manifest)
