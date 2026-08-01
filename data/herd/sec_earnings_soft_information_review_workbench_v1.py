"""SEC 실적 문구 원자 사실과 원문 문장을 나란히 검수하는 로컬 HTML을 만든다."""

from __future__ import annotations

import argparse
import html
import json
from pathlib import Path

import pandas as pd

from herd.sec_earnings_soft_information_measurement_v1 import (
    PROTOCOL_PATH,
    _load_protocol,
    resolve_review_sentences,
)


def build_payload(review_path: Path) -> tuple[list[dict], dict]:
    protocol = _load_protocol(PROTOCOL_PATH)
    review = pd.read_csv(review_path, dtype=str, keep_default_na=False)
    rows = review.to_dict("records")
    sentences = resolve_review_sentences(rows, protocol)
    payload = []
    for row in rows:
        sentence = sentences[row["review_id"]]
        payload.append({
            "reviewId": row["review_id"],
            "reviewHash": row["review_hash"],
            "atomicFactId": row["atomic_fact_id"],
            "ticker": row["ticker"],
            "cik": row["cik"],
            "accessionNumber": row["accession_number"],
            "acceptedAt": row["accepted_at"],
            "sourceUrl": row["source_url"],
            "sourceSha256": row["source_sha256"],
            "sourcePath": row["source_path"],
            "sourceKind": row["source_kind"],
            "blockPath": row["block_path"],
            "sentenceIndex": row["sentence_index"],
            "sentenceSha256": row["sentence_sha256"],
            "topic": row["topic"],
            "topicMatches": row["topic_matches"],
            "cueFamilies": row["cue_families"],
            "cueMatches": row["cue_matches"],
            "negatedCuePresent": row["negated_cue_present"],
            "comparisonPresent": row["comparison_present"],
            "era": row["era"],
            "sentence": sentence,
            "decision": row["review_decision"],
            "notes": row["review_notes"],
            "reviewerId": row["reviewer_id"],
            "reviewedAtUtc": row["reviewed_at_utc"],
            "reviewMethod": row["review_method"],
        })
    manifest = {
        "reportVersion": "HERD_SEC_EARNINGS_SOFT_INFORMATION_REVIEW_WORKBENCH_V1",
        "status": "READY_FOR_PRIMARY_SOURCE_REVIEW",
        "rows": len(payload),
        "issuers": len({row["cik"] for row in payload}),
        "topics": sorted({row["topic"] for row in payload}),
        "sentenceTextPersistedOnlyInLocalWorkbench": True,
        "automaticValidLabelsCreated": False,
        "priceOrReturnOutcomesOpened": False,
        "directionHypothesisAllowed": False,
        "operationalActionAuthority": False,
    }
    return payload, manifest


def render(payload: list[dict], manifest: dict, output_path: Path) -> None:
    data = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")
    manifest_text = html.escape(json.dumps(manifest, ensure_ascii=False, indent=2))
    document = f"""<!doctype html><html lang=\"ko\"><head><meta charset=\"utf-8\">
<meta name=\"viewport\" content=\"width=device-width\"><title>HerdSignal SEC 문구 검수</title>
<style>*{{box-sizing:border-box}}body{{margin:0;background:#080c12;color:#e5e9ef;font:14px system-ui}}
header{{position:sticky;top:0;z-index:2;padding:16px 22px;background:#0d131c;border-bottom:1px solid #26303d}}
h1{{font-size:18px;margin:0 0 9px}}button,select,input,textarea{{background:#111923;color:#e5e9ef;border:1px solid #303c4b;border-radius:7px;padding:8px}}
.bar{{display:flex;gap:8px;flex-wrap:wrap}}main{{display:grid;grid-template-columns:330px 1fr;min-height:calc(100vh - 98px)}}
aside{{height:calc(100vh - 98px);overflow:auto;border-right:1px solid #26303d}}.item{{padding:11px 14px;border-bottom:1px solid #1d2631;cursor:pointer}}
.item.active{{background:#172333}}section{{padding:22px;overflow:auto}}.muted{{color:#8793a3}}.topic{{color:#7eb0ef;font-weight:700}}
.sentence{{font-size:19px;line-height:1.65;background:#0d141e;border:1px solid #273342;border-radius:10px;padding:20px}}
.facts{{display:grid;grid-template-columns:repeat(3,minmax(180px,1fr));gap:9px;margin:14px 0}}.fact{{background:#0d141e;border:1px solid #273342;border-radius:8px;padding:11px;overflow-wrap:anywhere}}
.fact b{{display:block;color:#8793a3;font-size:11px;margin-bottom:6px}}textarea{{width:100%;min-height:85px}}@media(max-width:900px){{main{{grid-template-columns:1fr}}aside{{height:250px}}}}</style></head>
<body><header><h1>SEC 실적 문구 원문 검수</h1><div class=\"bar\"><select id=\"filter\"><option value=\"\">전체</option><option>PENDING</option><option>VALID</option><option>INVALID</option><option>AMBIGUOUS</option></select>
<input id=\"search\" placeholder=\"ticker / topic / accession\"><input id=\"reviewer\" placeholder=\"검수자 ID\"><select id=\"method\"><option>PRIMARY_SOURCE_DIRECT</option><option>AI_ASSISTED_PRIMARY_SOURCE_DIRECT</option></select><button id=\"exporter\">판정 CSV 내보내기</button></div>
<div class=\"muted\">가격·수익률 비공개 · 자동 VALID 없음 · 로컬에서만 원문 표시</div></header>
<main><aside id=\"list\"></aside><section id=\"detail\"><pre>{manifest_text}</pre></section></main><script>
const rows={data};let selected=null;const esc=s=>String(s??'').replace(/[&<>\"']/g,c=>({{'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;',"'":'&#39;'}}[c]));
function visible(r){{const q=search.value.toLowerCase();return(!filter.value||r.decision===filter.value)&&(!q||[r.ticker,r.topic,r.accessionNumber].join(' ').toLowerCase().includes(q))}}
function draw(){{const shown=rows.filter(visible);list.innerHTML=`<div class=\"item muted\">${{shown.length}} / ${{rows.length}}건</div>`+shown.map(r=>`<div class=\"item ${{selected===r.reviewId?'active':''}}\" data-id=\"${{r.reviewId}}\"><span class=\"topic\">${{esc(r.topic)}}</span> · ${{esc(r.ticker)}}<br><span class=\"muted\">${{esc(r.decision)}} · ${{esc(r.acceptedAt.slice(0,10))}}</span></div>`).join('');list.querySelectorAll('[data-id]').forEach(x=>x.onclick=()=>show(x.dataset.id))}}
function show(id){{selected=id;const r=rows.find(x=>x.reviewId===id);detail.innerHTML=`<h2>${{esc(r.ticker)}} · <span class=\"topic\">${{esc(r.topic)}}</span></h2><div class=\"muted\">${{esc(r.accessionNumber)}} · ${{esc(r.acceptedAt)}} · era ${{esc(r.era)}}</div><p class=\"sentence\">${{esc(r.sentence)}}</p><div class=\"facts\"><div class=\"fact\"><b>TOPIC MATCHES</b>${{esc(r.topicMatches)}}</div><div class=\"fact\"><b>CUE FAMILIES</b>${{esc(r.cueFamilies)}}</div><div class=\"fact\"><b>CUE MATCHES / SCOPE</b>${{esc(r.cueMatches)}}<br>negated=${{esc(r.negatedCuePresent)}} · comparison=${{esc(r.comparisonPresent)}}</div></div><p><a href=\"${{esc(r.sourceUrl)}}\" target=\"_blank\">SEC 원문 열기</a></p><select id=\"decision\">${{['PENDING','VALID','INVALID','AMBIGUOUS'].map(v=>`<option ${{r.decision===v?'selected':''}}>${{v}}</option>`).join('')}}</select><textarea id=\"notes\" placeholder=\"INVALID·AMBIGUOUS 근거와 오류 필드\">${{esc(r.notes)}}</textarea>`;decision.onchange=e=>{{r.decision=e.target.value;if(r.decision!=='PENDING'){{r.reviewerId=reviewer.value.trim();r.reviewMethod=method.value;r.reviewedAtUtc=new Date().toISOString()}}else{{r.reviewerId='';r.reviewMethod='';r.reviewedAtUtc=''}}draw()}};notes.oninput=e=>r.notes=e.target.value;draw()}}
function csv(v){{return '\"'+String(v??'').replaceAll('\"','\"\"')+'\"'}}
exporter.onclick=()=>{{const cols=['review_id','review_hash','atomic_fact_id','ticker','cik','accession_number','accepted_at','source_url','source_sha256','source_path','source_kind','block_path','sentence_index','sentence_sha256','topic','topic_matches','cue_families','cue_matches','negated_cue_present','comparison_present','era','review_decision','review_notes','reviewer_id','reviewed_at_utc','review_method'];const lines=[cols.join(','),...rows.map(r=>[r.reviewId,r.reviewHash,r.atomicFactId,r.ticker,r.cik,r.accessionNumber,r.acceptedAt,r.sourceUrl,r.sourceSha256,r.sourcePath,r.sourceKind,r.blockPath,r.sentenceIndex,r.sentenceSha256,r.topic,r.topicMatches,r.cueFamilies,r.cueMatches,r.negatedCuePresent,r.comparisonPresent,r.era,r.decision,r.notes,r.reviewerId,r.reviewedAtUtc,r.reviewMethod].map(csv).join(','))];const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([lines.join('\n')],{{type:'text/csv'}}));a.download='sec_earnings_soft_information_decisions_v1.csv';a.click()}}
filter.onchange=draw;search.oninput=draw;draw();</script></body></html>"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(document, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("review", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    payload, manifest = build_payload(args.review)
    render(payload, manifest, args.output)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
