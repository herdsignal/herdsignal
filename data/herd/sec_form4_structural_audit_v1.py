"""production parser와 독립적으로 Form 4 표본의 XML 필드 결합을 감사한다."""

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


OFFICIAL_CLASS = {
    "P": "OPEN_MARKET_OR_PRIVATE_PURCHASE",
    "S": "OPEN_MARKET_OR_PRIVATE_SALE",
    "F": "TAX_OR_EXERCISE_WITHHOLDING",
    "A": "RULE16B3_GRANT_AWARD_OR_ACQUISITION",
    "D": "RULE16B3_DISPOSITION_TO_ISSUER",
    "I": "RULE16B3_DISCRETIONARY_TRANSACTION",
    "C": "DERIVATIVE_CONVERSION",
    "E": "SHORT_DERIVATIVE_EXPIRATION",
    "H": "LONG_DERIVATIVE_EXPIRATION_OR_CANCELLATION",
    "K": "EQUITY_SWAP_OR_SIMILAR_INSTRUMENT",
    "M": "RULE16B3_DERIVATIVE_EXERCISE_OR_CONVERSION",
    "O": "OUT_OF_MONEY_DERIVATIVE_EXERCISE",
    "X": "IN_OR_AT_MONEY_DERIVATIVE_EXERCISE",
    "G": "BONA_FIDE_GIFT",
    "W": "WILL_OR_DESCENT_DISTRIBUTION",
    "J": "OTHER_REQUIRES_DESCRIPTION",
    "L": "SMALL_ACQUISITION_RULE16A6",
    "U": "CHANGE_OF_CONTROL_TENDER_DISPOSITION",
    "V": "VOLUNTARY_EARLY_REPORT",
    "Z": "VOTING_TRUST_DEPOSIT_OR_WITHDRAWAL",
}
OFFICIAL_GROUP = {
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


class StructuralAuditError(RuntimeError):
    pass


def _name(node: ET.Element) -> str:
    return node.tag.rsplit("}", 1)[-1]


def _direct(node: ET.Element | None, name: str) -> ET.Element | None:
    if node is None:
        return None
    return next((child for child in node if _name(child) == name), None)


def _at(node: ET.Element | None, path: str) -> ET.Element | None:
    current = node
    for name in path.split("/"):
        current = _direct(current, name)
        if current is None:
            return None
    return current


def _content(node: ET.Element | None, path: str = "") -> str:
    target = _at(node, path) if path else node
    return "" if target is None else "".join(target.itertext()).strip()


def _value(node: ET.Element | None, path: str) -> str:
    return _content(node, f"{path}/value")


def _owners(root: ET.Element) -> str:
    result = []
    for owner in (node for node in root.iter() if _name(node) == "reportingOwner"):
        identity = _direct(owner, "reportingOwnerId")
        relationship = _direct(owner, "reportingOwnerRelationship")
        result.append({
            "rptOwnerCik": _content(identity, "rptOwnerCik") or None,
            "rptOwnerName": _content(identity, "rptOwnerName") or None,
            "isDirector": _content(relationship, "isDirector") or None,
            "isOfficer": _content(relationship, "isOfficer") or None,
            "isTenPercentOwner": _content(
                relationship, "isTenPercentOwner"
            ) or None,
            "isOther": _content(relationship, "isOther") or None,
            "officerTitle": _content(relationship, "officerTitle") or None,
        })
    return json.dumps(result, ensure_ascii=False, sort_keys=True)


def _ten_b5(root: ET.Element, referenced: str) -> str:
    for node in root.iter():
        if _name(node) in {"aff10b5One", "isTenB5One", "tenB5One"}:
            value = _content(node).lower()
            if value in {"1", "true", "yes"}:
                return "TRUE"
            if value in {"0", "false", "no"}:
                return "FALSE"
    return (
        "TRUE"
        if re.search(r"\b10b5-?1\b", referenced, flags=re.IGNORECASE)
        else "UNKNOWN"
    )


def independently_extract(content: bytes, metadata: dict, index: int) -> dict:
    root = ET.fromstring(content)
    issuer = next((node for node in root.iter() if _name(node) == "issuer"), None)
    transactions = [
        (node, False) for node in root.iter()
        if _name(node) == "nonDerivativeTransaction"
    ] + [
        (node, True) for node in root.iter()
        if _name(node) == "derivativeTransaction"
    ]
    if index < 0 or index >= len(transactions):
        raise StructuralAuditError("transaction index out of range")
    transaction, derivative = transactions[index]
    coding = _direct(transaction, "transactionCoding")
    footnotes = {
        node.attrib.get("id", ""): _content(node)
        for node in root.iter() if _name(node) == "footnote"
    }
    identifiers = sorted({
        node.attrib.get("id", "").strip()
        for node in transaction.iter()
        if _name(node) == "footnoteId" and node.attrib.get("id", "").strip()
    })
    referenced = "\n".join(
        f"[{identifier}] {footnotes.get(identifier, '')}"
        for identifier in identifiers
    )
    code = _content(coding, "transactionCode")
    issuer_cik = _content(issuer, "issuerCik")
    return {
        "issuerCik": f"{int(issuer_cik):010d}",
        "reportingOwner": _owners(root),
        "securityTitle": _value(transaction, "securityTitle"),
        "transactionDate": _value(transaction, "transactionDate"),
        "transactionCode": code,
        "economicClass": OFFICIAL_CLASS.get(code, "UNKNOWN_TRANSACTION_CODE"),
        "economicGroup": OFFICIAL_GROUP.get(
            code, "UNKNOWN_TRANSACTION_CODE"
        ),
        "transactionShares": _value(
            transaction, "transactionAmounts/transactionShares"
        ),
        "transactionPricePerShare": _value(
            transaction, "transactionAmounts/transactionPricePerShare"
        ),
        "acquiredDisposedCode": _value(
            transaction,
            "transactionAmounts/transactionAcquiredDisposedCode",
        ),
        "sharesOwnedFollowingTransaction": _value(
            transaction,
            "postTransactionAmounts/sharesOwnedFollowingTransaction",
        ),
        "directOrIndirectOwnership": _value(
            transaction, "ownershipNature/directOrIndirectOwnership"
        ),
        "natureOfOwnership": _value(
            transaction, "ownershipNature/natureOfOwnership"
        ),
        "footnoteIds": "|".join(identifiers),
        "footnoteText": referenced,
        "isDerivative": str(derivative),
        "tenB5OneStatus": _ten_b5(root, referenced),
        "acceptanceDatetime": metadata["acceptance_datetime"],
    }


def audit(
    review_path: Path,
    corpus: Path,
    protocol_path: Path,
    detail_output: Path,
    report_output: Path,
) -> dict:
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    checks = protocol["required_checks"]
    review = pd.read_csv(review_path, keep_default_na=False, dtype=str)
    with (corpus / "index.csv").open(encoding="utf-8", newline="") as handle:
        sources = {
            row["source_sha256"]: row for row in csv.DictReader(handle)
        }
    results = []
    for row in review.to_dict("records"):
        source = sources[row["sourceSha256"]]
        raw = (corpus / source["path"]).read_bytes()
        if hashlib.sha256(raw).hexdigest() != row["sourceSha256"]:
            raise StructuralAuditError("source hash mismatch")
        expected = independently_extract(
            raw, source, int(row["transactionIndex"])
        )
        mismatch = [
            field for field in checks
            if str(row.get(field, "")) != str(expected.get(field, ""))
        ]
        results.append({
            "atomicTransactionId": row["atomicTransactionId"],
            "issuerCik": row["issuerCik"],
            "candidateTickers": row["candidateTickers"],
            "accessionNumber": row["accessionNumber"],
            "transactionCode": row["transactionCode"],
            "structuralDecision": (
                "STRUCTURE_MATCH" if not mismatch else "STRUCTURE_MISMATCH"
            ),
            "mismatchFields": "|".join(mismatch),
            "sourceSha256": row["sourceSha256"],
            "humanReviewDecision": row["reviewDecision"],
        })
    detail = pd.DataFrame(results)
    detail_output.parent.mkdir(parents=True, exist_ok=True)
    detail.to_csv(detail_output, index=False)
    mismatch_counts = Counter(
        field
        for value in detail["mismatchFields"]
        for field in value.split("|") if field
    )
    matched = int(detail["structuralDecision"].eq("STRUCTURE_MATCH").sum())
    report = {
        "report_version": "HERD_SEC_FORM4_STRUCTURAL_AUDIT_V1",
        "status": (
            "STRUCTURAL_AUDIT_PASSED"
            if matched == len(detail) else "STRUCTURAL_AUDIT_FAILED"
        ),
        "transactions": len(detail),
        "issuers": int(detail["issuerCik"].nunique()),
        "transaction_codes": sorted(detail["transactionCode"].unique()),
        "structure_matches": matched,
        "structure_mismatches": len(detail) - matched,
        "mismatch_field_counts": dict(sorted(mismatch_counts.items())),
        "human_valid_labels_created": False,
        "human_review_pending": int(
            detail["humanReviewDecision"].eq("PENDING").sum()
        ),
        "price_outcomes_opened": False,
        "direction_hypothesis_allowed": False,
        "operational_action_authority": False,
        "next_decision": (
            "COMPLETE_HUMAN_SOURCE_REVIEW"
            if matched == len(detail) else "REPAIR_PRODUCTION_PARSER"
        ),
    }
    report_output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("review", type=Path)
    parser.add_argument("corpus", type=Path)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--detail-output", type=Path, required=True)
    parser.add_argument("--report-output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(audit(
        args.review,
        args.corpus,
        args.protocol,
        args.detail_output,
        args.report_output,
    ), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
