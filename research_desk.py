"""AutoNext local evidence-to-analysis desk. No trading, hosted server or credentials."""
import argparse
from contextlib import closing
from datetime import datetime, timezone
from html import escape
import hashlib
import json
from pathlib import Path
import sqlite3
import urllib.request
import autonext as a
from sec_ledger import normalize, changes
from sec_adapter import COMPANIES

ROOT=Path(__file__).resolve().parent
STYLE='''body{margin:0;background:#f2f5fa;color:#172c48;font:16px/1.5 system-ui,sans-serif}main{max-width:1150px;margin:auto;padding:32px}h1{font-size:34px;margin-bottom:8px}h2{font-size:23px}h3{font-size:18px}a{color:#185abe}header{background:#132d50;color:white;padding:28px;border-radius:12px}article,section{background:white;padding:24px;margin:20px 0;border-radius:12px;border:1px solid #dce3ec}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:16px}.grid article{margin:0}table{border-collapse:collapse;width:100%;font-size:14px}td,th{text-align:left;padding:10px;border-bottom:1px solid #e0e6ed}small,.muted{color:#5c6b7a}.notice{padding:14px;border-left:4px solid #b97819;background:#fff7e7}pre{white-space:pre-wrap;overflow-wrap:anywhere;font:13px/1.5 ui-monospace,monospace}summary{cursor:pointer;font-weight:600}button,input{padding:9px;font:inherit}footer{font-size:13px;margin-top:28px}'''

def page(title,body):
    return '<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'+escape(title)+'</title><style>'+STYLE+'</style><main>'+body+'</main></html>'

def safe_link(url,title):
    if not url.startswith(('https://','http://')): return escape(title)
    return '<a rel="noreferrer" href="'+escape(url,quote=True)+'">'+escape(title)+'</a>'

def read_json(path): return json.loads(Path(path).read_text(encoding='utf-8-sig'))

def archived_bundle(symbol,archive):
    receipts=[read_json(f) for f in archive.glob('*.receipt.json')]
    selected=[];data=[]
    for kind in ('submissions','companyfacts'):
        r=max((r for r in receipts if r['cik']==COMPANIES[symbol] and r['kind']==kind),key=lambda r:a.timestamp(r['captured_at']))
        file=(archive/r['raw_file']).resolve()
        if file.parent!=archive.resolve(): raise ValueError('Archive path escaped its directory')
        raw=file.read_bytes()
        if hashlib.sha256(raw).hexdigest()!=r['sha256']: raise ValueError('Archive integrity failure')
        data.append(json.loads(raw));selected.append(r)
    return normalize(*data,selected,symbol)

def quote_bundle(security,raw,captured):
    meta=json.loads(raw)['chart']['result'][0]['meta']
    if meta['symbol']!=security['ticker'] or meta['currency']!=security['currency'] or meta['instrumentType']!='EQUITY': raise ValueError('Quote identity mismatch')
    exchange=meta.get('exchangeName')
    allowed={'NASDAQ':{'NMS','NGM','NCM'},'NYSE':{'NYQ'}}
    if exchange not in allowed.get(security['exchange'],set()): raise ValueError('Quote exchange mismatch')
    price=a.number(meta['regularMarketPrice'],'regularMarketPrice',0)
    if price<=0: raise ValueError('Price must be positive')
    observed=datetime.fromtimestamp(meta['regularMarketTime'],timezone.utc)
    age=(a.timestamp(captured)-observed).total_seconds()
    if not 0<=age<=7*86400: raise ValueError('Quote stale more than seven days or future dated')
    # Current regular-market quote, NOT historically adjusted close.
    sid='yahoo-quote-'+security['ticker']+'-'+hashlib.sha256(raw).hexdigest()[:20]
    source={'id':sid,'title':security['ticker']+' provider regular-market quote','visibility':'public',
        'locator':'https://finance.yahoo.com/quote/'+security['ticker']+'/',
        'published_at':observed.isoformat(),'captured_at':captured,
        'excerpt':f"Yahoo chart metadata: symbol {meta['symbol']}, currency {meta['currency']}, exchange {exchange}; regularMarketPrice {price}, regularMarketTime {meta['regularMarketTime']}. Identity/time/domain checked; single provider, not independently reconciled. Not an adjusted historical quote."}
    rows=[]
    for pe in (15,25,35):
        for factor in (1,1.2):
            rows.append({'id':sid+f'-pe{pe}-shares{factor}','known_at':captured,'source_ids':[sid],
                'price_observation':{'price':price,'observed_at':observed.isoformat(),'captured_at':captured,
                    'security_id':security['id'],'currency':security['currency'],'source_id':sid,'verified':True,
                    'adjustment_basis':'unadjusted_per_current_share'},
                'scenario':{'years':5,'required_return':.1,'terminal_pe':pe,'future_share_factor':factor,
                    'rationale':'Illustrative sensitivity grid: five-year horizon and 10% required return; terminal P/E 15/25/35 and future shares 1.0/1.2x. These are analysis assumptions, not sourced forecasts or recommended fair multiples. No interim dividends.'}})
    return a.validate({'security':security,'sources':[source],'claims':[],'expectations':[],'catalysts':[],'valuations':[],'earnings_scenarios':rows})

def fetch_quote(security,out):
    url='https://query1.finance.yahoo.com/v8/finance/chart/'+security['ticker']+'?range=5d&interval=1d'
    with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0 AutoNext research'}),timeout=25) as response:
        raw=response.read(2000001)
    if len(raw)>2000000: raise ValueError('Oversized price response')
    now=datetime.now(timezone.utc).isoformat(); bundle=quote_bundle(security,raw,now)
    (out/'quote.json').write_bytes(raw)
    (out/'quote-receipt.json').write_text(json.dumps({'url':url,'captured_at':now,'sha256':hashlib.sha256(raw).hexdigest()},indent=2))
    return bundle

def company_html(run,delta,price_error):
    s=run['security']; symbol=s['ticker']
    text='<p><a href="../index.html">← Research desk</a></p><header><h1>'+escape(symbol+' · '+s['company'])+'</h1><p>Evidence → business change → price-implied hurdle → unresolved questions</p></header>'
    text+='<p class="muted">Captured-mode snapshot '+escape(run['as_of'])+' · '+escape(run['run_id'])+'</p>'
    text+='<div class="notice">Research, not a recommendation. No automated quality score or buy/sell ranking. Company revenue does not prove a particular product moat.</div>'
    text+='<section><h2>1. What changed in the business?</h2>'
    latest={}
    for e in run['expectations']:
        if 'release-' in e['id'] and e['kind']=='observed_result': latest[(e['metric'],e['basis'])]=e
    if latest:
        text+='<table><tr><th>Metric / basis</th><th>Period</th><th>Reported value</th></tr>'
        for e in latest.values(): text+='<tr><td>'+escape(e['metric']+' / '+e['basis'])+'</td><td>'+escape(e['period'])+'</td><td>'+escape(f"{e['value']:,.2f} {e['unit']}")+'</td></tr>'
        text+='</table><p class="muted">Manually sourced release observations; GAAP/basic and adjusted/diluted are intentionally separate.</p>'
    for c in delta['sequential_changes'][:6]:
        text+='<p>'+escape(f"{c['metric']}: {c['old']:,.0f} → {c['new']:,.0f} {c['unit']}. {c['old_period']} vs {c['new_period']}; {c['comparison']}; {c['basis']}")+'</p>'
    text+='<p>'+escape(f"{len(delta['revisions'])} revised fact series; {len(delta['ambiguous_facts'])} ambiguous series excluded from change calculations.")+'</p></section>'
    text+='<section><h2>2. What does this price require?</h2>'
    if price_error: text+='<p class="notice">'+escape(price_error)+'</p>'
    if run['earnings_analysis']:
        p=run['earnings_analysis'][0]['input']['price_observation']
        text+='<p>'+escape(f"Provider regular-market quote: {p['price']:.2f} {p['currency']}; observed {p['observed_at']}. Single-provider checked, not independently reconciled.")+'</p>'
        text+='<p>Illustrative five-year hurdle at 10% required annual return. No earnings forecast is invented. More shares increase total earnings needed, not the per-future-share hurdle.</p><table><tr><th>Terminal P/E assumption</th><th>Future shares</th><th>Required terminal EPS</th><th>Total earnings per current share</th></tr>'
        for item in run['earnings_analysis']:
            v=item['input']['scenario'];r=item['result']
            if r['status']=='blocked':continue
            text+=f"<tr><td>{v['terminal_pe']}×</td><td>{v['future_share_factor']}×</td><td>{r['required_terminal_eps']:.2f}</td><td>{r['required_total_earnings_per_current_share']:.2f}</td></tr>"
        text+='</table>'
    else: text+='<p>No eligible checked current quote. Valuation abstains.</p>'
    text+='</section><section><h2>3. What is still unproven?</h2><ul><li>Which qualified product bottleneck creates durable pricing power?</li><li>Does growth convert to cash after capex, working capital, tax and dilution?</li><li>Can a defensible operating forecast clear the price-implied hurdle?</li><li>What competitor, customer qualification or architecture change would break this case?</li></ul><p>These are diligence questions, not automatically answered conclusions.</p></section>'
    text+='<section><h2>4. Evidence and audit trail</h2><p><a href="run.json">Snapshot JSON</a> · <a href="report.md">Complete Markdown</a> · <a href="changes.json">Fact changes</a></p>'
    text+='<details><summary>Read all retained source excerpts ('+str(len(run['sources']))+')</summary>'
    for source in run['sources']:
        text+='<p>'+safe_link(source['locator'],source['title'])+'<br><small>'+escape(source['published_at'])+'</small><br>'+escape(source['excerpt'])+'</p>'
    return page(symbol,text+'</details></section>')

def build(output,refresh_prices=False):
    output=Path(output).resolve();output.mkdir(parents=True,exist_ok=False)
    archive=ROOT/'outputs/sec/archive'; manifest={'created_at':datetime.now(timezone.utc).isoformat(),'companies':[]}
    with closing(a.connect(output/'research.sqlite')) as db:
        for symbol in COMPANIES:
            target=output/symbol;target.mkdir()
            try:
                bundle=archived_bundle(symbol,archive);a.ingest(db,bundle)
                extra=ROOT/'examples/primary_operating_20261117'/(symbol+'.json')
                if extra.exists(): a.ingest(db,read_json(extra))
                price_error='Price refresh not requested. No stale price silently substituted.'
                if refresh_prices:
                    try:
                        price=fetch_quote(bundle['security'],target);a.ingest(db,price);price_error=''
                    except Exception as exc: price_error='Quote unavailable: '+str(exc)
                run=a.build_run(db,bundle['security']['id'],datetime.now(timezone.utc).isoformat(),'captured');delta=changes(run)
                (target/'run.json').write_text(json.dumps(run,indent=2),encoding='utf-8')
                (target/'changes.json').write_text(json.dumps(delta,indent=2),encoding='utf-8')
                (target/'report.md').write_text(a.report(run),encoding='utf-8')
                (target/'index.html').write_text(company_html(run,delta,price_error),encoding='utf-8')
                manifest['companies'].append({'symbol':symbol,'status':'ok','sources':len(run['sources']),'quote_status':price_error or 'provider_checked','run_id':run['run_id']})
            except Exception as exc: manifest['companies'].append({'symbol':symbol,'status':'failed','error':str(exc)})
    body='<header><h1>AutoNext · public-market research</h1><p>Separate technical promise, business capture and the price you pay.</p></header><p>'+escape(manifest['created_at'])+'</p><div class="notice">Five-company research desk, not a comprehensive screener. Archived SEC facts + manually reviewed releases. Refresh dates and gaps remain visible.</div><h2>Explore the evidence</h2><div class="grid">'
    for item in manifest['companies']:
        body+='<article><h2>'+escape(item['symbol'])+'</h2>'
        if item['status']=='ok':body+='<p>'+str(item['sources'])+' retained sources</p><p>'+escape('Current quote available · single provider' if item['quote_status']=='provider_checked' else item['quote_status'])+'</p><a href="'+item['symbol']+'/index.html">Open company analysis →</a>'
        else:body+='<p>'+escape(item['error'])+'</p>'
        body+='</article>'
    body+='</div><section><h2>Does the historical pattern work?</h2><p>The exploratory revenue-growth proxy does not establish a robust edge. It is not a test of the full bottleneck/valuation thesis.</p>'
    pilot=ROOT/'outputs/historical-pilot/REPORT.md'
    if pilot.exists():
        (output/'historical-pilot.md').write_text(pilot.read_text(),encoding='utf-8')
        body+='<details><summary>Read pilot results and limitations</summary><pre>'+escape(pilot.read_text())+'</pre></details>'
    sector=ROOT/'outputs/sector/PHOTONICS_VALUE_CHAIN.md'
    if sector.exists():
        (output/'value-chain.md').write_text(sector.read_text(encoding='utf-8-sig'),encoding='utf-8')
        body+='<p><a href="value-chain.md">Company-specific value-chain hypotheses and falsifiers</a></p>'
    body+='</section><section><h2>Scope and next decisions</h2><p>Use company pages to inspect filed changes, test price-implied hurdles and decide what evidence to gather next. No licensed consensus, automated thesis committee, fully audited historical universe, portfolio allocation, alerts or execution is implied.</p><p><a href="manifest.json">Run manifest</a> · Local SQLite evidence ledger: research.sqlite</p></section>'
    (output/'index.html').write_text(page('AutoNext research desk',body),encoding='utf-8')
    (output/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    return manifest

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',default=str(ROOT/'outputs'/('desk-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S'))))
    p.add_argument('--refresh-prices',action='store_true',help='Fetch current single-provider regular-market quotes; abstain on failures')
    args=p.parse_args(); result=build(args.output,args.refresh_prices);print(json.dumps(result,indent=2));print('Open '+str(Path(args.output).resolve()/'index.html'))
    return int(any(x['status']!='ok' for x in result['companies']))
if __name__=='__main__': raise SystemExit(main())
