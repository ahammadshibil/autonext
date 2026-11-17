# AutoNext local research desk

## Start
From the project directory:

```console
python research_desk.py --refresh-prices
```

Open the printed `index.html` path in a browser. No server, login, dependency installation or API key is required. Omit `--refresh-prices` for a fully offline evidence-only run. Every run creates a new timestamped output directory and separate SQLite ledger; existing directories are refused rather than overwritten.

## What the integrated workflow does
1. Verify hashes of existing SEC raw archives; normalize filings with accession/acceptance provenance.
2. Import manually reviewed earnings releases for all five companies, keeping GAAP/basic/non-GAAP/diluted distinct.
3. Optionally fetch regular-market quotes from Yahoo; verify ticker, exchange, currency, instrument type, positivity, observation chronology and maximum seven-day age. Save raw response and SHA-256 receipt. Failures abstain and remain visible. Provider checks are not independent market-data authentication.
4. Produce captured-mode runs, fact changes and dated earnings-hurdle grids. The grid uses illustrative five-year/10% return assumptions, 15/25/35 terminal P/E and 1.0/1.2 future-share factors, NOT forecasts, consensus or fair-value recommendations.
5. Build a local HTML desk with company pages, source links/excerpts, complete Markdown/JSON reports, manifest, value-chain hypotheses and historical pilot limitations.

The quote is the current regular-market metadata price, not the historical adjusted-close series used by the pilot. It may be delayed. Its actual timestamp is displayed. No execution occurs.

## Refresh SEC evidence
The desk uses the newest hash-verified local receipts; it does not silently claim that old archives are current. To refresh, supply your identifying research contact string to the existing SEC adapter first:

```console
python sec_adapter.py --user-agent "Your research application and contact" --output outputs/sec
python research_desk.py --refresh-prices
```

Review the adapter's success/failure list; refresh may only succeed for some companies. Manual operating-release bundles are currently the five reviewed November 2026 releases. Updating those is separate; never change immutable source IDs in place. Read `examples/primary_operating_20261117` for their contract.

## Reproduce the historical experiment
```console
python historical_pilot.py
python -m unittest discover -s tests -v
```

The pilot uses a cached 2019-2025 retrospective five-survivor cohort, archived SEC rows and Yahoo adjusted prices. It tests a simple revenue-growth proxy, NOT the complete AutoNext thesis. See its report for costs, lag, overlapping windows, survivorship and sensitivity to AAOI. Do not present the pooled mean as proof of alpha.

## Honest scope
This is a usable local five-company evidence-to-scenario workflow. The original larger architecture is not complete: no independently reviewed committee, automated bottleneck scoring, full historical membership/delistings, licensed consensus, multi-user authorization, automatic forward forecasts, portfolio construction, alerts or trade execution. No live research decision is reduced to a universal score.

HTML is static and escapes imported text. No remote JavaScript is loaded. Keep the generated SQLite and reports local unless sharing is separately authorized. Source links are public; no credentials are stored.
