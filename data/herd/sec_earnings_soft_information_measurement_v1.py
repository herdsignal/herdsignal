"""SEC 실적발표 원문에서 가격 비노출 soft-information 원자 사실을 만든다."""

from __future__ import annotations

import gzip
import hashlib
import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable

import pandas as pd
from lxml import etree, html


ROOT = Path(__file__).resolve().parents[2]
PROTOCOL_PATH = Path(__file__).with_suffix(".json")
CANDIDATES_PATH = ROOT / "data/reports/sec_earnings_soft_information_candidates_v1.csv"
REVIEW_PATH = ROOT / "data/reports/sec_earnings_soft_information_source_review_v1.csv"
REPORT_PATH = ROOT / "data/reports/sec_earnings_soft_information_measurement_v1.json"
VERSION = "HERD_SEC_EARNINGS_SOFT_INFORMATION_MEASUREMENT_V1"


class SoftInformationMeasurementError(ValueError):
    """불변 입력·문장 추적성·연구 방화벽이 깨졌을 때 발생한다."""


@dataclass(frozen=True)
class PhraseMatch:
    value: str
    start: int
    end: int


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _load_protocol(path: Path = PROTOCOL_PATH) -> dict[str, Any]:
    protocol = json.loads(path.read_text())
    if (
        protocol.get("protocolVersion") != VERSION
        or protocol.get("status") != "LOCKED_BEFORE_SOURCE_REVIEW_OR_PRICE_OUTCOMES"
    ):
        raise SoftInformationMeasurementError("measurement protocol is not locked")
    for item in protocol.get("pinnedInputs", []):
        source = (ROOT / item["path"]).resolve()
        if not source.is_relative_to(ROOT) or not source.is_file():
            raise SoftInformationMeasurementError(f"missing input: {item['path']}")
        if _sha256(source) != item["sha256"]:
            raise SoftInformationMeasurementError(f"input changed: {item['path']}")
    _validate_firewall(protocol)
    return protocol


def _validate_firewall(protocol: dict[str, Any]) -> None:
    firewall = protocol.get("firewall", {})
    false_fields = {
        "sentenceTextStoredInCommittedLedger",
        "aggregateDirectionScoreComputed",
        "currentPriorDirectionCompared",
        "priceOrReturnOutcomesOpened",
        "directionHypothesisPreregistered",
        "automaticValidLabelsAllowed",
        "remoteModelAllowed",
        "herdFormulaChangeAllowed",
        "operationalActionAllowed",
    }
    if (
        any(firewall.get(field) is not False for field in false_fields)
        or firewall.get("operationalAction") != "HOLD"
        or firewall.get("operationalActionRatio") != 0.0
    ):
        raise SoftInformationMeasurementError("measurement firewall was weakened")
    selection = protocol.get("sourceReviewSelection", {})
    if (
        selection.get("fullCorpusMeasurementAllowedOnlyAfterSourceReviewPass")
        is not True
        or not 500 <= selection.get("minimumDocuments", 0)
        <= selection.get("maximumDocuments", 0)
        <= 1000
    ):
        raise SoftInformationMeasurementError(
            "source review selection boundary was weakened"
        )


@lru_cache(maxsize=None)
def _phrase_pattern(phrase: str) -> re.Pattern[str]:
    escaped = re.escape(phrase).replace(r"\ ", r"[\s\-]+")
    return re.compile(rf"(?<![A-Za-z]){escaped}(?![A-Za-z])", re.I)


def _find_phrases(value: str, phrases: Iterable[str]) -> list[PhraseMatch]:
    output: list[PhraseMatch] = []
    for phrase in phrases:
        output.extend(
            PhraseMatch(match.group(0), match.start(), match.end())
            for match in _phrase_pattern(phrase).finditer(value)
        )
    return sorted(output, key=lambda match: (match.start, -(match.end - match.start)))


def _normalize(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _ascii_blocks(value: str, source_kind: str) -> list[dict[str, str]]:
    blocks: list[dict[str, str]] = []
    current: list[tuple[int, str]] = []
    lines = value.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    for line_number, raw in enumerate(lines, start=1):
        line = _normalize(raw)
        if line:
            current.append((line_number, line))
        elif current:
            blocks.append({
                "source_kind": source_kind,
                "block_path": f"lines:{current[0][0]}-{current[-1][0]}",
                "block_text": " ".join(item[1] for item in current),
            })
            current = []
    if current:
        blocks.append({
            "source_kind": source_kind,
            "block_path": f"lines:{current[0][0]}-{current[-1][0]}",
            "block_text": " ".join(item[1] for item in current),
        })
    return blocks


def soft_text_blocks(content: bytes) -> list[dict[str, str]]:
    """표를 버리고 문장형 블록만 선형 시간에 추출한다."""
    decoded = content.decode("utf-8", errors="replace")
    if not re.search(r"<\s*(?:html|body|div|p|pre|li)\b", decoded, re.I):
        return _ascii_blocks(decoded, "ASCII")
    try:
        document = html.fromstring(content)
    except (ValueError, etree.ParserError):
        return _ascii_blocks(decoded, "ASCII_PARSE_FALLBACK")
    blocks: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for ordinal, element in enumerate(document.xpath("//pre|//p|//li|//div")):
        tag = element.tag.lower() if isinstance(element.tag, str) else ""
        ancestor_tags = {
            ancestor.tag.lower()
            for ancestor in element.iterancestors()
            if isinstance(ancestor.tag, str)
        }
        if "table" in ancestor_tags or "pre" in ancestor_tags:
            continue
        if tag == "div" and len(element):
            continue
        source_kind = f"HTML_{tag.upper()}"
        if tag == "pre":
            extracted = _ascii_blocks(element.text_content(), source_kind)
            for child_index, block in enumerate(extracted):
                text = block["block_text"]
                key = (source_kind, text)
                if key in seen:
                    continue
                seen.add(key)
                blocks.append({
                    "source_kind": source_kind,
                    "block_path": f"{tag}:{ordinal}:block:{child_index}",
                    "block_text": text,
                })
            continue
        text = _normalize(element.text_content())
        key = (source_kind, text)
        if not text or key in seen:
            continue
        seen.add(key)
        blocks.append({
            "source_kind": source_kind,
            "block_path": f"{tag}:{ordinal}",
            "block_text": text,
        })
    return blocks


def split_sentences(block_text: str) -> list[str]:
    """EDGAR 문단을 보수적으로 분리하며 원문 문장 내용은 반환 시에만 유지한다."""
    value = _normalize(block_text)
    if not value:
        return []
    boundaries = re.compile(
        r"(?<=[.!?])\s+(?=(?:[\"'“‘(]*[A-Z][A-Za-z]|[\"'“‘(]*\d{4}\b))"
    )
    return [sentence.strip() for sentence in boundaries.split(value) if sentence.strip()]


def _sentence_allowed(sentence: str, rules: dict[str, Any]) -> bool:
    if not rules["minimumCharacters"] <= len(sentence) <= rules["maximumCharacters"]:
        return False
    compact = re.sub(r"\s+", "", sentence)
    if compact and sum(character.isdigit() for character in compact) / len(compact) > rules["maximumDigitShare"]:
        return False
    if len(re.findall(r"\b[A-Za-z][A-Za-z'-]*\b", sentence)) < rules["minimumAlphabeticWords"]:
        return False
    lower = sentence.casefold()
    if any(phrase.casefold() in lower for phrase in rules["excludedBoilerplatePhrases"]):
        return False
    return not any(
        re.search(pattern, sentence, re.I)
        for pattern in rules["excludedBoilerplatePatterns"]
    )


def _negated(sentence: str, cue: PhraseMatch, protocol: dict[str, Any]) -> bool:
    prefix = sentence[:cue.start]
    tokens = re.findall(r"[A-Za-z']+", prefix.casefold())
    lookback = protocol["scopeRules"]["negationLookbackTokens"]
    return bool(set(tokens[-lookback:]) & set(protocol["scopeRules"]["negationTokens"]))


def extract_sentence_facts(sentence: str, protocol: dict[str, Any]) -> list[dict[str, Any]]:
    if not _sentence_allowed(sentence, protocol["sentenceRules"]):
        return []
    topics = {
        topic: _find_phrases(sentence, phrases)
        for topic, phrases in protocol["economicTopics"].items()
    }
    topics = {topic: matches for topic, matches in topics.items() if matches}
    cues = {
        family: _find_phrases(sentence, phrases)
        for family, phrases in protocol["cueFamilies"].items()
    }
    cues = {family: matches for family, matches in cues.items() if matches}
    if not topics or not cues:
        return []
    comparison = _find_phrases(sentence, protocol["scopeRules"]["comparisonPhrases"])
    facts = []
    for topic, topic_matches in topics.items():
        cue_rows = [
            {
                "family": family,
                "value": match.value.casefold(),
                "start": match.start,
                "end": match.end,
                "negated": _negated(sentence, match, protocol),
            }
            for family, matches in cues.items()
            for match in matches
            if min(
                max(topic_match.start - match.end, match.start - topic_match.end, 0)
                for topic_match in topic_matches
            ) <= protocol["scopeRules"]["maximumTopicCueDistanceCharacters"]
        ]
        if not cue_rows:
            continue
        facts.append({
            "topic": topic,
            "topicMatches": sorted({match.value.casefold() for match in topic_matches}),
            "cueFamilies": sorted({row["family"] for row in cue_rows}),
            "cueMatches": cue_rows,
            "negatedCuePresent": any(row["negated"] for row in cue_rows),
            "comparisonPresent": bool(comparison),
        })
    return facts


def _eligible_sources(
    protocol: dict[str, Any],
) -> tuple[Path, pd.DataFrame, int]:
    index_item = next(
        item for item in protocol["pinnedInputs"] if item["path"].endswith("index.csv")
    )
    corpus = (ROOT / index_item["path"]).parent
    pairs_item = next(
        item for item in protocol["pinnedInputs"] if item["path"].endswith("pairs_v1.csv")
    )
    pairs = pd.read_csv(ROOT / pairs_item["path"], dtype=str, keep_default_na=False)
    source_paths = set(pairs["path"]) | set(pairs["prior_path"])
    index = pd.read_csv(corpus / "index.csv", dtype=str, keep_default_na=False)
    sources = index.loc[index["path"].isin(source_paths)].copy()
    sources = sources.sort_values(
        ["accession_number", "source_bytes", "source_sha256"],
        ascending=[True, False, True],
    ).drop_duplicates("accession_number", keep="first")
    total = len(sources)
    selection = protocol["sourceReviewSelection"]
    sources["accepted_year"] = pd.to_datetime(
        sources["accepted_at"], utc=True
    ).dt.year
    first_year = int(sources["accepted_year"].min())
    sources["source_era"] = (
        (sources["accepted_year"] - first_year) // selection["eraLengthYears"]
    ).astype(int)
    sources["source_priority"] = sources["source_sha256"].map(
        lambda value: _sha256_bytes(
            f"{selection['selectionSalt']}|{value}".encode()
        )
    )
    sources = sources.sort_values("source_priority")
    selected = set(
        sources.groupby(["cik", "source_era"], sort=True).head(1).index
    )
    for index in sources.index:
        if len(selected) >= selection["maximumDocuments"]:
            break
        selected.add(index)
    if len(selected) < selection["minimumDocuments"]:
        raise SoftInformationMeasurementError(
            "not enough price-blind source review documents"
        )
    selected_sources = sources.loc[list(selected)].drop(
        columns=["accepted_year", "source_era", "source_priority"]
    )
    return (
        corpus,
        selected_sources.sort_values(["accepted_at", "cik", "accession_number"]),
        total,
    )


def extract_document_candidates(
    content: bytes,
    source: dict[str, str],
    protocol: dict[str, Any],
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for block in soft_text_blocks(content):
        for sentence_index, sentence in enumerate(split_sentences(block["block_text"])):
            sentence_sha = _sha256_bytes(sentence.encode())
            for fact in extract_sentence_facts(sentence, protocol):
                identity = "|".join((
                    source["source_sha256"], block["block_path"], str(sentence_index),
                    sentence_sha, fact["topic"],
                ))
                records.append({
                    "atomic_fact_id": _sha256_bytes(identity.encode()),
                    "ticker": source["ticker"],
                    "cik": source["cik"],
                    "accession_number": source["accession_number"],
                    "accepted_at": source["accepted_at"],
                    "source_url": source["source_url"],
                    "source_sha256": source["source_sha256"],
                    "source_path": source["path"],
                    "source_kind": block["source_kind"],
                    "block_path": block["block_path"],
                    "sentence_index": sentence_index,
                    "sentence_sha256": sentence_sha,
                    "topic": fact["topic"],
                    "topic_matches": json.dumps(fact["topicMatches"], separators=(",", ":")),
                    "cue_families": json.dumps(fact["cueFamilies"], separators=(",", ":")),
                    "cue_matches": json.dumps(fact["cueMatches"], separators=(",", ":")),
                    "negated_cue_present": fact["negatedCuePresent"],
                    "comparison_present": fact["comparisonPresent"],
                })
    return records


def _sample_review(candidates: pd.DataFrame, protocol: dict[str, Any]) -> pd.DataFrame:
    gate = protocol["reviewGate"]
    if candidates.empty:
        return candidates.copy()
    frame = candidates.copy()
    years = pd.to_datetime(frame["accepted_at"], utc=True).dt.year
    first_year = int(years.min())
    frame["era"] = ((years - first_year) // gate["eraLengthYears"]).astype(int)
    frame["review_priority"] = frame["atomic_fact_id"].map(
        lambda value: _sha256_bytes(f"{gate['selectionSalt']}|{value}".encode())
    )
    frame = frame.sort_values("review_priority")
    selected: set[int] = set()

    def take(group_columns: list[str]) -> None:
        for _, group in frame.groupby(group_columns, sort=True):
            available = [index for index in group.index if index not in selected]
            if available:
                selected.add(available[0])

    take(["cik"])
    take(["topic", "era"])
    take(["topic"])
    for index in frame.index:
        if len(selected) >= gate["sampleRows"]:
            break
        selected.add(index)
    if len(selected) < gate["minimumRows"]:
        raise SoftInformationMeasurementError("not enough atomic facts for source review")
    review = frame.loc[list(selected)].sort_values("review_priority").head(gate["sampleRows"]).copy()
    review.insert(0, "review_id", [f"SESI-{index:04d}" for index in range(1, len(review) + 1)])
    review["review_hash"] = review.apply(
        lambda row: _sha256_bytes("|".join((
            row["review_id"], row["atomic_fact_id"], row["source_sha256"],
            row["sentence_sha256"], row["topic"],
        )).encode()),
        axis=1,
    )
    for column, value in (
        ("review_decision", "PENDING"), ("review_notes", ""),
        ("reviewer_id", ""), ("reviewed_at_utc", ""), ("review_method", ""),
    ):
        review[column] = value
    return review.drop(columns=["review_priority"])


def build_measurement(
    candidates_path: Path = CANDIDATES_PATH,
    review_path: Path = REVIEW_PATH,
    report_path: Path = REPORT_PATH,
) -> dict[str, Any]:
    protocol = _load_protocol()
    corpus, sources, eligible_source_count = _eligible_sources(protocol)
    records: list[dict[str, Any]] = []
    for source in sources.to_dict("records"):
        path = corpus / source["path"]
        content = gzip.open(path, "rb").read()
        if _sha256_bytes(content) != source["source_sha256"]:
            raise SoftInformationMeasurementError(f"source hash mismatch: {source['path']}")
        records.extend(extract_document_candidates(content, source, protocol))
    candidates = pd.DataFrame(records)
    if candidates.empty:
        raise SoftInformationMeasurementError("no atomic soft-information facts extracted")
    candidates = candidates.sort_values(
        ["accepted_at", "cik", "accession_number", "atomic_fact_id"]
    ).drop_duplicates("atomic_fact_id")
    review = _sample_review(candidates, protocol)
    forbidden = {"sentence", "price", "return", "label", "herd", "action"}
    if any(token in column.casefold() for column in candidates.columns for token in forbidden):
        allowed_sentence_hash_columns = {"sentence_index", "sentence_sha256"}
        offending = [
            column for column in candidates.columns
            if any(token in column.casefold() for token in forbidden)
            and column not in allowed_sentence_hash_columns
        ]
        if offending:
            raise SoftInformationMeasurementError(f"forbidden ledger columns: {offending}")
    candidates_path.parent.mkdir(parents=True, exist_ok=True)
    candidates.to_csv(candidates_path, index=False)
    review.to_csv(review_path, index=False)
    gate = protocol["reviewGate"]
    checks = {
        "minimum_rows": len(review) >= gate["minimumRows"],
        "minimum_issuers": review["cik"].nunique() >= gate["minimumIssuers"],
        "minimum_topics": review["topic"].nunique() >= gate["minimumTopics"],
        "minimum_eras": review["era"].nunique() >= gate["minimumEras"],
        "all_pending": set(review["review_decision"]) == {"PENDING"},
    }
    report = {
        "reportVersion": VERSION,
        "status": "SOURCE_REVIEW_PENDING" if all(checks.values()) else "SOURCE_REVIEW_SAMPLE_FAILED",
        "eligibleSourceDocuments": eligible_source_count,
        "sourceReviewDocuments": len(sources),
        "atomicFacts": len(candidates),
        "reviewRows": len(review),
        "reviewIssuers": int(review["cik"].nunique()),
        "reviewTopics": int(review["topic"].nunique()),
        "reviewEras": int(review["era"].nunique()),
        "topicCounts": candidates["topic"].value_counts().sort_index().to_dict(),
        "checks": checks,
        "candidatesSha256": _sha256(candidates_path),
        "reviewQueueSha256": _sha256(review_path),
        "sentenceTextStoredInCommittedLedger": False,
        "aggregateDirectionScoreComputed": False,
        "currentPriorDirectionCompared": False,
        "priceOrReturnOutcomesOpened": False,
        "directionHypothesisPreregistered": False,
        "automaticValidLabelsCreated": False,
        "operationalAction": "HOLD",
        "operationalActionRatio": 0.0,
        "nextGate": protocol["nextGateWhilePending"],
    }
    report_path.write_text(json.dumps(report, indent=2) + "\n")
    return report


def resolve_review_sentence(row: dict[str, str], protocol: dict[str, Any]) -> str:
    return resolve_review_sentences([row], protocol)[row["review_id"]]


def resolve_review_sentences(
    rows: list[dict[str, str]],
    protocol: dict[str, Any],
) -> dict[str, str]:
    corpus, sources, _ = _eligible_sources(protocol)
    source_by_sha = {
        source["source_sha256"]: source for source in sources.to_dict("records")
    }
    output: dict[str, str] = {}
    rows_by_sha: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        rows_by_sha.setdefault(row["source_sha256"], []).append(row)
    for source_sha, source_rows in rows_by_sha.items():
        source = source_by_sha.get(source_sha)
        if source is None:
            raise SoftInformationMeasurementError("review source is not unique")
        content = gzip.open(corpus / source["path"], "rb").read()
        candidates = {
            candidate["atomic_fact_id"]: candidate
            for candidate in extract_document_candidates(content, source, protocol)
        }
        blocks = {block["block_path"]: block for block in soft_text_blocks(content)}
        for row in source_rows:
            match = candidates.get(row["atomic_fact_id"])
            if match is None:
                raise SoftInformationMeasurementError(
                    "review fact cannot be reconstructed"
                )
            block = blocks.get(match["block_path"])
            if block is None:
                raise SoftInformationMeasurementError(
                    "review block cannot be reconstructed"
                )
            sentences = split_sentences(block["block_text"])
            sentence = sentences[int(match["sentence_index"])]
            if _sha256_bytes(sentence.encode()) != row["sentence_sha256"]:
                raise SoftInformationMeasurementError(
                    "review sentence hash changed"
                )
            output[row["review_id"]] = sentence
    return output


if __name__ == "__main__":
    print(json.dumps(build_measurement(), indent=2))
