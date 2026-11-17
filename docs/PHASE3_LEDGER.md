# Phase 3: connected evidence ledger
Run: python sec_ledger.py

SEC facts now import into outputs/public_companies.sqlite and generate captured-mode saved runs.
Read outputs/ledger/FIVE_COMPANY_REVIEW.md. JSON bundles/runs/change records sit alongside it.

Normalization preserves exact dates, taxonomy, accession and unit; guidance is never invented.
Coherent's previously checked revenue guidance is explicitly mapped from fiscal Q1 FY2027 to July-September 2026, so the existing comparison engine now compares it with exact SEC revenue. This is a manually reviewed mapping, not a general automated fiscal calendar resolver.

Changes summarize latest comparable standalone quarters or instant balance-sheet periods. Retired historical revenue tags are suppressed from current summaries. YTD figures are not mixed with quarters. Historical restated values remain in the ledger; simultaneous conflicting values are excluded rather than arbitrarily chosen.
Missing direct Q4 standalone facts can prevent a sequential revenue comparison. We have not silently derived Q4 from annual minus nine-month numbers, nor equated alternate tags.

Actual finding examples: AAOI latest quarterly revenue rose 40.6% sequentially and period-end shares rose 6.5%; IPG revenue rose 3.2%. These are accounting changes, not market-expectations beats, stock recommendations or explanations of causes. Cash movement does not equal operating cash burn.

A read-only market-data tool returned observations for all five securities dated Nov 13/14 2026. Saved separately as reference_only_prices.json, with exact reported timestamps and capture timestamp. The underlying vendor, adjustment convention and redistribution rights were not established. They are NOT ingested into valuation, NOT official closing prices, and NOT a working autonomous feed. No API key or payment is necessary for this one-time contextual lookup; production price sourcing remains open.

The evidence adapter still lacks broad guidance extraction, cash-flow attribution, licensed consensus, security/corporate-action history and a coherent price-capital valuation bridge. No trades or publishing.

