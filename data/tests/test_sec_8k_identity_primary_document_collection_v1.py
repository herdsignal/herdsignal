import copy
import json

import pytest

from herd.sec_8k_identity_primary_document_collection_v1 import (
    PROTOCOL_PATH,
    Sec8KIdentityCollectionError,
    _normalize_row,
    select_queue,
)


def _protocol() -> dict:
    return json.loads(PROTOCOL_PATH.read_text(encoding="utf-8"))


def test_first_wave_is_locked_and_result_blind() -> None:
    rows = select_queue(_protocol())
    assert len(rows) == 275
    assert {row["priority"] for row in rows} == {"P0_AMBIGUOUS", "P1_TEN_YEAR_WINDOW"}


def test_normalized_source_never_promotes_identity() -> None:
    source = select_queue(_protocol())[0]
    content = b'<ix:nonNumeric name="dei:TradingSymbol">TEST</ix:nonNumeric>'
    row = _normalize_row(source, content)
    assert row["extracted_symbols"] == "TEST"
    assert row["extraction_status"] == "CANDIDATE_FOUND"
    assert row["adjudication_status"] == "PENDING_SOURCE_REVIEW"


def test_locked_queue_hash_is_enforced() -> None:
    protocol = copy.deepcopy(_protocol())
    protocol["locked_inputs"][2]["sha256"] = "0" * 64
    with pytest.raises(Sec8KIdentityCollectionError):
        select_queue(protocol)
