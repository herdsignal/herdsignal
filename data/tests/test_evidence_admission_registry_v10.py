import json

import pytest

from herd.evidence_admission_registry_v10 import (
    CONTRACT_PATH,
    EvidenceAdmissionV10Error,
    build_report,
)


def test_registry_preserves_all_rejections_and_blocks_combination(tmp_path):
    report = build_report(tmp_path / "report.json")
    assert report["adjudicated_hypotheses"] == 10
    assert report["admitted_families"] == []
    assert report["combination_allowed"] is False
    assert report["operational_action_ratio"] == 0.0


def test_registry_rejects_modified_input_hash(monkeypatch, tmp_path):
    contract = json.loads(CONTRACT_PATH.read_text())
    contract["inputs"][0]["sha256"] = "0" * 64
    changed = tmp_path / "contract.json"
    changed.write_text(json.dumps(contract))
    monkeypatch.setattr(
        "herd.evidence_admission_registry_v10.CONTRACT_PATH",
        changed,
    )
    with pytest.raises(EvidenceAdmissionV10Error):
        build_report(tmp_path / "report.json")
