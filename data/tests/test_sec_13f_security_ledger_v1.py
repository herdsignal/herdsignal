import csv
import io
import zipfile
from pathlib import Path

from herd.sec_13f_security_ledger_v1 import (
    _class_letter,
    _dominant_owner,
    _scan_observations,
    _ticker_for,
    is_valid_cusip,
    is_primary_equity_title,
    issuer_token_signature,
    normalize_issuer_name,
)


def _archive(path: Path) -> None:
    submission = (
        "ACCESSION_NUMBER\tFILING_DATE\tSUBMISSIONTYPE\tCIK\tPERIODOFREPORT\n"
        "0000000001-20-000001\t14-FEB-2020\t13F-HR\t0000000001\t31-DEC-2019\n"
    )
    infotable = (
        "ACCESSION_NUMBER\tINFOTABLE_SK\tNAMEOFISSUER\tTITLEOFCLASS\tCUSIP"
        "\tFIGI\tVALUE\tSSHPRNAMT\tSSHPRNAMTTYPE\tPUTCALL"
        "\tINVESTMENTDISCRETION\tOTHERMANAGER\tVOTING_AUTH_SOLE"
        "\tVOTING_AUTH_SHARED\tVOTING_AUTH_NONE\n"
        "0000000001-20-000001\t1\tALPHABET INC\tCAP STK CL A\t02079K305"
        "\tBBG009S39JY5\t100\t10\tSH\t\tSOLE\t\t10\t0\t0\n"
        "0000000001-20-000001\t2\tOLD ALPHABET NAME\tCAP STK CL A\t02079K305"
        "\t\t100\t10\tSH\t\tSOLE\t\t10\t0\t0\n"
        "0000000001-20-000001\t3\tALPHABET INC\tCAP STK CL C\t02079K107"
        "\t\t100\t10\tSH\t\tSOLE\t\t10\t0\t0\n"
        "0000000001-20-000001\t4\tALPHABET INC\tCALL\t02079K305"
        "\t\t100\t10\tSH\tCALL\tSOLE\t\t10\t0\t0\n"
    )
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("SUBMISSION.tsv", submission)
        archive.writestr("INFOTABLE.tsv", infotable)


def test_name_normalization_handles_common_sec_abbreviations() -> None:
    assert normalize_issuer_name("The Honeywell International, Inc.") == (
        normalize_issuer_name("HONEYWELL INTL INC")
    )
    assert normalize_issuer_name("Estée Lauder Companies (The)") == (
        normalize_issuer_name("ESTEE LAUDER COS")
    )
    assert issuer_token_signature("HUNT J B TRANSPORT SERVICES INC") == (
        issuer_token_signature("JB HUNT TRANSPORTATION SERVICES INC")
    )
    assert normalize_issuer_name("APPLIED MATERIALS INC /DE/") == (
        normalize_issuer_name("APPLIED MATLS INC")
    )


def test_cusip_check_digit_rejects_placeholders_and_typos() -> None:
    assert is_valid_cusip("02079K305")
    assert is_valid_cusip("038222105")
    assert not is_valid_cusip("000000000")
    assert not is_valid_cusip("02079K304")


def test_primary_equity_title_excludes_other_security_types() -> None:
    assert is_primary_equity_title("COM")
    assert is_primary_equity_title("CAP STK CL A")
    assert is_primary_equity_title("CL C")
    assert is_primary_equity_title("SH BEN INT NEW")
    assert not is_primary_equity_title("MUTUAL FUNDS - EQUITY")
    assert not is_primary_equity_title("CONVERTIBLE PREFERRED STOCK")
    assert not is_primary_equity_title("NOTE 5.25%")


def test_identifier_conflict_requires_clear_dominance() -> None:
    assert _dominant_owner({"issuer": 1_000, "typo": 3}) == "issuer"
    assert _dominant_owner({"left": 100, "right": 20}) == ""


def test_share_classes_are_not_duplicated() -> None:
    tickers = {"0001652044": {"GOOG", "GOOGL"}}
    assert _class_letter("CAP STK CL A") == "A"
    assert _ticker_for("0001652044", "CAP STK CL A", tickers)[0] == "GOOGL"
    assert _ticker_for("0001652044", "CAP STK CL C", tickers)[0] == "GOOG"
    assert _ticker_for(
        "0001652044", "CAP STK CL C", tickers, "02079K305"
    )[0] == "GOOGL"
    assert _ticker_for("0001652044", "COM", tickers)[0] == ""


def test_scan_filters_options_and_preserves_classes(tmp_path: Path) -> None:
    path = tmp_path / "fixture.zip"
    _archive(path)
    aliases = {normalize_issuer_name("ALPHABET INC"): "0001652044"}
    observations, diagnostics = _scan_observations(
        [path],
        aliases,
        {},
        {},
        {"0001652044": {"GOOG", "GOOGL"}},
    )
    assert diagnostics == {}
    assert {row.ticker for row in observations.values()} == {"GOOG", "GOOGL"}
    assert sum(row.rows for row in observations.values()) == 2
