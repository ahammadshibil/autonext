"""Normalize archived SEC facts into AutoNext's local evidence ledger."""
import argparse
import hashlib
import json
from datetime import datetime,timezone,date
from pathlib import Path
from contextlib import closing
import autonext as a
from sec_adapter import COMPANIES, METRICS, filing_rows

def normalize(sub,facts,receipts,symbol):
 if int(sub["cik"])!=int(facts["cik"]) or symbol not in sub.get("tickers",[]): raise ValueError("Identity mismatch")
 idx=sub["tickers"].index(symbol)
 exchange=sub["exchanges"][idx].upper()
 if exchange=="NASDAQ": exchange="NASDAQ"
 security={"id":f"{exchange}:{symbol}:COMMON","company":sub["name"],"ticker":symbol,"exchange":exchange,
           "share_class":"common","currency":"USD","sector":"photonics"}
 # Preserve existing verified security identity for Coherent.
 if symbol=="COHR":
  security=json.loads(Path("examples/coherent_primary_sources.json").read_text(encoding="utf-8-sig"))["security"]
 captured=max(r["captured_at"] for r in receipts)
 rows=filing_rows(sub,captured); accepted={r["accessionNumber"]:r for r in rows}
 out={"security":security,"sources":[],"claims":[],"expectations":[],"catalysts":[],"valuations":[]}
 sources={}; seen=set()
 for metric,tags in METRICS.items():
  for tag in tags:
   unit="shares" if metric=="shares" else "USD"
   for f in facts.get("facts",{}).get("us-gaap",{}).get(tag,{}).get("units",{}).get(unit,[]):
    filing=accepted.get(f.get("accn"))
    if not filing or filing.get("form") not in ("10-K","10-Q","10-K/A","10-Q/A"):continue
    if not f.get("end") or f["end"]>a.timestamp(captured).date().isoformat():continue
    a.number(f["val"],"SEC fact")
    acc=f["accn"]; known=filing["acceptanceDateTime"]
    sid="sec-"+acc+"-"+a.digest(receipts)[:10]
    period=f.get("start","instant")+"/"+f["end"]
    identity=(tag,period,unit,acc,f["val"])
    if identity in seen:continue
    seen.add(identity)
    url=f"https://www.sec.gov/Archives/edgar/data/{int(sub['cik'])}/{acc.replace('-','')}/{filing['primaryDocument']}"
    sources[sid]={"id":sid,"title":sub["name"]+" "+filing["form"]+" "+acc,"locator":url,
                  "published_at":known,"captured_at":captured,"visibility":"public",
                  "excerpt":"Structured SEC XBRL facts retained in archived companyfacts JSON; values preserve taxonomy, unit, start/end, accession and acceptance time.",
                  "capture_receipts":receipts}
    out["expectations"].append({"id":"sec-fact-"+a.digest([identity,receipts])[:24],"known_at":known,"source_ids":[sid],
     "kind":"observed_result","metric":metric,"period":period,"unit":unit,"basis":"us-gaap:"+tag,"value":f["val"],
     "start":f.get("start"),"end":f["end"],"accession":acc,"form":filing["form"]})
 out["sources"]=list(sources.values())
 if symbol=="COHR":
  original=json.loads(Path("examples/coherent_primary_sources.json").read_text(encoding="utf-8-sig"))
  guidance=next(r for r in original["expectations"] if r["id"]=="cohr-guidance-revenue-q1")
  guidance={**guidance,"id":"cohr-guidance-revenue-q1-date-normalized-v1","period":"2026-07-01/2026-09-30","basis":"us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax","normalization_note":"Manual reviewed mapping: FY2027 Q1 to July-September 2026; consolidated revenue guide compared with SEC consolidated revenue. Not an EPS or non-GAAP mapping."}
  out["expectations"].append(guidance)
  out["sources"] += [r for r in original["sources"] if r["id"] in guidance["source_ids"]]
 a.validate(out);return out

def changes(run):
 # Keep latest disclosure for an exact accounting/period key. Conflicting same-time values are not silently resolved.
 groups={}
 for r in run["expectations"]:
  if r["kind"]!="observed_result" or "end" not in r:continue
  key=tuple(r[k] for k in ("metric","period","basis","unit"))
  groups.setdefault(key,[]).append(r)
 current=[]; revisions=[]; ambiguous=[]
 for key,rs in groups.items():
  rs.sort(key=lambda r:a.timestamp(r["known_at"]))
  latest_time=rs[-1]["known_at"]; latest=[r for r in rs if r["known_at"]==latest_time]
  if len({r["value"] for r in latest})>1:
   ambiguous.append({"key":key,"row_ids":[r["id"] for r in latest]});continue
  current.append(latest[-1])
  if rs[0]["value"]!=latest[-1]["value"]:
   revisions.append({"metric":key[0],"period":key[1],"basis":key[2],"first":rs[0]["value"],
                     "latest":latest[-1]["value"],"first_id":rs[0]["id"],"latest_id":latest[-1]["id"]})
 series={}
 for r in current:
  days=(date.fromisoformat(r["end"])-date.fromisoformat(r["start"])).days+1 if r.get("start") else None
  # Only instant or standalone quarters; do not compare YTD with a quarter.
  if days is not None and not 80<=days<=100:continue
  key=(r["metric"],r["basis"],r["unit"],"instant" if days is None else "quarter")
  series.setdefault(key,[]).append(r)
 comparisons=[]
 newest_by_metric={}
 for r in current: newest_by_metric[r["metric"]]=max(newest_by_metric.get(r["metric"],""),r["end"])
 for key,rs in series.items():
  rs.sort(key=lambda r:r["end"])
  if len(rs)<2:continue
  old,new=rs[-2:]
  if new["end"]!=newest_by_metric[new["metric"]]:continue
  if (a.timestamp(run["as_of"]).date()-date.fromisoformat(new["end"])).days>200:continue
  gap=(date.fromisoformat(new["end"])-date.fromisoformat(old["end"])).days
  if not (60<=gap<=120 or 350<=gap<=380):continue
  comparisons.append({"metric":key[0],"basis":key[1],"unit":key[2],"comparison":("sequential period" if gap<=120 else "year over year")+", not guidance beat",
    "old_period":old["period"],"new_period":new["period"],"old":old["value"],"new":new["value"],
    "change":new["value"]-old["value"],"percent":(new["value"]/old["value"]-1)*100 if old["value"]>0 else None,
    "old_id":old["id"],"new_id":new["id"]})
 return {"sequential_changes":comparisons,"revisions":revisions,"ambiguous_facts":ambiguous}

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument("--archive",default="outputs/sec/archive")
 p.add_argument("--db",default="outputs/public_companies.sqlite");p.add_argument("--output",default="outputs/ledger")
 args=p.parse_args(); root=Path(args.archive); dest=Path(args.output);dest.mkdir(parents=True,exist_ok=True)
 receipts=[json.loads(f.read_text()) for f in root.glob("*.receipt.json")]
 now=datetime.now(timezone.utc).isoformat(); overview=["# Five-company filing review","Actual period changes and explicitly sourced management-guidance comparisons. No market-consensus claims.",""]
 for symbol,cik in COMPANIES.items():
  rs=[max((r for r in receipts if r["cik"]==cik and r["kind"]==kind),key=lambda r:r["captured_at"]) for kind in ("submissions","companyfacts")]
  data=[]
  for r in rs:
   raw=(root/r["raw_file"]).read_bytes()
   if hashlib.sha256(raw).hexdigest()!=r["sha256"]:raise ValueError("Archive integrity failure")
   data.append(json.loads(raw))
  bundle=normalize(*data,rs,symbol)
  (dest/(symbol+"-bundle.json")).write_text(json.dumps(bundle,indent=2),encoding="utf-8")
  with closing(a.connect(args.db)) as db:
   a.ingest(db,bundle);run=a.build_run(db,bundle["security"]["id"],now,"captured")
  diff=changes(run)
  (dest/(symbol+"-run.json")).write_text(json.dumps(run,indent=2),encoding="utf-8")
  (dest/(symbol+"-changes.json")).write_text(json.dumps(diff,indent=2),encoding="utf-8")
  byid={r["id"]:r for r in run["expectations"]}; sources={s["id"]:s for s in run["sources"]}
  lines=[f"## {symbol}: {bundle['security']['company']}"]
  for c in diff["sequential_changes"]:
   source=sources[byid[c["new_id"]]["source_ids"][0]]["locator"]
   pct=f"{c['percent']:+.1f}%" if c["percent"] is not None else "percentage not meaningful"
   lines.append(f"- {c['metric']}: {c['old']:,.0f} to {c['new']:,.0f} {c['unit']} ({pct}; {c['comparison']}). {c['old_period']} versus {c['new_period']}. [Filing]({source})")
  for c in run["expectation_comparisons"]:
   lines.append(f"- Management revenue guidance: {c['range']}; filed actual {c['actual']:,.0f} {c['unit']}, {c['range_outcome']}. Difference from derived midpoint: {c['difference']:,.0f}. Not a consensus comparison.")
  lines.append(f"- {len(diff['revisions'])} revised fact series; {len(diff['ambiguous_facts'])} ambiguous series excluded. See changes JSON.")
  lines.append("- No market-expectations beat/miss inferred. Cash movements need financing/investing/operating cash-flow attribution; share-count changes need issuance/buyback context.")
  overview+=lines+[""]
 (dest/"FIVE_COMPANY_REVIEW.md").write_text("\n".join(overview),encoding="utf-8")
 print("\n".join(overview))
if __name__=="__main__": main()

