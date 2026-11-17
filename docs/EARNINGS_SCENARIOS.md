# Earnings scenarios integrated into the evidence ledger

Added 16 November 2026. This is a working local integration, not a completed stock-selection system.

Run the fully synthetic demonstration:

```console
python autonext.py --db outputs/earnings-demo.sqlite ingest examples/earnings_scenario_demo.json
python autonext.py --db outputs/earnings-demo.sqlite run DEMO:PHOTON:COMMON --as-of 2026-03-01T00:00:00Z
python -m unittest discover -s tests -v
```

The optional `earnings_scenarios` bundle collection follows the same immutable ID, known_at, source_ids and public-source rules as other evidence. Every scenario has a `price_observation` (security_id, currency, price, observed_at, captured_at, source_id, verified, adjustment_basis) and `scenario` (years, required_return, terminal_pe, future_share_factor, rationale).

A user-supplied `verified: true` flag records an attestation, NOT automatic source authentication. Supply a retained public-source excerpt and independently check the quoted security, timestamp and unadjusted current-share basis. Reference-only or unknown-adjustment observations remain visible but produce blocked results. Captured mode also checks the price observation capture time. Published mode can use later-captured public evidence, as elsewhere in AutoNext.

Required terminal EPS = current share price * (1 + required annual return)^years / terminal P/E.
Required total earnings per current share = required terminal EPS * future/current share ratio.

Dilution changes the second quantity, not EPS twice. An optional terminal_eps must explicitly use net_income_per_future_diluted_share. Its gap to the hurdle and corresponding annualized return are a labelled operating scenario, not consensus or a forecast. Interest, tax, financing and dilution must already be reflected in that assumed EPS. No interim distributions or share-class conversions are modeled.

New runs retain all eligible scenarios rather than collapsing different assumptions into one winner. Run diffs track additions and changes; reusing an immutable scenario ID with different contents is rejected. Old saved runs without this collection can still be compared.

Not yet delivered: verified live price/share adapter, actual five-company operating cases, ranking, portfolio allocation, trading, or publication. Existing revenue-multiple scenarios retain their prior contract; these new price safeguards do not retrospectively authenticate them. No real-company prices or scenarios were invented for this integration.
