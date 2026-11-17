# AutoNext terminal + Obsidian plan

## Product decision

AutoNext should not build another investment dashboard. The terminal is the deterministic research engine; Obsidian is the human thinking and memory layer.

```text
primary sources
      ↓
point-in-time evidence ledger
      ↓
terminal: inspect · search · compare · scenario
      ↓
immutable Obsidian snapshot
      ↓
human-owned thesis · catalyst ledger · decision log
      ↓
later outcome review and calibration
```

The browser desk remains a generated audit artifact, not the main product surface.

## What comparable repositories teach us

### OpenBB — one core, several surfaces

[OpenBB](https://github.com/OpenBB-finance/OpenBB) describes a connect-once, consume-everywhere data platform. AutoNext should use the same separation at a much smaller scale: the evidence model is the product core; terminal commands and Obsidian notes are adapters over it. We should not duplicate research logic inside each surface.

### EdgarTools — simple ticker-first access, rich provenance beneath

[EdgarTools](https://github.com/dgunning/edgartools) turns complex EDGAR filings into typed company and filing objects while retaining direct filing access. AutoNext's terminal should similarly make `company COHR` easy without collapsing publication time, capture time, accounting basis, accession identity or source excerpts.

### stock-analysis — fixed research contracts and epistemic labels

[stock-analysis](https://github.com/AdvancingTitans/stock-analysis) distinguishes facts, derived facts and analysis, and uses different Quick, Standard and Deep report contracts. AutoNext should eventually add depth modes, but the first release keeps one compact deterministic company view. The fact/derivation/scenario boundary is mandatory now.

### Obsidian investment workflow — maintained notes plus immutable reports

[obsidian-skills](https://github.com/dengrish/obsidian-skills) uses maintained stock notes linked to immutable daily reports. This is the right knowledge architecture for AutoNext. Generated company notes may refresh; dated evidence snapshots never change; the investor's thesis note is created once and never overwritten.

### QuantOS — point-in-time research and valid abstention

[QuantOS](https://github.com/purysho/QuantOS) emphasizes event time versus knowledge time, immutable evidence, explicit counter-evidence and valid `INSUFFICIENT_EVIDENCE` outcomes. AutoNext already follows much of this discipline. We should borrow the safety semantics, not its much larger modeling and execution scope.

## Implemented MVP contract

```console
python research_cli.py universe
python research_cli.py company COHR
python research_cli.py compare --terminal-pe 25 --return-rate 0.10
python research_cli.py scenario COHR --terminal-pe 20 --share-factor 1.1
python research_cli.py search qualification volume --ticker COHR
python research_cli.py obsidian --output PATH_INSIDE_YOUR_VAULT
python research_cli.py doctor --vault PATH_INSIDE_YOUR_VAULT
python research_cli.py workflow --vault PATH_INSIDE_YOUR_VAULT
```

The Obsidian export creates:

```text
AutoNext Research.md                 generated research home
Companies/COHR.md                    generated current company page
Snapshots/2026-11-17/COHR ....md    immutable evidence snapshot
Theses/COHR Thesis.md                human-owned; created once
```

The exporter refuses to overwrite a non-AutoNext company/home note. It refuses to mutate an existing snapshot whose content differs. It never overwrites thesis notes.

## Build order

### Phase 1 — usable local loop (implemented)

- Discover the latest generated desk.
- List the research universe and data dates.
- Inspect one company's operating evidence and audit paths.
- Search retained evidence.
- Run explicit price-hurdle sensitivities.
- Export Obsidian-native Markdown with wikilinks, properties and research-boundary callouts.
- Rebuild, export and validate the local workflow with one command.
- Fail visibly on missing artifacts, stale dated prices or incomplete scenario generation.

### Phase 2 — repeatable evidence refresh

- Replace the five-company hard-coded universe with a watchlist file.
- Add `update TICKER` with SEC identity, rate-limit and receipt controls.
- Capture complete primary documents or filing sections, not only retained paraphrases.
- Reconcile prices across two independent providers before a price is marked reconciled.
- Add `doctor` for stale sources, missing receipts and broken vault links.

### Phase 3 — thesis and catalyst memory

- Parse a structured catalyst table from each human thesis note without rewriting prose.
- Store discovery time, expected recognition window, financing runway, falsifier and actual recognition date.
- Add `thesis diff TICKER` and a dated pre-mortem before each catalyst.
- Record forecasts prospectively and score calibration only after outcomes mature.

### Phase 4 — deeptech research graph

- Map research → technology → product → distribution for each company.
- Separate technical proof, qualification, volume production and economic capture.
- Link suppliers, customers, competitors, enabling technologies and public securities.
- Add founder, employee and organisation evidence with source-quality controls.

### Phase 5 — independent committee, then portfolio research

- Run genuinely independent analyst, technical, market, risk and red-team reviews.
- Preserve disagreements and blocking objections; do not average them into a confidence score.
- Add portfolio construction only after point-in-time universe, price reconciliation and prospective calibration exist.
- Keep live order authority outside AutoNext.

## Explicit non-goals for the current release

- No frontend expansion.
- No universal attractiveness score.
- No model-generated forecast disguised as consensus.
- No automatic buy/sell recommendation.
- No broker connection or trade execution.
- No claim that the current five-company photonics set is a historical investable universe.
