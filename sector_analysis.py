"""Evidence-qualified value-chain comparison. No composite stock ranking."""
import argparse,itertools,json
from pathlib import Path
from datetime import datetime,timezone
GATES=("physical_difficulty","qualified_supplier_scarcity","switching_cost","economic_capture","durability")
def validate(d):
 sources={s["id"] for s in d["sources"]}
 symbols=[c["ticker"] for c in d["companies"]]
 if len(symbols)!=len(set(symbols)):raise ValueError("Duplicate company")
 for c in d["companies"]:
  if not c["source_ids"] or not set(c["source_ids"])<=sources:raise ValueError("Missing evidence")
  if set(c["bottleneck_evidence"])!=set(GATES):raise ValueError("Missing bottleneck gate")
  if any(x not in ("supported","unknown","contradicted") for x in c["bottleneck_evidence"].values()):raise ValueError("Invalid gate")
  for key in ("proof_needed","alternatives","falsifier"):
   if not c.get(key):raise ValueError("Missing counter-case")
 for s in d["scenarios"]:
  if s["type"]!="conditional_scenario" or s["probability"] is not None or s["stock_return"] is not None:raise ValueError("Unsupported quantified forecast")
  if not set(s["source_ids"])<=sources:raise ValueError("Unknown scenario source")
  if [x["order"] for x in s["steps"]]!=[1,2,3]:raise ValueError("Three ordered mechanisms required")
  if any(not x.get(k) for x in s["steps"] for k in ("mechanism","condition","falsifier")):raise ValueError("Unfalsifiable causal step")
 return d
def pairs(d):
 return [{"a":a["ticker"],"b":b["ticker"],"overlap":sorted(set(a["cohorts"])&set(b["cohorts"])),
          "interpretation":"potential product-level comparison; no blanket substitution or supply relationship inferred"}
         for a,b in itertools.combinations(d["companies"],2) if set(a["cohorts"])&set(b["cohorts"])]
def bottleneck(c):
 failed=[k for k,v in c["bottleneck_evidence"].items() if v=="contradicted"]
 unknown=[k for k,v in c["bottleneck_evidence"].items() if v=="unknown"]
 return {"result":"contradicted" if failed else "unproven" if unknown else "supported_candidate_not_monopoly",
         "unknown":unknown,"contradicted":failed}
def render(d):
 validate(d);src={s["id"]:s for s in d["sources"]}
 link=lambda ids:" ".join("["+i+"]("+src[i]["url"]+")" for i in ids)
 lines=["# Photonics: find the bottleneck before choosing the stock",
 "The five companies are not five substitutes. A supplier, manufacturer and industrial-laser business can react differently to the same technology shift.",
 "","## Start from the job"]
 lines+=["- "+x for x in d["first_principles"]]
 lines+=["","## Value chain and evidence gaps"]
 for c in d["companies"]:
  lines += [f"### {c['ticker']}",c["role"]+" "+link(c["source_ids"]),
   "Research hypothesis: "+c["constraint"],"What would establish an advantage: "+c["proof_needed"],
   "Alternative route: "+c["alternatives"],"What breaks the thesis: "+c["falsifier"],
   "Bottleneck verdict: "+bottleneck(c)["result"]+". Technical capability is not monopoly proof.",""]
 lines+=["## Head-to-head scope"]
 for p in pairs(d):lines.append(f"- {p['a']} / {p['b']}: "+", ".join(p["overlap"])+". Match specific products and customer requirements before comparing.")
 lines+=["- Fabrinet is a manufacturing-layer comparison, not a direct substitution for every branded optical supplier.",
 "- IPG belongs primarily in an industrial-process cohort, not an AI-network optics ranking.","","## Conditional second- and third-order pathways"]
 for s in d["scenarios"]:
  lines += ["### "+s["trigger"],"Scenario, not an observed forecast. "+link(s["source_ids"])]
  for st in s["steps"]:lines.append(f"{st['order']}. {st['mechanism']} Only if: {st['condition']} Breaks if: {st['falsifier']}")
 lines += ["","## Separate company advantage from stock attractiveness",
 "No stock winner is selected. A scarce capability may already be overvalued; rising volume can coexist with price erosion, dilution or weak cash conversion. Next compare sourced expectations and a coherent price/capital snapshot, not technical prestige.",
 "","## Evidence discipline",
 "Source descriptions establish capabilities. Bottleneck conditions and causal pathways are analyst hypotheses requiring tests. Pages with unknown publication time are capture-only; this sector map is not historical backtest evidence."]
 for s in d["sources"]:lines.append("- "+s["id"]+": "+s["locator"]+". "+s["summary"]+" "+s["url"])
 return "\n".join(lines)+"\n"
if __name__=="__main__":
 p=argparse.ArgumentParser();p.add_argument("input",nargs="?",default="examples/photonics_sector.json");p.add_argument("--output",default="outputs/sector");a=p.parse_args()
 d=validate(json.loads(Path(a.input).read_text(encoding="utf-8-sig")));out=Path(a.output);out.mkdir(parents=True,exist_ok=True)
 (out/"PHOTONICS_VALUE_CHAIN.md").write_text(render(d),encoding="utf-8")
 (out/"comparison.json").write_text(json.dumps({"pairs":pairs(d),"bottlenecks":{c["ticker"]:bottleneck(c) for c in d["companies"]},"stock_ranking":None},indent=2),encoding="utf-8")
 print("Saved evidence-qualified sector map and comparisons; no stock ranking.")

