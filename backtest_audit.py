"""Evidence replay audit, NOT a portfolio-return backtest. Standard library only."""
import argparse
from contextlib import closing
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
import autonext

CATEGORIES = ('claims', 'expectations', 'catalysts', 'valuations', 'earnings_scenarios')

def audit(db_path, cutoffs):
    dates = sorted(set(cutoffs), key=autonext.timestamp)
    if not dates:
        raise ValueError('At least one cutoff is required')
    # build_run records runs; isolate those writes from the original ledger.
    uri = Path(db_path).resolve().as_uri() + '?mode=ro'
    with closing(sqlite3.connect(uri, uri=True)) as source, closing(sqlite3.connect(':memory:')) as db:
        source.backup(db)
        inventory, snapshots = [], []
        ids = [r[0] for r in db.execute('SELECT DISTINCT security_id FROM bundles ORDER BY security_id')]
        for sid in ids:
            bundles = [json.loads(r[0]) for r in db.execute('SELECT payload FROM bundles WHERE security_id=?', (sid,))]
            sources = {s['id']:s for b in bundles for s in b['sources']}
            expectations = {r['id']:r for b in bundles for r in b['expectations']}
            inventory.append({'security_id':sid, 'sources':len(sources), 'expectations':len(expectations),
                'earliest_publication': min((s['published_at'] for s in sources.values()), key=autonext.timestamp, default=None),
                'earliest_capture':min((s['captured_at'] for s in sources.values()), key=autonext.timestamp, default=None),
                'guidance_rows':sum(r['kind']=='management_guidance' for r in expectations.values())})
            for cutoff in dates:
                for mode in ('published', 'captured'):
                    run = autonext.build_run(db, sid, cutoff, mode)
                    limit = autonext.timestamp(cutoff)
                    for s in run['sources']:
                        if autonext.timestamp(s['published_at']) > limit or (mode=='captured' and autonext.timestamp(s['captured_at']) > limit):
                            raise AssertionError('Future source leaked into replay')
                    allowed = {s['id'] for s in run['sources']}
                    for category in CATEGORIES:
                        for row in run[category]:
                            if autonext.timestamp(row['known_at']) > limit or not set(row['source_ids']) <= allowed:
                                raise AssertionError('Future row leaked into replay')
                    snapshots.append({'security_id':sid, 'as_of':run['as_of'], 'mode':mode,
                        'run_id':run['run_id'], 'source_count':len(run['sources']),
                        'expectation_count':len(run['expectations']),
                        'comparison_count':len(run['expectation_comparisons']),
                        'comparisons':run['expectation_comparisons']})
    return {'status':'evidence_replay_only', 'generated_at':datetime.now(timezone.utc).isoformat(),
        'portfolio_return':None, 'leakage_checks_passed':True, 'inventory':inventory, 'snapshots':snapshots,
        'limitations':[
            'No frozen selection, entry, exit or position-sizing rule: AutoNext currently records research, not a trading strategy.',
            'Five retrospectively selected surviving securities; not a historical membership or delisting-complete universe.',
            'Published replay uses late-collected evidence. Captured replay tests retained-source availability, not when human judgments were actually formed.',
            'No verified historical total-return prices, corporate actions, delisting proceeds or benchmark series in this dataset.',
            'No return or predictive performance inferred from guidance-versus-actual comparisons.']}

def markdown(result):
    lines=['# AutoNext historical replay audit', '', '**Evidence replay completed. Investment performance NOT tested.**', '',
        'No future-dated sources or rows were found in the tested snapshots.', '',
        '| Security | Evidence rows | Guidance rows | Earliest capture |', '|---|---:|---:|---|']
    for row in result['inventory']:
        lines.append(f"| {row['security_id']} | {row['expectations']} | {row['guidance_rows']} | {row['earliest_capture']} |")
    lines += ['', '## Replay coverage', '| Security | Cutoff | Mode | Sources | Evidence rows | Comparisons |', '|---|---|---|---:|---:|---:|']
    for row in result['snapshots']:
        lines.append(f"| {row['security_id']} | {row['as_of'][:10]} | {row['mode']} | {row['source_count']} | {row['expectation_count']} | {row['comparison_count']} |")
    lines += ['', '## Why this cannot establish a profitable pattern'] + ['- '+x for x in result['limitations']]
    lines += ['', 'See docs/BACKTEST_PROTOCOL.md for the next experiment. No trades placed.']
    return '\n'.join(lines)+'\n'

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--db', required=True)
    p.add_argument('--as-of', action='append', required=True)
    p.add_argument('--output', required=True, help='New output filename stem')
    a=p.parse_args()
    result=audit(a.db,a.as_of)
    Path(a.output+'.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    Path(a.output+'.md').write_text(markdown(result),encoding='utf-8')
    print(f"Audited {len(result['snapshots'])} snapshots; no investment-return claim.")
