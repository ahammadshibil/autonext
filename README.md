# AutoNext
## Public-market deeptech research, with evidence you can inspect

[![tests](https://github.com/ahammadshibil/autonext/actions/workflows/tests.yml/badge.svg)](https://github.com/ahammadshibil/autonext/actions/workflows/tests.yml)

AutoNext asks: **What must be true at this price, what evidence supports it, and what would change our view?**

This is the first implemented, local research slice of the original AutoNext architecture. It is not a live stock screener, financial adviser, production-complete platform, or trading agent.

### Run it
Python 3.11+; standard library only. No package installation or API key required.

```console
python autonext.py --db demo.sqlite ingest examples/photonics_demo.json
python autonext.py --db demo.sqlite run DEMO:PHOTON:COMMON --as-of 2025-12-31T23:59:59Z
python autonext.py --db demo.sqlite run DEMO:PHOTON:COMMON --as-of 2026-03-01T00:00:00Z --format json
python autonext.py --db demo.sqlite diff OLD_RUN_ID NEW_RUN_ID
python -m unittest discover -s tests -v
```

The bundled company, prices, sources and outcomes are **entirely synthetic**. They demonstrate behavior, not an investment thesis. Import real public-company evidence using the same JSON contract; inspect retained excerpts against their sources yourself.

### Implemented
- SQLite append-only bundle ledger, content hashes and immutable run records.
- Public security identity: company, ticker, exchange, share class, currency.
- Claim provenance and source excerpts; public-only evidence import.
- Exact as-of filtering, both published and captured-snapshot modes.
- Management guidance / analyst estimates / licensed consensus / actuals remain separate.
- Like-for-like expectation comparisons require matching metric, period, unit and accounting basis.
- Reverse revenue valuation with explicit dilution, terminal cash/debt, discount rate and horizon.
- Photonics distinction: lab validation, qualification, design win, volume revenue.
- Catalyst cards explain what evidence would support/weaken a thesis and what remains unresolved.
- Markdown/JSON reports and stored-run diffs. No opaque composite ranking.

### Valuation model
For a scenario with no interim distributions:

```text
Required terminal equity = today's price Ã— (1 + discount rate)^years Ã— future diluted shares
Required terminal EV = required terminal equity + future debt âˆ’ future cash
Implied terminal revenue = required terminal EV / terminal EV-to-revenue multiple
```

This is an inversion of explicit assumptions, not a prediction. Future issuance, future cash and debt must be mutually coherent; this release does not model financing proceeds or a full cash-flow bridge. All money uses the security's currency and actual currency units; all shares are absolute counts. No automated FX conversion.

### Evidence contract
See examples/photonics_demo.json. Every claim, expectation, catalyst and valuation needs an ID, known_at and source_ids. Every source needs publication/capture timestamps with timezone, title, locator, retained excerpt and public visibility.

Use new immutable IDs for revised guidance, filings, corrections and assumptions. Conflicting reuse blocks analysis rather than silently overwriting history. Distinguish separate securities using separate security IDs. Publication time is not period end.

Published mode only includes sources published by the cutoff, even if captured later. Captured mode additionally requires retained snapshots by the cutoff. Neither is a claim of full historical market knowledge or a backtested strategy. Frozen imports and no LLM inference reduce, but do not eliminate, human data-selection or hindsight bias.

### Deliberate limits
- Read-only SEC filing adapter now available (see Phase 2 below). No live price/consensus adapter; manually imported evidence is not independently authenticated.
- Source excerpts must be supplied; full-document archiving and paragraph-level citation checks are not implemented.
- No automatic source-entitlement verification. Import only public material you may use.
- No team authorization or multi-tenancy. Keep the database local and do not expose it as a service.
- No complete accounting normalisation, corporate-action adjustment, security history or restatement resolution.
- No ranking calibration, portfolio allocation, price targets, trade execution or recommendations.
- No Scout/Assay/Radar/Conviction live adapter calls yet. See the roadmap for integration boundaries.

The original architecture is preserved unchanged in docs/AUTONEXT_SYSTEM_DESIGN_ORIGINAL.md. The current public-market scope is in docs/PUBLIC_MARKET_ALIGNMENT.md.

## Real primary-source walkthrough: Coherent
The second example is manually extracted from Coherent's August 12 and November 4, 2026 earnings releases, with source URLs and retained paraphrases. It is not synthetic and is not a current investment recommendation.

```console
python autonext.py --db coherent.sqlite ingest examples/coherent_primary_sources.json
python autonext.py --db coherent.sqlite run NYSE:COHR:COMMON --as-of 2026-09-01T00:00:00Z
python autonext.py --db coherent.sqlite run NYSE:COHR:COMMON --as-of 2026-11-16T02:05:00Z
```

The earlier snapshot contains guidance but cannot see November results. The later snapshot shows revenue within management's published range, and non-GAAP EPS above its range. GAAP and non-GAAP EPS are not mixed. A range midpoint is labelled as a derived midpoint, not a management point forecast. No real-company valuation is generated because no market-price/capital snapshot was verified.

Known limitations: the retained evidence is a manually checked paraphrase, not a full archived filing. Date-only source publication is assigned conservative end-of-date UTC, explicitly noted; do not use this example for intraday research. Capture time is the actual review date, so captured-mode historical runs intentionally exclude these late-collected sources. Rows with the same expectation kind are treated as one series per metric/period/basis; independent analyst forecaster-series support remains to be added before importing multiple analysts' forecasts.

## Phase 2: live SEC evidence desk
See docs/PHASE2_DATA_INTEGRATION.md. Run sec_adapter.py for archived public filings and candidate financial facts across five real photonics companies. This is separate from the normalized expectations ledger; no live price or buy/sell ranking is implied.

## Earnings scenarios in the research workflow
See docs/EARNINGS_SCENARIOS.md and examples/earnings_scenario_demo.json. Dated per-share earnings hurdles now flow through the existing evidence ledger, as-of runs, Markdown/JSON reports and diffs. Reference-only prices abstain. This remains a scenario model, not an automated investment ranking.


## Integrated local research desk
Run `python research_desk.py --refresh-prices` and open the printed index.html. See docs/RESEARCH_DESK.md for the complete workflow, refresh commands and limits.

## Terminal research workflow
`research_cli.py` reads the newest generated desk by default and never changes its evidence ledger.

```console
python research_cli.py universe
python research_cli.py company COHR
python research_cli.py compare --terminal-pe 25 --return-rate 0.10 --years 5
python research_cli.py scenario COHR --terminal-pe 20 --share-factor 1.1
python research_cli.py search qualification volume --ticker COHR
python research_cli.py --json company COHR
python research_cli.py obsidian --output "C:\\path\\to\\vault\\AutoNext"
python research_cli.py doctor --vault "C:\\path\\to\\vault\\AutoNext"
python research_cli.py workflow --vault "C:\\path\\to\\vault\\AutoNext"
```

Use `--desk PATH` before the command to inspect a specific historical desk. Comparisons and scenarios are transparent sensitivities, not forecasts, attractiveness rankings, recommendations or trade instructions. Search covers retained excerpts only. The Obsidian exporter refreshes generated company pages, creates immutable dated snapshots and never overwrites human-owned thesis notes. See `docs/TERMINAL_OBSIDIAN_PLAN.md`.

`workflow` is the end-to-end local command: it builds a new desk from the latest hash-verified SEC captures and reviewed operating releases, refreshes single-provider prices, exports the result to Obsidian and runs `doctor`. Add `--offline` to abstain from price-dependent analysis. To refresh SEC captures too, add `--refresh-sec --sec-user-agent "AutoNext research your@email.example"`; the SEC requires an identifying contact string.

