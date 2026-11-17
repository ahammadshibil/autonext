# Phase 2: live filing evidence, not guessed stock recommendations

## What now works
SEC submissions and company-facts integrations run locally without an API key. Five issuer/CIK mappings were checked against the live SEC response: COHR, LITE, IPGP, FN, AAOI. Raw response bytes are content-hashed and archived with individual fetch receipts (URL, capture time, issuer, digest). Filing links retain accession and exact SEC acceptance time.

```console
python sec_adapter.py --symbols COHR LITE IPGP FN AAOI --user-agent "AutoNext Research contact ahammadshibil.com"
```

Read outputs/sec/verification.json to find the verified reports. Each report separates period revenue from instant cash/share counts and lists recent operating filings. It does not silently turn nine-month revenue into quarterly revenue or treat missing tags as zero.

Human value: inspect actual filed numbers with direct evidence, know when information became public, find the latest filing to read, and avoid comparing mismatched periods. The reports are an evidence desk, not yet a finished company thesis.

## Real integration findings
- Coherent's quarterly filed revenue is USD 2,370,324,000, not merely the rounded USD 2,370m in the earnings-release example. Do not replace the rounded guidance comparison without preserving source precision.
- IPG and Applied Optoelectronics each have both quarterly and nine-month revenue facts for the same end date. AutoNext retains the different start dates rather than adding or confusing them.
- Coherent did not supply an eligible us-gaap common-share fact through this selector. It remains unknown. Do not substitute weighted-average diluted EPS shares for outstanding equity shares.
- Sources are company-wide statements, not proof that a specific new photonics product has qualified or reached volume.
- Initial live validation rejected legitimate nested SEC XML paths. This was fixed with segment-by-segment validation; traversal paths remain rejected.

## As-of discipline
Published mode filters by SEC acceptance timestamps, not fiscal period ends. Captured mode additionally requires both snapshots to have existed by the cutoff. Historical filings outside the recent submissions index are excluded even when companyfacts contains their facts. Archive-page ingestion is not implemented yet. No claim of an unbiased historical backtest.

Companyfacts contains restatements and alternate duration contexts. Candidates remain labelled, not fully normalized. Custom XBRL tags and non-GAAP guidance are not automatically extracted. Only USD and a specific common-stock share tag are selected.

## Price data decision
Primary SEC documentation: https://www.sec.gov/search-filings/edgar-application-programming-interfaces
Price provider documentation checked: https://www.alphavantage.co/documentation/

SEC supplies filings, not a tradable market-price feed. Alpha Vantage documents an end-of-day quote endpoint with an API key; real-time/delayed access and commercial use have separate entitlement considerations. No account, subscription or credentials were created or searched. No price integration is claimed. Do not use demo-symbol prices as company data.

Next price adapter needs a user-authorized data provider and permission for intended use, exact security identity/exchange/currency, raw versus adjusted convention, observation time versus capture time, stale-data checks, corporate-action handling, and no credentials in saved receipts. No verified price means no real reverse valuation, not a fabricated number.

## Remaining gaps
This standalone adapter does not yet import normalized facts into the original SQLite expectations ledger. Cross-company thesis comparisons, archived older filing indexes, document-level extraction, automated guidance matching, valuation capital bridges, and product-specific evidence remain next work. Bounded retries cover throttling/server responses; a local serial limiter is not an organization-wide request limiter. HTML filings are linked, not fully archived. No live trades, public publication or remote push.

