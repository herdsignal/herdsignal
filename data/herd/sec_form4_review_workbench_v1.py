"""잠긴 Form 4 표본을 원문과 나란히 검수하는 오프라인 HTML을 만든다."""

from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import xml.etree.ElementTree as ET
from pathlib import Path


class ReviewWorkbenchError(RuntimeError):
    pass


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _tag(element: ET.Element) -> str:
    return element.tag.rsplit("}", 1)[-1]


def _transaction_xml(content: bytes, index: int) -> str:
    root = ET.fromstring(content)
    transactions = [
        node for node in root.iter() if _tag(node) == "nonDerivativeTransaction"
    ] + [
        node for node in root.iter() if _tag(node) == "derivativeTransaction"
    ]
    if index < 0 or index >= len(transactions):
        raise ReviewWorkbenchError(f"transaction index out of range: {index}")
    return ET.tostring(transactions[index], encoding="unicode")


def build_payload(review_path: Path, corpus: Path, protocol_path: Path) -> tuple[list[dict], dict]:
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    if protocol.get("status") != "LOCKED_BEFORE_HUMAN_SOURCE_REVIEW":
        raise ReviewWorkbenchError("review protocol must be locked")
    with review_path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    with (corpus / "index.csv").open(encoding="utf-8", newline="") as handle:
        sources = {
            row["source_sha256"]: row for row in csv.DictReader(handle)
        }
    required = protocol["required_checks"]
    payload = []
    for row in rows:
        source = sources.get(row["sourceSha256"])
        if source is None:
            raise ReviewWorkbenchError(
                f"source missing: {row['atomicTransactionId']}"
            )
        raw_path = corpus / source["path"]
        if _sha256(raw_path) != row["sourceSha256"]:
            raise ReviewWorkbenchError("source hash mismatch")
        parsed = {field: row.get(field, "") for field in required}
        payload.append({
            "atomicTransactionId": row["atomicTransactionId"],
            "reviewHash": row["reviewHash"],
            "issuerCik": row["issuerCik"],
            "ticker": row["candidateTickers"],
            "accessionNumber": row["accessionNumber"],
            "transactionCode": row["transactionCode"],
            "economicClass": row["economicClass"],
            "sourceUrl": source["source_url"],
            "sourceSha256": row["sourceSha256"],
            "parsed": parsed,
            "rawTransactionXml": _transaction_xml(
                raw_path.read_bytes(), int(row["transactionIndex"])
            ),
            "rawFootnotes": row["rawFootnotes"],
            "decision": row["reviewDecision"],
            "notes": row["reviewNotes"],
        })
    manifest = {
        "report_version": "HERD_SEC_FORM4_REVIEW_WORKBENCH_V1",
        "status": "READY_FOR_HUMAN_SOURCE_REVIEW",
        "transactions": len(payload),
        "issuers": len({row["issuerCik"] for row in payload}),
        "transaction_codes": sorted({row["transactionCode"] for row in payload}),
        "review_queue_sha256": _sha256(review_path),
        "source_manifest_sha256": _sha256(corpus / "manifest.json"),
        "protocol_sha256": _sha256(protocol_path),
        "price_outcomes_opened": False,
        "automatic_valid_labels_created": False,
        "direction_hypothesis_allowed": False,
        "operational_action_authority": False,
    }
    return payload, manifest


def render(payload: list[dict], manifest: dict, output: Path) -> None:
    data = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")
    manifest_json = html.escape(
        json.dumps(manifest, ensure_ascii=False, indent=2)
    )
    document = f"""<!doctype html>
<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>HerdSignal Form 4 Source Review</title>
<style>
*{{box-sizing:border-box}} body{{margin:0;background:#09111d;color:#dce6f3;font:14px system-ui}}
header{{position:sticky;top:0;z-index:3;padding:16px 24px;background:#0d1726;border-bottom:1px solid #263449}}
h1{{margin:0 0 8px;font-size:18px}} .meta,.muted{{color:#91a0b5}} .toolbar{{display:flex;gap:8px;flex-wrap:wrap}}
button,select,input,textarea{{background:#111e30;color:#dce6f3;border:1px solid #31435d;border-radius:7px;padding:8px}}
main{{display:grid;grid-template-columns:340px 1fr;min-height:calc(100vh - 92px)}} aside{{border-right:1px solid #263449;overflow:auto;height:calc(100vh - 92px)}}
.item{{padding:11px 14px;border-bottom:1px solid #1c2a3d;cursor:pointer}} .item.active{{background:#172943}}
.code{{font-weight:700;color:#6ca8ff}} section{{padding:20px;overflow:auto}} .grid{{display:grid;grid-template-columns:repeat(3,minmax(180px,1fr));gap:8px}}
.field{{background:#0f1a2a;border:1px solid #223249;border-radius:8px;padding:10px;overflow-wrap:anywhere}}
.field b{{display:block;color:#91a0b5;font-size:11px;margin-bottom:5px}} pre{{white-space:pre-wrap;word-break:break-word;background:#07101b;border:1px solid #223249;border-radius:8px;padding:14px}}
.decision{{display:flex;gap:8px;align-items:center;margin:16px 0}} textarea{{width:100%;min-height:76px}}
@media(max-width:900px){{main{{grid-template-columns:1fr}} aside{{height:260px;border-right:0}} .grid{{grid-template-columns:1fr}}}}
</style></head><body>
<header><h1>Form 4 원문 검수</h1><div class="toolbar">
<select id="filter"><option value="">전체</option><option>PENDING</option><option>VALID</option><option>INVALID</option><option>AMBIGUOUS</option></select>
<input id="search" placeholder="ticker / accession / code"><button id="export">판정 CSV 내보내기</button>
</div><div class="meta">가격 결과·HERD 점수 비공개 · 자동 VALID 없음 · {len(payload)}건</div></header>
<main><aside id="list"></aside><section id="detail"><pre>{manifest_json}</pre></section></main>
<script>
const rows={data}; let selected=null;
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}}[c]));
function visible(r){{const f=filter.value,q=search.value.toLowerCase();return(!f||r.decision===f)&&(!q||[r.ticker,r.accessionNumber,r.transactionCode,r.economicClass].join(' ').toLowerCase().includes(q))}}
function drawList(){{list.innerHTML=rows.filter(visible).map(r=>`<div class="item ${{selected===r.atomicTransactionId?'active':''}}" data-id="${{r.atomicTransactionId}}"><span class=code>${{esc(r.transactionCode)}}</span> ${{esc(r.ticker)}}<br><span class=muted>${{esc(r.decision)}} · ${{esc(r.accessionNumber)}}</span></div>`).join('');list.querySelectorAll('.item').forEach(x=>x.onclick=()=>show(x.dataset.id))}}
function show(id){{selected=id;const r=rows.find(x=>x.atomicTransactionId===id);detail.innerHTML=`<h2>${{esc(r.ticker)}} · code ${{esc(r.transactionCode)}} · ${{esc(r.economicClass)}}</h2><div class=muted>${{esc(r.accessionNumber)}} · SHA ${{esc(r.sourceSha256)}}</div><div class=grid>${{Object.entries(r.parsed).map(([k,v])=>`<div class=field><b>${{esc(k)}}</b>${{esc(v)}}</div>`).join('')}}</div><h3>원문 transaction XML</h3><pre>${{esc(r.rawTransactionXml)}}</pre><h3>문서 전체 각주</h3><pre>${{esc(r.rawFootnotes)}}</pre><div class=decision><select id=decision>${{['PENDING','VALID','INVALID','AMBIGUOUS'].map(v=>`<option ${{r.decision===v?'selected':''}}>${{v}}</option>`).join('')}}</select><a href="${{esc(r.sourceUrl)}}" target=_blank>SEC 원문</a></div><textarea id=notes placeholder="오류 필드와 근거">${{esc(r.notes)}}</textarea>`;decision.onchange=e=>{{r.decision=e.target.value;drawList()}};notes.oninput=e=>r.notes=e.target.value;drawList()}}
function csv(v){{return '"'+String(v??'').replaceAll('"','""')+'"'}}
export.onclick=()=>{{const cols=['atomicTransactionId','reviewHash','issuerCik','ticker','accessionNumber','transactionCode','economicClass','sourceSha256','reviewDecision','reviewNotes'];const lines=[cols.join(','),...rows.map(r=>[r.atomicTransactionId,r.reviewHash,r.issuerCik,r.ticker,r.accessionNumber,r.transactionCode,r.economicClass,r.sourceSha256,r.decision,r.notes].map(csv).join(','))];const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([lines.join('\\n')],{{type:'text/csv'}}));a.download='sec_form4_review_decisions_v1.csv';a.click()}}
filter.onchange=drawList;search.oninput=drawList;drawList();
</script></body></html>"""
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(document, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("review", type=Path)
    parser.add_argument("corpus", type=Path)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--manifest-output", type=Path, required=True)
    args = parser.parse_args()
    payload, manifest = build_payload(args.review, args.corpus, args.protocol)
    render(payload, manifest, args.output)
    args.manifest_output.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
