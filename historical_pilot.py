"""Exploratory survivor-cohort revenue-growth event study; NOT strategy validation."""
import bisect, hashlib, json, math, statistics, urllib.request
from datetime import datetime, timezone, date
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'outputs'/'historical-pilot'
TICKERS=('COHR','LITE','FN','AAOI','IPGP')
RULE={'signal':'standalone quarterly revenue year-on-year growth > 0', 'horizon_sessions':63,
      'entry':'first shared session strictly after SEC acceptance calendar date in New York; close',
      'one_way_cost_bps':25,'cohort':'five retrospectively selected current survivors',
      'start':'2019-01-01','end':'2025-12-31','benchmark':'SPY adjusted close',
      'status':'exploratory proxy, frozen before viewing outcomes; not full AutoNext thesis'}

def fetch(ticker):
    path=OUT/(ticker+'-yahoo.json')
    if not path.exists():
        url=f'https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?range=10y&interval=1d&events=div%2Csplits&includeAdjustedClose=true'
        raw=urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0'}),timeout=30).read()
        path.write_bytes(raw)
        (OUT/(ticker+'-receipt.json')).write_text(json.dumps({'url':url,'captured_at':datetime.now(timezone.utc).isoformat(),'sha256':hashlib.sha256(raw).hexdigest()}))
    data=json.loads(path.read_text())['chart']['result'][0]
    if data['meta']['symbol']!=ticker or data['meta']['currency']!='USD': raise ValueError('Security mismatch')
    series={datetime.fromtimestamp(t,ZoneInfo('America/New_York')).date():v for t,v in zip(data['timestamp'],data['indicators']['adjclose'][0]['adjclose']) if v is not None and math.isfinite(v) and v>0}
    return series

def quarterly(row):
    return row['kind']=='observed_result' and row['metric']=='revenue' and row['unit']=='USD' and 'start' in row and 70 <= (date.fromisoformat(row['end'])-date.fromisoformat(row['start'])).days <=105

def events(bundle):
    # Preserve accession-linked as-filed values. No current restated value substituted backward.
    rows=sorted([r for r in bundle['expectations'] if quarterly(r)],key=lambda r:(r['known_at'],r['id']))
    seen=set()
    for r in rows:
        end=date.fromisoformat(r['end']); key=(r['start'],r['end'],r['basis'])
        if key in seen: continue
        seen.add(key)
        known=datetime.fromisoformat(r['known_at'].replace('Z','+00:00')).astimezone(ZoneInfo('America/New_York')).date()
        if not RULE['start']<=known.isoformat()<=RULE['end'] or not 0<=(known-end).days<=100: continue
        prior=[p for p in rows if p['known_at']<=r['known_at'] and p['basis']==r['basis'] and 350<=(end-date.fromisoformat(p['end'])).days<=380 and p['value']>0]
        if not prior: continue
        p=max(prior,key=lambda p:p['known_at'])
        yield {'available_date':known.isoformat(),'period_end':r['end'],'growth':r['value']/p['value']-1,'actual_id':r['id'],'prior_id':p['id'],'basis':r['basis']}

def outcomes(bundle,prices,benchmark):
    calendar=sorted(set(prices)&set(benchmark)); result=[]
    seen_periods=set()
    for e in events(bundle):
        # Avoid duplicate taxonomy records being counted as independent events.
        if e['period_end'] in seen_periods: continue
        seen_periods.add(e['period_end'])
        i=bisect.bisect_right(calendar,date.fromisoformat(e['available_date'])); j=i+RULE['horizon_sessions']
        if j>=len(calendar): continue
        a,b=calendar[i],calendar[j]
        gross=prices[b]/prices[a]-1; bench=benchmark[b]/benchmark[a]-1
        c=RULE['one_way_cost_bps']/10000
        net=(1+gross)*(1-c)/(1+c)-1
        result.append({**e,'entry':a.isoformat(),'exit':b.isoformat(),'positive_growth':e['growth']>0,'gross_return':gross,'net_return':net,'benchmark_return':bench,'excess_net':net-bench})
    return result

def summary(rows):
    return {'n':len(rows),'mean_excess_net':statistics.mean(r['excess_net'] for r in rows) if rows else None,
            'median_excess_net':statistics.median(r['excess_net'] for r in rows) if rows else None,
            'outperform_fraction':statistics.mean(r['excess_net']>0 for r in rows) if rows else None}

def main():
    OUT.mkdir(exist_ok=True)
    # Write the declared rule before retrieving or analyzing outcomes.
    (OUT/'rule.json').write_text(json.dumps(RULE,indent=2))
    spy=fetch('SPY'); rows=[]
    for ticker in TICKERS:
        b=json.loads((ROOT/'outputs'/'ledger'/(ticker+'-bundle.json')).read_text())
        rows.extend(dict(r,ticker=ticker) for r in outcomes(b,fetch(ticker),spy))
    groups={name:summary([r for r in rows if r['positive_growth']==positive]) for name,positive in [('positive_growth',True),('nonpositive_growth',False)]}
    companies={t:summary([r for r in rows if r['ticker']==t and r['positive_growth']]) for t in TICKERS}
    sensitivity=summary([r for r in rows if r['positive_growth'] and r['ticker']!='AAOI'])
    result={'rule':RULE,'groups':groups,'positive_by_company':companies,'sensitivity_exclude_AAOI_positive':sensitivity,'events':rows}
    (OUT/'results.json').write_text(json.dumps(result,indent=2))
    lines=['# Exploratory revenue-growth pilot','','Not a validation of AutoNext or an investable portfolio backtest. Five current survivors were chosen retrospectively; observations overlap. No significance, CAGR or Sharpe claims.','',
      'Signal: positive as-filed standalone quarterly revenue growth versus the comparable year-ago quarter. 2019-2025 filing dates. Enter at the next shared trading-session close; hold 63 sessions. Stock returns include an assumed 25 bps per side; SPY buy-and-hold reference has no transaction costs.','',
      '| Group | Events | Mean net excess vs SPY | Median net excess | Beat SPY |','|---|---:|---:|---:|---:|']
    for k,v in groups.items():
        if v['n']: lines.append(f"| {k} | {v['n']} | {v['mean_excess_net']:.2%} | {v['median_excess_net']:.2%} | {v['outperform_fraction']:.1%} |")
    lines+=['','## Limitations','- This simple commercial-growth proxy is not the bottleneck/value-capture/price-implied-expectations thesis. No valuation signal is tested.',
      '- Survivor and industry-selection bias; IPGP is an industrial-laser exposure. No historical complete universe, delisted outcomes or sector-neutral matching.',
      '- Reconstructed current SEC Company Facts retain accession timestamps but original filings and restatement mappings have not been independently re-audited.',
      '- Yahoo adjusted close is a dividend/split-adjusted proxy, not an executable quote. Corporate actions, COHR/IIVI continuity and complex transactions require further reconciliation.',
      '- Quarterly periods are restricted to 70-105 days; annual/half-year periods are excluded rather than differenced. Sparse taxonomy-matched coverage is not randomly missing.',
      '- Return windows overlap; pooled observations are not independent. No optimized thresholds or claimed untouched holdout. No trades.',
      '', 'Sources: https://help.yahoo.com/kb/SLN28256.html ; archived SEC accession links in the existing ledger; raw Yahoo responses and SHA-256 receipts alongside this report.',
      'Historical-universe expansion lead: https://legacy2.solactive.com/ordinary-adjustment-solactive-epic-core-photonics-index-effective-date-20th-january-2025/ (not yet imported).']
    lines += ['', '## Outlier sensitivity', f"Excluding AAOI: {sensitivity['n']} positive-growth events; mean net excess {sensitivity['mean_excess_net']:.2%}, median {sensitivity['median_excess_net']:.2%}, outperform fraction {sensitivity['outperform_fraction']:.1%}. Diagnostic only, not a revised strategy. Pooled mean is heavily driven by AAOI."]
    (OUT/'REPORT.md').write_text('\n'.join(lines)+'\n')
    print(json.dumps({'groups':groups,'positive_by_company':companies},indent=2))

if __name__=='__main__': main()
