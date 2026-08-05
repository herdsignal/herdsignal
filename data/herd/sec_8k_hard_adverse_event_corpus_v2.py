"""검수된 filing-date 식별을 SEC hard-adverse corpus에 결합한다."""
from __future__ import annotations
import csv, hashlib, json
from collections import Counter
from pathlib import Path
from typing import Any

ROOT=Path(__file__).resolve().parents[2]; PROTOCOL=Path(__file__).with_suffix('.json')
class Sec8KHardAdverseCorpusV2Error(ValueError): pass
def _sha(path:Path)->str:return hashlib.sha256(path.read_bytes()).hexdigest()
def _rooted(rel:str)->Path:
 p=(ROOT/rel).resolve()
 if not p.is_relative_to(ROOT): raise Sec8KHardAdverseCorpusV2Error('path escapes repository')
 return p
def _csv(path:Path):
 with path.open(newline='',encoding='utf-8') as h:return list(csv.DictReader(h))
def build(protocol_path:Path=PROTOCOL)->tuple[list[dict[str,str]],dict[str,Any]]:
 p=json.loads(protocol_path.read_text(encoding='utf-8'))
 if p.get('status')!='LOCKED_AFTER_TIME_VALID_EVENT_IDENTITY_PROMOTION' or p['authority']['operational_action_ratio']!=0.0: raise Sec8KHardAdverseCorpusV2Error('V2 corpus is not fail-closed')
 paths={}
 for i in p['locked_inputs']:
  q=_rooted(i['path'])
  if not q.is_file() or _sha(q)!=i['sha256']:raise Sec8KHardAdverseCorpusV2Error(f"locked input changed: {i['path']}")
  paths[i['role']]=q
 report=json.loads(paths['PROMOTION_REPORT'].read_text(encoding='utf-8'))
 if report.get('status')!='TIME_VALID_EVENT_IDENTITY_PROMOTION_COMPLETE' or report.get('open_ended_intervals_inferred')!=0:raise Sec8KHardAdverseCorpusV2Error('promotion is not event-date safe')
 promo={r['accession_number']:r for r in _csv(paths['PROMOTION_LEDGER'])}
 rows=_csv(paths['V1_CORPUS']); changed=0
 for row in rows:
  evidence=promo.get(row['accession_number'])
  if not evidence:continue
  if row['identity_status'] not in {'UNMAPPED','AMBIGUOUS'} or row['cik']!=evidence['cik'] or row['filing_date']!=evidence['filing_date']:raise Sec8KHardAdverseCorpusV2Error('promotion conflicts with V1 corpus')
  row['canonical_symbol_at_filing']=evidence['approved_symbol']; row['identity_status']='SEC_PRIMARY_DOCUMENT_REVIEWED'; changed+=1
 counts=Counter(r['identity_status'] for r in rows); exp=p['expected']
 mapped=sum(v for k,v in counts.items() if k not in {'UNMAPPED','AMBIGUOUS'})
 if len(rows)!=exp['events'] or changed!=exp['new_promotions'] or mapped!=exp['mapped_after_merge']:raise Sec8KHardAdverseCorpusV2Error('V2 coverage count changed')
 return rows,{'report_version':p['protocol_version'],'status':'HARD_ADVERSE_CORPUS_V2_IDENTITY_COVERAGE_UPDATED','events':len(rows),'newly_mapped_events':changed,'mapped_events':mapped,'unmapped_events':counts['UNMAPPED'],'ambiguous_events':counts['AMBIGUOUS'],'identity_status_counts':dict(sorted(counts.items())),'price_outcomes_opened':False,'direction_hypothesis_allowed':False,'blind_holdout_access':False,'operational_action_ratio':0.0,'next_stage':p['next_stage']}
def run():
 p=json.loads(PROTOCOL.read_text(encoding='utf-8')); rows,report=build(); out=_rooted(p['outputs']['ledger'])
 with out.open('w',newline='',encoding='utf-8') as h:
  w=csv.DictWriter(h,fieldnames=list(rows[0]),lineterminator='\n');w.writeheader();w.writerows(rows)
 report['ledger_path']=p['outputs']['ledger'];report['ledger_sha256']=_sha(out); rp=_rooted(p['outputs']['report']);rp.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');return report
if __name__=='__main__':print(json.dumps(run(),ensure_ascii=False,indent=2))
