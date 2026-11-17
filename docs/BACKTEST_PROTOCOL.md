# Backtest protocol: does the AutoNext pattern work?

## What we have tested now
The existing evidence ledger can be replayed at historical cutoffs. `backtest_audit.py` copies the database into memory, runs both published and captured modes, and checks source publication/capture and row availability. It does not modify the input database. The November 2026 dataset contains five manually chosen surviving photonics companies, mostly reported financial facts. Old financial period ends are not dates when investors knew the figures.

This checks the plumbing, not stock-picking skill. Historical judgments newly written today are hindsight reconstructions, even when their cited filings are old. Current SEC Company Facts also need original-accession/restatement checks before they can be treated as an unbiased historical panel.

## Freeze a testable hypothesis before looking at returns
A useful first candidate: companies showing independently evidenced commercial conversion and earnings improvement, without an excessive price-implied earnings hurdle, subsequently outperform comparable public photonics companies. This is a proposed hypothesis, not an implemented strategy or a proven finding.

Translate each term into a reproducible numeric/boolean rule; specify thresholds, treatment of missing evidence, entry, holding period, exit, position sizing and cash allocation. Version/hash the rule and record every variant tried. Do not optimize rules on the evaluation period. Treat management beating its own guidance separately from stock returns and consensus surprise.

## Data and bias controls
- Reconstruct the eligible listed universe at each decision date, including failures, acquired companies and delistings. Keep today's five-company sample only as a plumbing pilot.
- Use original public filing/release availability, not financial period end. Retain original versions and corrections separately. No future restatements or retrospectively assigned qualitative scores.
- Freeze historical universe membership and all signal inputs before evaluation. If evidence was assembled retrospectively, label the study reconstructed, not prospective.
- Execute no earlier than the next tradable session after signal availability, with a conservative extra session for date-only publications. Never assume the announcement closing price was attainable.
- Obtain auditable split/dividend-adjusted total-return data and delisting outcomes; verify adjustment convention and time zone. Do not replace missing outcomes by dropping the companies.
- Compare with a broad US equity total-return benchmark and a contemporaneously eligible equal-weight photonics basket. Define rebalance dates before testing; apply costs consistently.
- Report gross and net results with explicit one-way commissions/slippage sensitivities (for example 10, 25, 50 basis points as test assumptions, not measured costs). Include turnover and liquidity/capacity limits.
- Use chronological development/validation/untouched test periods and walk-forward evaluation. Purge or embargo overlapping outcome windows. Keep clustered company/date exposures in uncertainty estimates.
- Report sample size, coverage, returns, benchmark-relative results, drawdown, turnover, hit rate, missing-data counts and stability across periods. A small or correlated sample is inconclusive, not proof.

## Practical next step
First source the point-in-time universe and historical adjusted security/benchmark prices; then freeze one simple signal and evaluate it once. In parallel, store forward-dated AutoNext decisions now for a genuinely prospective paper test. No actual trades, publication or financial account access are needed.

## Reproduce the completed readiness audit
```console
python backtest_audit.py --db outputs/operating-review-20261117.sqlite --as-of 2020-12-31T23:59:59Z --as-of 2024-12-31T23:59:59Z --as-of 2026-09-01T00:00:00Z --as-of 2026-11-05T23:59:59Z --output outputs/backtest-readiness-20261117
```
