import copy
import json

import pytest

from herd.sec_8k_modern_exception_promotion_v3 import PROTOCOL, Sec8KModernExceptionPromotionV3Error, build


def test_reviewed_modern_exception_improves_coverage_without_interval_inference() -> None:
    promotions, corpus, promotion_report, corpus_report = build()
    bax = next(row for row in corpus if row["accession_number"] == "0001193125-20-035710")
    assert len(promotions) == 116
    assert bax["canonical_symbol_at_filing"] == "BAX"
    assert bax["identity_status"] == "SEC_PRIMARY_DOCUMENT_REVIEWED"
    assert promotion_report["open_ended_intervals_inferred"] == 0
    assert corpus_report["mapped_events"] == 301
    assert corpus_report["unmapped_events"] == 646
    assert corpus_report["operational_action_ratio"] == 0.0


def test_promotion_rejects_parser_change_authority(tmp_path) -> None:
    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    changed = copy.deepcopy(protocol)
    changed["authority"]["parser_changed"] = True
    path = tmp_path / "protocol.json"
    path.write_text(json.dumps(changed), encoding="utf-8")
    with pytest.raises(Sec8KModernExceptionPromotionV3Error, match="fail-closed"):
        build(path)
