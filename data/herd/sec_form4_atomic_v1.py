"""해시 고정 Form 4 XML을 각주 보존 atomic 거래 원장으로 변환한다."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

import pandas as pd

from herd.sec_guidance_table_review_gate_v1 import wilson_lower


CLASS_BY_CODE = {
    "P": "OPEN_MARKET_OR_PRIVATE_PURCHASE",
    "S": "OPEN_MARKET_OR_PRIVATE_SALE",
    "A": "RULE16B3_GRANT_AWARD_OR_ACQUISITION",
    "D": "RULE16B3_DISPOSITION_TO_ISSUER",
    "I": "RULE16B3_DISCRETIONARY_TRANSACTION",
    "F": "TAX_OR_EXERCISE_WITHHOLDING",
    "C": "DERIVATIVE_CONVERSION",
    "E": "SHORT_DERIVATIVE_EXPIRATION",
    "H": "LONG_DERIVATIVE_EXPIRATION_OR_CANCELLATION",
    "M": "RULE16B3_DERIVATIVE_EXERCISE_OR_CONVERSION",
    "O": "OUT_OF_MONEY_DERIVATIVE_EXERCISE",
    "X": "IN_OR_AT_MONEY_DERIVATIVE_EXERCISE",
    "K": "EQUITY_SWAP_OR_SIMILAR_INSTRUMENT",
    "G": "BONA_FIDE_GIFT",
    "W": "WILL_OR_DESCENT_DISTRIBUTION",
    "J": "OTHER_REQUIRES_DESCRIPTION",
    "L": "SMALL_ACQUISITION_RULE16A6",
    "U": "CHANGE_OF_CONTROL_TENDER_DISPOSITION",
    "V": "VOLUNTARY_EARLY_REPORT",
    "Z": "VOTING_TRUST_DEPOSIT_OR_WITHDRAWAL",
}
GROUP_BY_CODE = {
    "P": "PURCHASE",
    "S": "SALE",
    "A": "COMPENSATION",
    "D": "COMPENSATION_RELATED_DISPOSITION",
    "I": "BENEFIT_PLAN_TRANSACTION",
    "F": "TAX_OR_EXERCISE_WITHHOLDING",
    "C": "DERIVATIVE",
    "E": "DERIVATIVE",
    "H": "DERIVATIVE",
    "M": "DERIVATIVE",
    "O": "DERIVATIVE",
    "X": "DERIVATIVE",
    "K": "DERIVATIVE",
    "G": "GIFT_OR_ESTATE",
    "W": "GIFT_OR_ESTATE",
    "J": "OTHER",
    "L": "OTHER_EXEMPT_ACQUISITION",
    "U": "CORPORATE_ACTION",
    "V": "OTHER",
    "Z": "OTHER",
}
REQUIRED_ACCURACY_FIELDS = (
    "transactionCode", "transactionShares", "transactionPricePerShare",
    "sharesOwnedFollowingTransaction", "directOrIndirectOwnership",
)


class Form4ParseError(RuntimeError):
    pass


class IssuerCikMismatch(Form4ParseError):
    pass


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _tag(element: ET.Element) -> str:
    return element.tag.rsplit("}", 1)[-1]


def _child(element: ET.Element | None, name: str) -> ET.Element | None:
    if element is None:
        return None
    return next((node for node in element if _tag(node) == name), None)


def _path(element: ET.Element | None, *names: str) -> ET.Element | None:
    current = element
    for name in names:
        current = _child(current, name)
        if current is None:
            return None
    return current


def _text(element: ET.Element | None, *names: str) -> str | None:
    node = _path(element, *names) if names else element
    if node is None:
        return None
    value = "".join(node.itertext()).strip()
    return value or None


def _value(element: ET.Element | None, *names: str) -> str | None:
    node = _path(element, *names)
    return _text(_child(node, "value")) if node is not None else None


def _bool_text(value: str | None) -> bool | None:
    if value is None:
        return None
    lowered = value.strip().lower()
    if lowered in {"1", "true", "yes"}:
        return True
    if lowered in {"0", "false", "no"}:
        return False
    return None


def _explicit_ten_b5_transaction_plan(text: str) -> bool:
    if not re.search(r"\b10b5-?1\b", text, flags=re.IGNORECASE):
        return False
    normalized = re.sub(r"\[F\d+\]\s*", "", text)
    patterns = (
        r"(?:^|\n)\s*transactions?\s+(?:was\s+|were\s+)?(?:made\s+|effected\s+|executed\s+)?(?:pursuant\s+to|under)\b.{0,80}\b10b5-?1\b",
        r"(?:this|the)\s+transactions?\b.{0,180}\bpursuant\s+to\b.{0,80}\b10b5-?1\b",
        r"\btransactions?\s+(?:reported|made|effected|executed)\b.{0,180}\b10b5-?1\b",
        r"\b(?:sales?|purchases?|exercises?)\s+reported\b.{0,180}\b10b5-?1\b",
        r"\bsales?\b.{0,400}\bpursuant\s+to\b.{0,120}\b10b5-?1\b",
        r"\boptions?\s+were\s+exercised\b.{0,180}\b10b5-?1\b",
        r"\bsale\s+of\s+shares\b.{0,180}\b10b5-?1\b",
        r"(?:^|\n)\s*pursuant\s+to\b.{0,80}\b10b5-?1\b",
    )
    return any(
        re.search(pattern, normalized, flags=re.IGNORECASE | re.DOTALL)
        for pattern in patterns
    )


def _footnote_ids(element: ET.Element) -> list[str]:
    return sorted({
        ref.attrib.get("id", "").strip()
        for ref in element.iter()
        if _tag(ref) == "footnoteId" and ref.attrib.get("id", "").strip()
    })


def _ten_b5_status(root: ET.Element, referenced: str) -> tuple[str, str | None]:
    for node in root.iter():
        if _tag(node) in {"aff10b5One", "isTenB5One", "tenB5One"}:
            raw = _text(node)
            checked = _bool_text(raw)
            if checked is not None:
                return ("TRUE" if checked else "FALSE"), raw
    if _explicit_ten_b5_transaction_plan(referenced):
        return "TRUE", None
    return "UNKNOWN", None


def parse_document(content: bytes, metadata: dict) -> list[dict]:
    try:
        root = ET.fromstring(content)
    except ET.ParseError as error:
        raise Form4ParseError("invalid ownership XML") from error
    issuer = next((node for node in root.iter() if _tag(node) == "issuer"), None)
    issuer_cik_raw = _text(issuer, "issuerCik")
    if not issuer_cik_raw:
        raise Form4ParseError("issuerCik missing")
    issuer_cik = f"{int(issuer_cik_raw):010d}"
    if issuer_cik != metadata["issuer_cik"]:
        raise IssuerCikMismatch(
            f"issuerCik mismatch: {issuer_cik} != {metadata['issuer_cik']}"
        )
    footnotes = {
        node.attrib.get("id", ""): _text(node) or ""
        for node in root.iter() if _tag(node) == "footnote"
    }
    owners = []
    for owner in (node for node in root.iter() if _tag(node) == "reportingOwner"):
        owner_id = _child(owner, "reportingOwnerId")
        relationship = _child(owner, "reportingOwnerRelationship")
        owners.append({
            "rptOwnerCik": _text(owner_id, "rptOwnerCik"),
            "rptOwnerName": _text(owner_id, "rptOwnerName"),
            "isDirector": _text(relationship, "isDirector"),
            "isOfficer": _text(relationship, "isOfficer"),
            "isTenPercentOwner": _text(relationship, "isTenPercentOwner"),
            "isOther": _text(relationship, "isOther"),
            "officerTitle": _text(relationship, "officerTitle"),
        })
    document_type = _text(root, "documentType")
    period = _text(root, "periodOfReport")
    transactions = [
        (node, False) for node in root.iter()
        if _tag(node) == "nonDerivativeTransaction"
    ] + [
        (node, True) for node in root.iter()
        if _tag(node) == "derivativeTransaction"
    ]
    rows = []
    for index, (transaction, is_derivative) in enumerate(transactions):
        amounts = _child(transaction, "transactionAmounts")
        post = _child(transaction, "postTransactionAmounts")
        ownership = _child(transaction, "ownershipNature")
        coding = _child(transaction, "transactionCoding")
        ids = _footnote_ids(transaction)
        referenced = "\n".join(
            f"[{identifier}] {footnotes.get(identifier, '')}" for identifier in ids
        )
        ten_b5, ten_b5_raw = _ten_b5_status(root, referenced)
        code = _text(coding, "transactionCode")
        atomic_id = hashlib.sha256(
            f"{metadata['issuer_cik']}|{metadata['accession_number']}|{index}".encode()
        ).hexdigest()
        rows.append({
            "atomicTransactionId": atomic_id,
            "transactionIndex": index,
            "issuerCik": issuer_cik,
            "issuerName": _text(issuer, "issuerName"),
            "issuerTradingSymbol": _text(issuer, "issuerTradingSymbol"),
            "candidateTickers": metadata["candidate_tickers"],
            "accessionNumber": metadata["accession_number"],
            "filingDate": metadata["filing_date"],
            "acceptanceDatetime": metadata["acceptance_datetime"],
            "periodOfReport": period,
            "documentType": document_type,
            "reportingOwner": json.dumps(owners, ensure_ascii=False, sort_keys=True),
            "isDirector": "|".join(str(owner["isDirector"] or "") for owner in owners),
            "isOfficer": "|".join(str(owner["isOfficer"] or "") for owner in owners),
            "isTenPercentOwner": "|".join(
                str(owner["isTenPercentOwner"] or "") for owner in owners
            ),
            "officerTitle": "|".join(str(owner["officerTitle"] or "") for owner in owners),
            "securityTitle": _value(transaction, "securityTitle"),
            "transactionDate": _value(transaction, "transactionDate"),
            "transactionCode": code,
            "economicClass": CLASS_BY_CODE.get(
                code or "", "UNKNOWN_TRANSACTION_CODE"
            ),
            "economicGroup": GROUP_BY_CODE.get(
                code or "", "UNKNOWN_TRANSACTION_CODE"
            ),
            "equitySwapInvolved": _text(coding, "equitySwapInvolved"),
            "transactionShares": _value(amounts, "transactionShares"),
            "transactionPricePerShare": _value(
                amounts, "transactionPricePerShare"
            ),
            "acquiredDisposedCode": _value(amounts, "transactionAcquiredDisposedCode"),
            "sharesOwnedFollowingTransaction": _value(
                post, "sharesOwnedFollowingTransaction"
            ),
            "directOrIndirectOwnership": _value(
                ownership, "directOrIndirectOwnership"
            ),
            "natureOfOwnership": _value(ownership, "natureOfOwnership"),
            "footnoteIds": "|".join(ids),
            "footnoteText": referenced,
            "rawFootnotes": json.dumps(footnotes, ensure_ascii=False, sort_keys=True),
            "isDerivative": is_derivative,
            "tenB5OneCheckbox": ten_b5_raw,
            "tenB5OneStatus": ten_b5,
            "sourceSha256": metadata["source_sha256"],
        })
    return rows


def build(
    corpus: Path,
    atomic_output: Path,
    review_output: Path,
    rejection_output: Path,
    report_output: Path,
) -> dict:
    with (corpus / "index.csv").open(encoding="utf-8", newline="") as handle:
        index = list(csv.DictReader(handle))
    rows, errors = [], []
    for metadata in index:
        content = (corpus / metadata["path"]).read_bytes()
        digest = hashlib.sha256(content).hexdigest()
        if digest != metadata["source_sha256"]:
            raise Form4ParseError(
                f"source hash mismatch: {metadata['accession_number']}"
            )
        try:
            rows.extend(parse_document(content, metadata))
        except IssuerCikMismatch as error:
            errors.append({
                "accession_number": metadata["accession_number"],
                "expected_issuer_cik": metadata["issuer_cik"],
                "candidate_tickers": metadata["candidate_tickers"],
                "source_sha256": metadata["source_sha256"],
                "reason": "SUBMISSIONS_CONTAINER_IS_NOT_XML_ISSUER",
                "error": str(error),
            })
        except Form4ParseError:
            raise
    frame = pd.DataFrame(rows)
    if frame.empty:
        raise Form4ParseError("no Form 4 transactions parsed")
    atomic_output.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(atomic_output, index=False)
    pd.DataFrame(errors).to_csv(rejection_output, index=False)

    frame["reviewHash"] = frame["atomicTransactionId"].map(
        lambda value: hashlib.sha256(f"FORM4_REVIEW_V1|{value}".encode()).hexdigest()
    )
    issuer_review = (
        frame.sort_values(["issuerCik", "reviewHash"])
        .groupby("issuerCik", sort=True, group_keys=False)
        .head(5)
    )
    code_review = (
        frame.sort_values(["transactionCode", "reviewHash"])
        .groupby("transactionCode", sort=True, group_keys=False)
        .head(3)
    )
    review = (
        pd.concat([issuer_review, code_review], ignore_index=True)
        .drop_duplicates("atomicTransactionId")
        .sort_values(["issuerCik", "reviewHash"])
        .copy()
    )
    review["reviewDecision"] = "PENDING"
    review["reviewNotes"] = ""
    review.to_csv(review_output, index=False)

    code_counts = Counter(frame["transactionCode"].fillna(""))
    known = int(frame["economicClass"].ne("UNKNOWN_TRANSACTION_CODE").sum())
    decisions = Counter(review["reviewDecision"])
    reviewed = decisions["VALID"] + decisions["INVALID"] + decisions["AMBIGUOUS"]
    valid = decisions["VALID"]
    field_coverage = {
        column: float(frame[column].notna().mean())
        for column in (
            "transactionDate",
            "transactionCode",
            "transactionShares",
            "transactionPricePerShare",
            "acquiredDisposedCode",
            "sharesOwnedFollowingTransaction",
            "directOrIndirectOwnership",
            "natureOfOwnership",
        )
    }
    class_counts = frame["economicClass"].value_counts().to_dict()
    group_counts = frame["economicGroup"].value_counts().to_dict()
    report = {
        "report_version": "HERD_SEC_FORM4_ATOMIC_V1",
        "status": "SOURCE_REVIEW_PENDING",
        "documents": len(index),
        "documents_parsed": len(index) - len(errors),
        "documents_rejected_issuer_mismatch": len(errors),
        "transactions": len(frame),
        "issuers": int(frame["issuerCik"].nunique()),
        "transaction_code_counts": dict(sorted(code_counts.items())),
        "economic_class_counts": class_counts,
        "economic_group_counts": group_counts,
        "known_code_coverage": known / len(frame),
        "field_coverage": field_coverage,
        "transactions_with_referenced_footnotes": int(
            frame["footnoteIds"].fillna("").ne("").sum()
        ),
        "ten_b5_1_status_counts": frame["tenB5OneStatus"].value_counts().to_dict(),
        "direct_indirect_counts": frame[
            "directOrIndirectOwnership"
        ].value_counts(dropna=False).to_dict(),
        "review_sample_transactions": len(review),
        "review_sample_issuers": int(review["issuerCik"].nunique()),
        "review_sample_transaction_codes": int(
            review["transactionCode"].nunique()
        ),
        "population_transaction_codes": int(frame["transactionCode"].nunique()),
        "review_selection": "5_PER_ISSUER_PLUS_3_PER_TRANSACTION_CODE_BY_SHA256",
        "reviewed_transactions": reviewed,
        "valid_transactions": valid,
        "field_accuracy": None if not reviewed else valid / reviewed,
        "wilson_95_lower_bound": wilson_lower(valid, reviewed),
        "accuracy_gate_passed": False,
        "source_manifest_sha256": _file_sha256(corpus / "manifest.json"),
        "atomic_output_sha256": _file_sha256(atomic_output),
        "review_sample_sha256": _file_sha256(review_output),
        "rejection_ledger_sha256": _file_sha256(rejection_output),
        "price_outcomes_opened": False,
        "direction_hypothesis_allowed": False,
        "operational_action_authority": False,
        "next_decision": "COMPLETE_PRIMARY_SOURCE_REVIEW",
    }
    report_output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("corpus", type=Path)
    parser.add_argument("--atomic-output", type=Path, required=True)
    parser.add_argument("--review-output", type=Path, required=True)
    parser.add_argument("--rejection-output", type=Path, required=True)
    parser.add_argument("--report-output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build(
        args.corpus,
        args.atomic_output,
        args.review_output,
        args.rejection_output,
        args.report_output,
    ), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
