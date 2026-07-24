import sqlite3
from pathlib import Path

from herd.sec_13f_pit_holdings_v1 import (
    _initialize_database,
    _materialize_effective_holdings,
)
from herd.sec_13f_source_review_v1 import (
    _compare,
    _download_with_retry,
    _parse_original_submission,
)


SUBMISSION = b"""<SEC-DOCUMENT>0000000001-24-000001.txt
<SEC-HEADER>
<ACCESSION-NUMBER>0000000001-24-000001
<ACCEPTANCE-DATETIME>20240515163000
CONFORMED SUBMISSION TYPE:	13F-HR
</SEC-HEADER>
<DOCUMENT>
<TYPE>13F-HR
<XML>
<edgarSubmission>
  <headerData><filerInfo><filer><credentials><cik>0000000001</cik></credentials></filer></filerInfo></headerData>
  <formData>
    <coverPage>
      <reportCalendarOrQuarter>03-31-2024</reportCalendarOrQuarter>
      <isAmendment>false</isAmendment>
    </coverPage>
  </formData>
</edgarSubmission>
</XML>
</DOCUMENT>
<DOCUMENT>
<TYPE>INFORMATION TABLE
<XML>
<informationTable>
  <infoTable>
    <nameOfIssuer>ALPHABET INC</nameOfIssuer>
    <titleOfClass>CAP STK CL C</titleOfClass>
    <cusip>02079K107</cusip>
    <value>100</value>
    <shrsOrPrnAmt><sshPrnamt>10</sshPrnamt><sshPrnamtType>SH</sshPrnamtType></shrsOrPrnAmt>
    <investmentDiscretion>SOLE</investmentDiscretion>
    <votingAuthority><Sole>10</Sole><Shared>0</Shared><None>0</None></votingAuthority>
  </infoTable>
  <infoTable>
    <nameOfIssuer>ALPHABET INC</nameOfIssuer>
    <titleOfClass>CAP STK CL C</titleOfClass>
    <cusip>02079K107</cusip>
    <value>50</value>
    <shrsOrPrnAmt><sshPrnamt>5</sshPrnamt><sshPrnamtType>SH</sshPrnamtType></shrsOrPrnAmt>
    <investmentDiscretion>DFND</investmentDiscretion>
    <votingAuthority><Sole>0</Sole><Shared>5</Shared><None>0</None></votingAuthority>
  </infoTable>
</informationTable>
</XML>
</DOCUMENT>
</SEC-DOCUMENT>"""


def test_parse_original_submission_aggregates_selected_security() -> None:
    parsed = _parse_original_submission(SUBMISSION, "02079K107")
    assert parsed["acceptance_datetime"] == "2024-05-15T16:30:00Z"
    assert parsed["manager_cik"] == "0000000001"
    assert parsed["submission_type"] == "13F-HR"
    assert parsed["report_period"] == "2024-03-31"
    assert parsed["reported_value"] == 150
    assert parsed["reported_shares"] == 15
    assert parsed["investment_discretions"] == "DFND|SOLE"
    assert parsed["voting_shared"] == 5


def test_compare_enforces_next_session_and_all_holding_fields() -> None:
    parsed = _parse_original_submission(SUBMISSION, "02079K107")
    row = {
        "manager_cik": "0000000001",
        "report_period": "2024-03-31",
        "submission_type": "13F-HR",
        "amendment_operation": "INITIAL_SNAPSHOT",
        "amendment_type": "",
        "expected_issuer_names": "ALPHABET INC",
        "expected_class_titles": "CAP STK CL C",
        "expected_reported_value": "150",
        "expected_reported_shares": "15",
        "expected_investment_discretions": "DFND|SOLE",
        "expected_voting_sole": "10",
        "expected_voting_shared": "5",
        "expected_voting_none": "0",
        "conservative_availability_date": "2024-05-16",
    }
    assert _compare(row, parsed) == []
    row["expected_reported_shares"] = "16"
    assert _compare(row, parsed) == ["reported_shares"]


def test_compare_allows_safe_delay_and_unknown_cover_conflict() -> None:
    parsed = _parse_original_submission(SUBMISSION, "02079K107")
    parsed["is_amendment"] = False
    parsed["submission_type"] = "13F-HR/A"
    row = {
        "manager_cik": "0000000001",
        "report_period": "2024-03-31",
        "submission_type": "13F-HR/A",
        "amendment_type": "",
        "amendment_operation": "EXCLUDE_UNKNOWN_AMENDMENT_SEMANTICS",
        "expected_issuer_names": "ALPHABET INC",
        "expected_class_titles": "CAP STK CL C",
        "expected_reported_value": "150",
        "expected_reported_shares": "15",
        "expected_investment_discretions": "DFND|SOLE",
        "expected_voting_sole": "10",
        "expected_voting_shared": "5",
        "expected_voting_none": "0",
        "conservative_availability_date": "2024-05-17",
    }
    assert _compare(row, parsed) == []
    row["conservative_availability_date"] = "2024-05-15"
    assert _compare(row, parsed) == ["availability_before_exact_acceptance"]


def test_download_retries_transient_sec_failure(monkeypatch) -> None:
    class Response:
        def __init__(self, status_code: int, content: bytes = b"") -> None:
            self.status_code = status_code
            self.content = content
            self.headers = {}

        def raise_for_status(self) -> None:
            raise RuntimeError(f"HTTP {self.status_code}")

    class Session:
        def __init__(self) -> None:
            self.responses = [Response(503), Response(200, b"ok")]

        def get(self, *_args, **_kwargs):
            return self.responses.pop(0)

    monkeypatch.setattr(
        "herd.sec_13f_source_review_v1.time.sleep",
        lambda _seconds: None,
    )
    assert _download_with_retry(Session(), "https://www.sec.gov/test") == b"ok"


def test_effective_materialization_keeps_unknown_amendment_excluded(
    tmp_path: Path,
) -> None:
    connection = _initialize_database(tmp_path / "fixture.sqlite")
    connection.execute(
        """
        INSERT INTO filings VALUES (
          'a', '0000000001', 'Fixture', '2024-03-31', '2024-05-15',
          '2024-05-16', '13F-HR/A', 1, 1, '',
          'EXCLUDE_UNKNOWN_AMENDMENT_SEMANTICS', 0, '', ''
        )
        """
    )
    connection.execute(
        """
        INSERT INTO holdings VALUES (
          'a', 'GOOG', '0001652044', '02079K107', '', 'ALPHABET INC',
          'CAP STK CL C', 100, 10, 'SOLE', '', 10, 0, 0, 1
        )
        """
    )
    stats = _materialize_effective_holdings(connection)
    assert stats["usable_events"] == 0
    assert connection.execute(
        "SELECT COUNT(*) FROM effective_holdings"
    ).fetchone()[0] == 0
    connection.close()
