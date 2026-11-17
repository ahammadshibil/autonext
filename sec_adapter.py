"""Read-only SEC public filing adapter; immutable captures, no investment advice."""
import argparse
import hashlib
import json
import math
import re
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path
from autonext import timestamp, canonical

COMPANIES = {"COHR":820318, "LITE":1633978, "IPGP":1111928, "FN":1408710, "AAOI":1158114}
METRICS = {"revenue": ["RevenueFromContractWithCustomerExcludingAssessedTax","SalesRevenueNet","Revenues"],
           "cash": ["CashAndCashEquivalentsAtCarryingValue"],
           "shares": ["CommonStockSharesOutstanding"]}
class SecClient:
    def __init__(self, root, user_agent):
        if len(user_agent.strip()) < 10:
            raise ValueError("A descriptive SEC User-Agent is required")
        self.root = Path(root); self.root.mkdir(parents=True, exist_ok=True)
        self.agent = user_agent; self.last = 0
    def fetch(self, cik, kind):
        if not isinstance(cik,int) or cik <= 0 or kind not in ("submissions","companyfacts"):
            raise ValueError("Invalid SEC request")
        path = f"submissions/CIK{cik:010}.json" if kind == "submissions" else f"api/xbrl/companyfacts/CIK{cik:010}.json"
        url = "https://data.sec.gov/" + path
        # Serial local client, maximum 2 requests/sec, not a distributed limiter.
        for attempt in range(3):
            time.sleep(max(0, .5-(time.monotonic()-self.last))); self.last=time.monotonic()
            try:
                req=urllib.request.Request(url,headers={"User-Agent":self.agent,"Accept":"application/json"})
                with urllib.request.urlopen(req,timeout=30) as r:
                    raw=r.read(30_000_001)
                break
            except urllib.error.HTTPError as e:
                if e.code not in (429,500,502,503,504) or attempt==2: raise
                delay=e.headers.get("Retry-After","")
                time.sleep(min(60,max(2**(attempt+1),int(delay) if delay.isdigit() else 0)))
        if len(raw)>30_000_000: raise ValueError("Oversized SEC response")
        data=json.loads(raw)
        if int(data.get("cik",-1)) != cik: raise ValueError("SEC identity mismatch")
        sha=hashlib.sha256(raw).hexdigest()
        target=self.root/(sha+".json")
        if target.exists():
            if target.read_bytes()!=raw: raise ValueError("Archive hash collision")
        else:
            with target.open("xb") as f: f.write(raw)
        receipt={"url":url,"cik":cik,"kind":kind,"captured_at":datetime.now(timezone.utc).isoformat(),
                 "sha256":sha,"raw_file":target.name}
        # Each fetch gets an independent receipt, even when bytes are unchanged.
        name=hashlib.sha256(canonical(receipt).encode()).hexdigest()
        with (self.root/(name+".receipt.json")).open("x",encoding="utf-8") as f: json.dump(receipt,f,indent=2)
        return data,receipt

def filing_rows(submissions, cutoff):
    r=submissions.get("filings",{}).get("recent",{})
    n=len(r.get("accessionNumber",[])); out=[]
    if any(len(v)!=n for v in r.values() if isinstance(v,list)):
        raise ValueError("Malformed SEC column arrays")
    for i in range(n):
        row={k:v[i] for k,v in r.items() if isinstance(v,list)}
        accepted=row.get("acceptanceDateTime")
        if accepted and timestamp(accepted)<=timestamp(cutoff):
            out.append(row)
    return sorted(out,key=lambda r:timestamp(r["acceptanceDateTime"]),reverse=True)

def build_research(submissions, facts, receipts, cutoff, mode="published"):
    timestamp(cutoff)
    if int(submissions["cik"]) != int(facts["cik"]): raise ValueError("Mixed companies")
    if mode not in ("published","captured"): raise ValueError("Invalid as-of mode")
    if mode=="captured" and any(timestamp(r["captured_at"])>timestamp(cutoff) for r in receipts):
        raise ValueError("Captured snapshot was unavailable at this cutoff")
    rows=filing_rows(submissions,cutoff)
    accepted={r["accessionNumber"]:r for r in rows}
    cik=int(submissions["cik"])
    for row in rows:
        doc=row.get("primaryDocument","")
        if doc and any(part in ("", ".", "..") or not re.fullmatch(r"[A-Za-z0-9_.-]+",part) for part in doc.split("/")): raise ValueError("Unsafe SEC document path")
        acc=row["accessionNumber"]
        if not re.fullmatch(r"\d{10}-\d{2}-\d{6}",acc): raise ValueError("Invalid accession")
        row["url"]=f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc.replace('-','')}/{doc}"
    selected={}
    for metric,tags in METRICS.items():
        candidates=[]
        for tag in tags:
            item=facts.get("facts",{}).get("us-gaap",{}).get(tag,{})
            unit="shares" if metric=="shares" else "USD"
            for f in item.get("units",{}).get(unit,[]):
                filing=accepted.get(f.get("accn"))
                if not filing or not f.get("end") or f["end"]>timestamp(cutoff).date().isoformat(): continue
                if isinstance(f.get("val"),bool) or not isinstance(f.get("val"),(int,float)) or not math.isfinite(f["val"]): continue
                # Preserve duration, accession, form, taxonomy. Never infer quarterly from YTD.
                candidates.append({**f,"tag":tag,"unit":unit,"accepted_at":filing["acceptanceDateTime"],"source":filing["url"]})
        # Most recent economic period, then latest disclosure known at cutoff; no summed tags.
        candidates.sort(key=lambda x:(x["end"],timestamp(x["accepted_at"])),reverse=True)
        if candidates:
            newest=candidates[0]["end"]
            selected[metric]=[r for r in candidates if r["end"]==newest][:12]
        else: selected[metric]=[]
    return {"company":submissions["name"],"cik":cik,"tickers":submissions.get("tickers",[]),
            "as_of":cutoff,"mode":mode,"receipts":receipts,"filings":[r for r in rows if r["form"] in ("10-K","10-Q","8-K","20-F","6-K","10-K/A","10-Q/A")][:12],"metrics":selected,
            "price":None,"valuation_status":"blocked: no verified market-price and coherent capital snapshot",
            "limits":["Recent submissions only; older archive pages not yet ingested.",
                      "Fact candidates are not normalized financial statements. Durations and restatements are retained.",
                      "Published mode reconstructs from a later capture, not a contemporaneous backtest.",
                      "Company-wide facts do not establish an individual product's commercial validation.",
                      "SEC data is public; exchange price licensing is separate. No guessed or synthetic live price."]}

def render(r):
    lines=[f"# {r['company']}: evidence desk",f"As of {r['as_of']} ({r['mode']})","",
           "## What can I verify?"]
    for metric,rows in r["metrics"].items():
        lines += [f"### {metric.title()}"]
        if not rows: lines += ["No eligible SEC fact in this captured recent-filings window."]; continue
        seen=set()
        for f in rows:
            key=(f.get("start"),f["end"],f["val"],f["tag"])
            if key in seen: continue
            seen.add(key)
            period=f.get("start","Instant")+" to "+f["end"]
            lines += [f"- {f['val']:,.0f} {f['unit']} | {period} | {f['tag']} | [{f['form']}]({f['source']}) | accepted {f['accepted_at']}"]
    lines += ["","## What changed in disclosures?"]
    lines += [f"- {f['acceptanceDateTime']} [{f['form']}]({f['url']}) | period {f.get('reportDate','')}" for f in r["filings"]]
    lines += ["","## What cannot be concluded?",r["valuation_status"]]+["- "+s for s in r["limits"]]
    return "\n".join(lines)+"\n"

def refresh(symbols, output, user_agent, as_of):
    symbols=list(COMPANIES) if symbols is None else [str(symbol).upper() for symbol in symbols]
    unknown=[symbol for symbol in symbols if symbol not in COMPANIES]
    if unknown: raise ValueError("Unknown SEC symbols: "+", ".join(unknown))
    timestamp(as_of)
    root=Path(output);root.mkdir(parents=True,exist_ok=True)
    client=SecClient(root/"archive",user_agent);results=[]
    for symbol in symbols:
        try:
            sub,sr=client.fetch(COMPANIES[symbol],"submissions")
            if symbol not in sub.get("tickers",[]): raise ValueError("Ticker/CIK mismatch")
            facts,fr=client.fetch(COMPANIES[symbol],"companyfacts")
            r=build_research(sub,facts,[sr,fr],as_of)
            suffix=hashlib.sha256(canonical(r).encode()).hexdigest()[:12]
            stem=root/(symbol+"-"+suffix)
            stem.with_suffix(".json").write_text(json.dumps(r,indent=2),encoding="utf-8")
            stem.with_suffix(".md").write_text(render(r),encoding="utf-8")
            results.append({"symbol":symbol,"status":"ok","report":str(stem.with_suffix(".md")),"filings":len(r["filings"])})
        except (ValueError,KeyError,urllib.error.URLError,TimeoutError) as e:
            results.append({"symbol":symbol,"status":"failed","error":str(e)})
    return results

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--symbols",nargs="+",choices=COMPANIES,default=list(COMPANIES))
    p.add_argument("--output",default="outputs/sec")
    p.add_argument("--user-agent",required=True,help="Your identifying research application/contact string")
    p.add_argument("--as-of",default=datetime.now(timezone.utc).isoformat())
    args=p.parse_args()
    results=refresh(args.symbols,args.output,args.user_agent,args.as_of)
    print(json.dumps(results,indent=2))
    return 0 if all(r["status"]=="ok" for r in results) else 1
if __name__=="__main__": raise SystemExit(main())

