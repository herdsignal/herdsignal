import io
import sqlite3
import zipfile
from datetime import date
from pathlib import Path

from herd.sec_13f_pit_holdings_v1 import (
    _amendment_semantics,
    _create_effective_indexes,
    _create_indexes,
    _initialize_database,
    _insert_archive,
    _materialize_effective_holdings,
    next_market_session,
)


def _fixture(path: Path) -> None:
    submission = (
        "ACCESSION_NUMBER\tFILING_DATE\tSUBMISSIONTYPE\tCIK\tPERIODOFREPORT\n"
        "0000000001-20-000001\t14-FEB-2020\t13F-HR\t0000000001\t31-DEC-2019\n"
        "0000000001-20-000002\t17-FEB-2020\t13F-HR/A\t0000000001\t31-DEC-2019\n"
    )
    cover = (
        "ACCESSION_NUMBER\tREPORTCALENDARORQUARTER\tISAMENDMENT\tAMENDMENTNO"
        "\tAMENDMENTTYPE\tCONFDENIEDEXPIRED\tDATEDENIEDEXPIRED\tDATEREPORTED"
        "\tREASONFORNONCONFIDENTIALITY\tFILINGMANAGER_NAME"
        "\tFILINGMANAGER_STREET1\tFILINGMANAGER_STREET2\tFILINGMANAGER_CITY"
        "\tFILINGMANAGER_STATEORCOUNTRY\tFILINGMANAGER_ZIPCODE\tREPORTTYPE"
        "\tFORM13FFILENUMBER\tCRDNUMBER\tSECFILENUMBER"
        "\tPROVIDEINFOFORINSTRUCTION5\tADDITIONALINFORMATION\n"
        "0000000001-20-000001\t31-DEC-2019\t\t\t\t\t\t\t\tFixture"
        "\t\t\t\t\t\t13F HOLDINGS REPORT\t028-00001\t\t\tN\t\n"
        "0000000001-20-000002\t31-DEC-2019\tY\t1\tNEW HOLDINGS\t\t\t\t"
        "\tFixture\t\t\t\t\t\t13F HOLDINGS REPORT\t028-00001\t\t\tN\t\n"
    )
    info_header = (
        "ACCESSION_NUMBER\tINFOTABLE_SK\tNAMEOFISSUER\tTITLEOFCLASS\tCUSIP"
        "\tFIGI\tVALUE\tSSHPRNAMT\tSSHPRNAMTTYPE\tPUTCALL"
        "\tINVESTMENTDISCRETION\tOTHERMANAGER\tVOTING_AUTH_SOLE"
        "\tVOTING_AUTH_SHARED\tVOTING_AUTH_NONE\n"
    )
    info = info_header + (
        "0000000001-20-000001\t1\tALPHABET INC\tCAP STK CL C\t02079K107"
        "\t\t100\t10\tSH\t\tSOLE\t\t10\t0\t0\n"
        "0000000001-20-000001\t2\tALPHABET INC\tCAP STK CL C\t02079K107"
        "\t\t50\t5\tSH\t\tDEFINED\t1\t0\t5\t0\n"
        "0000000001-20-000002\t3\tALPHABET INC\tCAP STK CL C\t02079K107"
        "\t\t20\t2\tSH\t\tSOLE\t\t2\t0\t0\n"
        "0000000001-20-000002\t4\tALPHABET INC\tCALL\t02079K107"
        "\t\t20\t2\tSH\tCALL\tSOLE\t\t2\t0\t0\n"
    )
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("SUBMISSION.tsv", submission)
        archive.writestr("COVERPAGE.tsv", cover)
        archive.writestr("INFOTABLE.tsv", info)


def test_next_market_session_is_conservative_across_weekend_and_holiday() -> None:
    assert next_market_session(date(2020, 2, 14)) == date(2020, 2, 18)
    assert next_market_session(date(2024, 7, 3)) == date(2024, 7, 5)
    assert next_market_session(date(2018, 12, 4)) == date(2018, 12, 6)
    assert next_market_session(date(2025, 1, 8)) == date(2025, 1, 10)


def test_amendment_semantics_fail_closed() -> None:
    assert _amendment_semantics("13F-HR", {"is_amendment": ""}) == (
        False,
        "",
        "INITIAL_SNAPSHOT",
        True,
    )
    assert _amendment_semantics(
        "13F-HR/A",
        {"is_amendment": "Y", "amendment_type": "NEW HOLDINGS"},
    )[2:] == ("ADD_NEW_HOLDINGS_FROM_AVAILABILITY", True)
    assert _amendment_semantics(
        "13F-HR/A",
        {"is_amendment": "Y", "amendment_type": ""},
    )[2:] == ("EXCLUDE_UNKNOWN_AMENDMENT_SEMANTICS", False)


def test_archive_ingestion_aggregates_rows_and_preserves_amendment(
    tmp_path: Path,
) -> None:
    archive = tmp_path / "fixture.zip"
    database = tmp_path / "fixture.sqlite"
    _fixture(archive)
    connection = _initialize_database(database)
    filings, holdings = _insert_archive(
        connection,
        archive,
        {
            "02079K107": {
                "ticker": "GOOG",
                "issuer_cik": "0001652044",
            }
        },
    )
    assert filings == 2
    assert holdings == 2
    original = connection.execute(
        """
        SELECT reported_value, reported_shares, source_rows
        FROM holdings WHERE accession_number='0000000001-20-000001'
        """
    ).fetchone()
    assert original == (150, 15, 2)
    amendment = connection.execute(
        """
        SELECT amendment_type, amendment_operation, availability_date
        FROM filings WHERE accession_number='0000000001-20-000002'
        """
    ).fetchone()
    assert amendment == (
        "NEW HOLDINGS",
        "ADD_NEW_HOLDINGS_FROM_AVAILABILITY",
        "2020-02-18",
    )
    materialization = _materialize_effective_holdings(connection)
    effective = connection.execute(
        """
        SELECT reported_value, reported_shares, source_accession_number
        FROM effective_holdings
        WHERE event_accession_number='0000000001-20-000002'
        """
    ).fetchone()
    assert effective == (150, 15, "0000000001-20-000001")
    assert materialization["new_holdings_overlap_rows_ignored"] == 1
    _create_indexes(connection)
    assert connection.execute(
        """
        SELECT COUNT(*) FROM sqlite_master
        WHERE type='index' AND name='effective_holdings_asof_idx'
        """
    ).fetchone()[0] == 0
    _create_effective_indexes(connection)
    assert connection.execute(
        """
        SELECT COUNT(*) FROM sqlite_master
        WHERE type='index' AND name='effective_holdings_asof_idx'
        """
    ).fetchone()[0] == 1
    connection.close()
