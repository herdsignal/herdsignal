import json
from pathlib import Path

from herd.leading_information_readiness_v2 import audit, load_protocol


HEADER = "CIK|Company Name|Form Type|Date Filed|Filename\n"


def test_protocol_blocks_owner_cik_and_blanket_insider_sale_direction():
    protocol = load_protocol()
    assert "JOIN_FORM4_REPORTING_OWNER_CIK_TO_ISSUER_CIK" in protocol["forbidden"]
    assert "TREAT_ALL_INSIDER_SALES_AS_BEARISH" in protocol["forbidden"]
    assert protocol["policy"]["price_outcomes_opened"] is False


def test_readiness_fails_closed_without_issuer_xml(monkeypatch, tmp_path: Path):
    master = tmp_path / "master"
    raw = master / "raw"
    raw.mkdir(parents=True)
    (raw / "2020-Q1-master.idx").write_text(
        "header\n" + HEADER
        + "1|OWNER|4|2020-01-02|edgar/data/1/a.txt\n"
        + "2|MANAGER|13F-HR|2020-02-14|edgar/data/2/b.txt\n",
        encoding="latin-1",
    )
    (master / "manifest.json").write_text("{}", encoding="utf-8")
    atomic = tmp_path / "atomic.json"
    pairs = tmp_path / "pairs.json"
    atomic.write_text(json.dumps({"valid_rows_promoted": 500}), encoding="utf-8")
    pairs.write_text(json.dumps({
        "atomic_revision_pairs": 80,
        "distinct_tickers": 24,
        "pair_coverage_gate_passed": False,
    }), encoding="utf-8")
    protocol_path = tmp_path / "protocol.json"
    protocol = load_protocol()
    protocol["master_index"]["path"] = "master"
    guidance = next(
        item for item in protocol["sources"]
        if item["id"] == "SEC_8K_GUIDANCE_REVISION"
    )
    guidance["local_atomic_report"] = "atomic.json"
    guidance["local_pair_report"] = "pairs.json"
    protocol_path.write_text(json.dumps(protocol), encoding="utf-8")
    monkeypatch.setattr("herd.leading_information_readiness_v2.ROOT", tmp_path)
    report = audit(protocol_path)
    assert report["status"] == "NO_NON_PRICE_DIRECTION_SOURCE_READY"
    form4 = next(
        item for item in report["source_decisions"]
        if item["source"] == "SEC_FORM4_INSIDER_TRANSACTIONS"
    )
    assert form4["master_index_filings"] == 1
    assert form4["master_cik_join_allowed"] is False
    assert form4["sell_direction_allowed"] is False
