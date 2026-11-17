"""AutoNext: local, evidence-first public-company research. Python 3.11+."""
import argparse
import earnings_scenarios
from contextlib import closing
import hashlib
import json
import math
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS bundles (
 digest TEXT PRIMARY KEY, security_id TEXT NOT NULL, imported_at TEXT NOT NULL,
 payload TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS runs (
 run_id TEXT PRIMARY KEY, created_at TEXT NOT NULL, payload TEXT NOT NULL
);
"""
PHOTONICS_STAGES = ("lab_validation", "customer_qualification", "design_win", "volume_revenue")
KINDS = ("management_guidance", "analyst_estimate", "licensed_consensus", "observed_result")
REQUIRED_VALUATION = ("price", "shares", "cash", "debt", "years", "discount_rate",
                      "terminal_revenue_multiple", "future_shares", "future_cash", "future_debt")

def timestamp(value):
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None:
        raise ValueError("Timestamps require a timezone (use ...T00:00:00Z)")
    return result.astimezone(timezone.utc)

def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)

def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()

def number(value, field, minimum=None):
    if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value):
        raise ValueError(f"{field} must be a finite number")
    if minimum is not None and value < minimum:
        raise ValueError(f"{field} must be >= {minimum}")
    return value

def validate(bundle):
    if not isinstance(bundle, dict):
        raise ValueError("Bundle must be a JSON object")
    for name in ("sources", "claims", "expectations", "catalysts", "valuations", "earnings_scenarios"):
        if name in bundle and (not isinstance(bundle[name], list) or any(not isinstance(r, dict) for r in bundle[name])):
            raise ValueError(f"{name} must be a list of objects")
    for key in ("security", "sources", "claims", "expectations"):
        if key not in bundle:
            raise ValueError(f"Missing {key}")
    s = bundle["security"]
    for key in ("id", "company", "ticker", "exchange", "share_class", "currency", "sector"):
        if not isinstance(s.get(key), str) or not s[key].strip():
            raise ValueError(f"security.{key} required")
    if s["sector"] != "photonics":
        raise ValueError("First supported vertical is photonics")
    sources = {}
    for source in bundle["sources"]:
        sid = source["id"]
        if sid in sources:
            raise ValueError(f"Duplicate source {sid}")
        if not source.get("title") or not source.get("locator"):
            raise ValueError("Each source needs title and locator")
        if source.get("visibility") != "public":
            raise ValueError("This release accepts public evidence only")
        timestamp(source["published_at"])
        timestamp(source["captured_at"])
        if timestamp(source["captured_at"]) < timestamp(source["published_at"]):
            raise ValueError("Source cannot be captured before publication")
        if not source.get("excerpt", "").strip():
            raise ValueError("Source needs a retained excerpt, not only a URL")
        sources[sid] = source
    def refs(row):
        if not row.get("source_ids") or any(s not in sources for s in row["source_ids"]):
            raise ValueError("Unknown or missing source reference")
        for sid in row["source_ids"]:
            if timestamp(row["known_at"]) < timestamp(sources[sid]["published_at"]):
                raise ValueError("Row cannot be known before its source was published")
    for category in ("claims", "expectations", "catalysts", "valuations", "earnings_scenarios"):
        ids = set()
        for row in bundle.get(category, []):
            if row["id"] in ids:
                raise ValueError(f"Duplicate {category} id")
            ids.add(row["id"])
            timestamp(row["known_at"])
            refs(row)
            if category == "claims":
                if row.get("status") not in ("supported", "contradicted", "unresolved"):
                    raise ValueError("Claim status must be supported, contradicted or unresolved")
                if row.get("stage") not in PHOTONICS_STAGES:
                    raise ValueError("Invalid photonics commercialisation stage")
                if not row.get("text", "").strip():
                    raise ValueError("Claim text required")
            if category == "expectations":
                if row.get("kind") not in KINDS:
                    raise ValueError("Invalid expectation kind")
                number(row["value"], "expectation.value")
                if "low" in row or "high" in row:
                    low = number(row["low"], "expectation.low")
                    high = number(row["high"], "expectation.high")
                    if not low <= row["value"] <= high:
                        raise ValueError("Expectation midpoint must be within range")
                for field in ("metric", "period", "unit", "basis"):
                    if not row.get(field):
                        raise ValueError(f"Expectation {field} required")
            if category == "catalysts":
                for field in ("event", "uncertainty", "supports", "weakens", "still_unresolved"):
                    if not row.get(field):
                        raise ValueError(f"Catalyst {field} required")
                timestamp(row["expected_at"])
            if category == "earnings_scenarios":
                earnings_scenarios.validate_scenario(row, s)
                price = row["price_observation"]
                source = sources[price["source_id"]]
                if timestamp(price["captured_at"]) < timestamp(source["published_at"]):
                    raise ValueError("Price capture precedes source publication")
            if category == "valuations":
                validate_valuation(row)
    return bundle

def validate_valuation(v):
    for field in REQUIRED_VALUATION:
        number(v[field], field, 0)
    for field in ("price", "shares", "future_shares", "terminal_revenue_multiple"):
        if v[field] <= 0:
            raise ValueError(f"{field} must be positive")
    if v["years"] <= 0 or v["years"] > 50:
        raise ValueError("years must be > 0 and <= 50")
    if v["discount_rate"] > 1:
        raise ValueError("discount_rate must be a fraction between 0 and 1")
    if v.get("units") != "currency_units_and_absolute_shares":
        raise ValueError("Use actual currency amounts and absolute shares, not mixed millions")
    if not v.get("assumptions", "").strip():
        raise ValueError("Valuation assumptions must be stated")
    for field in ("expected_at",):
        if field in v:
            timestamp(v[field])

def reverse_valuation(v):
    """No interim distributions: terminal per-share proceeds discounted to today's price."""
    validate_valuation(v)
    equity = v["price"] * v["shares"]
    ev = equity + v["debt"] - v["cash"]
    required_terminal_equity = v["price"] * (1 + v["discount_rate"]) ** v["years"] * v["future_shares"]
    required_terminal_ev = required_terminal_equity + v["future_debt"] - v["future_cash"]
    if required_terminal_ev <= 0:
        return {"equity_value": equity, "enterprise_value": ev,
                "implied_terminal_revenue": None,
                "limitation": "Terminal net cash alone exceeds required equity value; this revenue-multiple inversion is not informative."}
    return {"equity_value": equity, "enterprise_value": ev,
            "implied_terminal_revenue": required_terminal_ev / v["terminal_revenue_multiple"],
            "limitation": "Scenario inversion, not a forecast or price target. No interim dividends/buybacks; terminal cash/debt and dilution are explicit assumptions."}

def connect(path):
    db = sqlite3.connect(path)
    db.executescript(SCHEMA)
    return db

def ingest(db, bundle):
    validate(bundle)
    key = digest(bundle)
    db.execute("INSERT OR IGNORE INTO bundles VALUES (?,?,?,?)",
               (key, bundle["security"]["id"], datetime.now(timezone.utc).isoformat(), canonical(bundle)))
    db.commit()
    return key

def build_run(db, security_id, as_of, mode="published"):
    cutoff = timestamp(as_of)
    if mode not in ("published", "captured"):
        raise ValueError("mode must be published or captured")
    bundles = db.execute("SELECT digest,payload FROM bundles WHERE security_id=? ORDER BY digest", (security_id,)).fetchall()
    if not bundles:
        raise ValueError("No evidence imported for this security")
    security = None
    rows = {k: {} for k in ("sources", "claims", "expectations", "catalysts", "valuations", "earnings_scenarios")}
    hashes = []
    for h, payload in bundles:
        bundle = json.loads(payload)
        if security is not None and bundle["security"] != security:
            raise ValueError("Conflicting security identity; reconcile before analysis")
        security = bundle["security"]
        hashes.append(h)
        for category in rows:
            for row in bundle.get(category, []):
                key = row["id"]
                if key in rows[category] and rows[category][key] != row:
                    raise ValueError(f"Immutable {category} id {key} was reused with different content; use a new version id")
                rows[category][key] = row
    eligible = {sid: s for sid, s in rows["sources"].items()
                if timestamp(s["published_at"]) <= cutoff
                and (mode != "captured" or timestamp(s["captured_at"]) <= cutoff)}
    filtered = {"sources": sorted(eligible.values(), key=lambda s: s["id"])}
    for category in ("claims", "expectations", "catalysts", "valuations", "earnings_scenarios"):
        filtered[category] = sorted(
            (row for row in rows[category].values()
             if timestamp(row["known_at"]) <= cutoff and all(s in eligible for s in row["source_ids"])),
            key=lambda r: (timestamp(r["known_at"]), r["id"]))
    exp = filtered["expectations"]
    comparisons = []
    # Results and expectations must have identical metric, period, unit AND basis.
    for actual in (e for e in exp if e["kind"] == "observed_result"):
        key = tuple(actual[k] for k in ("metric", "period", "unit", "basis"))
        candidates = [e for e in exp if e["kind"] != "observed_result"
                      and tuple(e[k] for k in ("metric", "period", "unit", "basis")) == key
                      and timestamp(e["known_at"]) < timestamp(actual["known_at"])]
        latest = {}
        for e in candidates:
            # Each category remains separate; analyst estimates never become consensus.
            latest[e["kind"]] = e
        for kind, expectation in latest.items():
            comparisons.append({"actual_id": actual["id"], "expectation_id": expectation["id"],
                                "kind": kind, "metric": actual["metric"], "period": actual["period"],
                                "unit": actual["unit"], "basis": actual["basis"],
                                "expected": expectation["value"], "actual": actual["value"],
                                "difference": actual["value"] - expectation["value"],
                                "range": ([expectation["low"], expectation["high"]] if "low" in expectation else None),
                                "range_outcome": (("below range" if actual["value"] < expectation["low"] else "above range" if actual["value"] > expectation["high"] else "within range") if "low" in expectation else None)})
    valuation = None
    if filtered["valuations"]:
        latest = filtered["valuations"][-1]
        valuation = {"input": latest, "result": reverse_valuation(latest)}
    # Price observation capture time is independently enforced in captured mode.
    filtered["earnings_scenarios"] = [row for row in filtered["earnings_scenarios"]
        if mode != "captured" or timestamp(row["price_observation"]["captured_at"]) <= cutoff]
    earnings = [{"input": row, "result": earnings_scenarios.evaluate(row)}
                for row in filtered["earnings_scenarios"]]
    result = {"security": security, "as_of": cutoff.isoformat(), "mode": mode,
              "bundle_hashes": hashes, **filtered, "expectation_comparisons": comparisons,
              "valuation": valuation, "earnings_analysis": earnings,
              "warnings": ["Public evidence only. Source excerpts are user-imported and not independently authenticated.",
                           "Published mode reconstructs published evidence; captured mode restricts to retained snapshots.",
                           "No market feed, consensus licence, LLM inference, trading or investment recommendation."]}
    result["run_id"] = digest(result)[:24]
    db.execute("INSERT OR IGNORE INTO runs VALUES (?,?,?)",
               (result["run_id"], datetime.now(timezone.utc).isoformat(), canonical(result)))
    db.commit()
    return result

def difference(old, new):
    if old["security"]["id"] != new["security"]["id"]:
        raise ValueError("Diff requires the same security")
    out = {"old": old["run_id"], "new": new["run_id"], "changes": {}}
    for category in ("claims", "expectations", "catalysts", "valuations", "earnings_scenarios"):
        before = {r["id"]: r for r in old.get(category, [])}
        after = {r["id"]: r for r in new.get(category, [])}
        out["changes"][category] = {"added": [after[k] for k in sorted(after.keys()-before.keys())],
                                    "removed": [before[k] for k in sorted(before.keys()-after.keys())],
                                    "changed": [after[k] for k in sorted(after.keys() & before.keys()) if after[k] != before[k]]}
    return out

def report(r):
    s = r["security"]
    lines = [f"# AutoNext | {s['company']} ({s['exchange']}:{s['ticker']})",
             f"Security: {s['id']} | {s['share_class']} | {s['currency']}",
             f"As of: {r['as_of']} | evidence mode: {r['mode']} | run: {r['run_id']}",
             "", "## What do we know?"]
    for stage in PHOTONICS_STAGES:
        lines.append(f"### {stage.replace('_', ' ').title()}")
        claims = [c for c in r["claims"] if c["stage"] == stage]
        lines.extend([f"- **{c['status']}**: {c['text']} [{', '.join(c['source_ids'])}]" for c in claims]
                     or ["No imported claim at this stage. This is unknown, not a negative score."])
    lines += ["", "## Expectations ledger"]
    for e in r["expectations"]:
        detail = f"{e['value']:,.2f}"
        if "low" in e:
            detail = f"{e['low']:,.2f} to {e['high']:,.2f} (midpoint {e['value']:,.2f})"
        lines.append(f"- {e['kind']} | {e['metric']} | {e['period']} | {e['basis']} | {detail} {e['unit']} | known {e['known_at']} [{e['id']}; sources: {', '.join(e['source_ids'])}]")
    if not r["expectations"]:
        lines.append("No eligible expectation or actual imported.")
    lines += ["", "## What did expectations get right or wrong?"]
    for c in r["expectation_comparisons"]:
        lines.append(f"- {c['metric']}, {c['period']} ({c['basis']}): {c['kind']} {c['expected']:,.2f}; actual {c['actual']:,.2f} {c['unit']}; difference {c['difference']:,.2f}. [{c['expectation_id']} / {c['actual_id']}]")
        if c["range"] is not None:
            lines.append(f"  Published range: {c['range'][0]:,.2f} to {c['range'][1]:,.2f}; result {c['range_outcome']}. Expected point above is the computed range midpoint, not a separate forecast.")
    if not r["expectation_comparisons"]:
        lines.append("No comparable actual-versus-prior-expectation pair available.")
    lines += ["", "## What must be true at this price?"]
    if r["valuation"]:
        v, result = r["valuation"]["input"], r["valuation"]["result"]
        lines += [f"Price input: {v['price']} {s['currency']}, dated {v['known_at']}.",
                  f"Implied terminal revenue: {result['implied_terminal_revenue']} {s['currency']}.",
                  f"Assumptions: {v['assumptions']}",
                  f"Inputs: {v['years']} years; discount rate {v['discount_rate']:.1%}; terminal EV/revenue {v['terminal_revenue_multiple']}x; future shares {v['future_shares']:,.0f}.",
                  result["limitation"]]
    else:
        lines.append("No eligible valuation snapshot imported. No target or score is invented.")
    lines += ["", "## Per-share earnings scenarios"]
    for analysis in r.get("earnings_analysis", []):
        row, outcome = analysis["input"], analysis["result"]
        lines.append(f"### Scenario {row['id']} [{', '.join(row['source_ids'])}]")
        if outcome["status"] == "blocked":
            lines.append("Blocked: " + outcome["reason"])
            continue
        lines += [f"Required terminal EPS: {outcome['required_terminal_eps']:.4f} {s['currency']} per future diluted share.",
                  f"Required total earnings per current share: {outcome['required_total_earnings_per_current_share']:.4f} {s['currency']}.",
                  f"Price observed: {outcome['price_observed_at']}. Assumptions: {row['scenario']['rationale']}",
                  f"Inputs: {row['scenario']['years']} years; required return {row['scenario']['required_return']:.1%}; terminal P/E {row['scenario']['terminal_pe']}x; future/current shares {row['scenario']['future_share_factor']}x.",
                  outcome["limitation"]]
        if "assumed_terminal_eps" in outcome:
            lines.append(f"User-assumed terminal EPS: {outcome['assumed_terminal_eps']:.4f}; gap to hurdle: {outcome['eps_above_hurdle']:.4f}; scenario annualized return: {outcome['scenario_annualized_return']:.1%}.")
    if not r.get("earnings_analysis"):
        lines.append("No eligible sourced earnings scenario. No ranking is inferred.")
    lines += ["", "## What would change the thesis?"]
    for c in r["catalysts"]:
        lines += [f"### {c['event']} (expected {c['expected_at']})",
                  f"Uncertainty: {c['uncertainty']}", f"Supports: {c['supports']}",
                  f"Weakens: {c['weakens']}", f"Still unresolved: {c['still_unresolved']}"]
    if not r["catalysts"]:
        lines.append("No sourced catalyst imported.")
    lines += ["", "## Evidence and limitations"]
    for source in r["sources"]:
        lines += [f"- [{source['id']}] {source['title']}: {source['locator']} | published {source['published_at']} | captured {source['captured_at']}",
                  f"  Retained excerpt: {source['excerpt']}"]
    lines += [f"- {w}" for w in r["warnings"]]
    return "\n".join(lines) + "\n"

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default="autonext.sqlite")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("ingest"); p.add_argument("bundle")
    p = sub.add_parser("run"); p.add_argument("security_id"); p.add_argument("--as-of", required=True)
    p.add_argument("--mode", choices=["published", "captured"], default="published")
    p.add_argument("--format", choices=["json", "markdown"], default="markdown")
    p = sub.add_parser("diff"); p.add_argument("old_run"); p.add_argument("new_run")
    args = parser.parse_args(argv)
    try:
        with closing(connect(args.db)) as db:
            if args.command == "ingest":
                print(ingest(db, json.loads(Path(args.bundle).read_text(encoding="utf-8-sig"))))
            elif args.command == "run":
                r = build_run(db, args.security_id, args.as_of, args.mode)
                print(report(r) if args.format == "markdown" else json.dumps(r, indent=2, allow_nan=False))
            else:
                def get(key):
                    row = db.execute("SELECT payload FROM runs WHERE run_id=?", (key,)).fetchone()
                    if not row: raise ValueError(f"Unknown run {key}")
                    return json.loads(row[0])
                print(json.dumps(difference(get(args.old_run), get(args.new_run)), indent=2))
        return 0
    except (ValueError, KeyError, OSError, sqlite3.Error) as exc:
        print(f"AutoNext: {exc}", file=sys.stderr)
        return 2

if __name__ == "__main__":
    raise SystemExit(main())
