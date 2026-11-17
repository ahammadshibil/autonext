"""Terminal research interface for a generated AutoNext desk.

This reads existing, immutable desk outputs. It does not fetch data, alter the
ledger, make recommendations, construct a portfolio or execute trades.
"""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parent
DISCLAIMER = "Sensitivity analysis only; not a forecast, ranking, recommendation or trade instruction."
GENERATED_MARKER = "autonext_generated: true"
DOSSIER_DIR = ROOT / "dossiers"


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def load_dossier(symbol, required=True):
    """Load a small, sourced security-state override for non-standalone cases."""
    symbol = str(symbol).upper()
    path = DOSSIER_DIR / f"{symbol}.json"
    if not path.is_file():
        if required:
            raise ValueError(f"No investment dossier for {symbol}: {path}")
        return None
    dossier = read_json(path)
    for key in ("schema_version", "ticker", "as_of", "security_state", "executive_view", "sources"):
        if key not in dossier:
            raise ValueError(f"Dossier {path} is missing {key}")
    if dossier["schema_version"] != 1 or dossier["ticker"].upper() != symbol:
        raise ValueError(f"Invalid dossier identity or schema: {path}")
    mode = dossier["security_state"].get("mode")
    if mode not in ("standalone", "pending_all_stock_merger"):
        raise ValueError(f"Unsupported security state in {path}: {mode}")
    if not dossier["sources"] or any(not row.get("url", "").startswith("https://") for row in dossier["sources"]):
        raise ValueError(f"Dossier sources must contain HTTPS URLs: {path}")
    if mode == "pending_all_stock_merger":
        transaction = dossier.get("transaction", {})
        prices = transaction.get("dated_prices", {})
        if transaction.get("exchange_ratio", 0) <= 0 or prices.get("lite", 0) <= 0 or prices.get("mrvl", 0) <= 0:
            raise ValueError(f"Dossier merger terms and dated prices must be positive: {path}")
    return dossier


def security_mode(symbol):
    dossier = load_dossier(symbol, required=False)
    return dossier["security_state"]["mode"] if dossier else "standalone"


def merger_math(dossier):
    """Mechanical fixed-ratio arithmetic using same-time dated inputs."""
    transaction = dossier["transaction"]
    prices = transaction["dated_prices"]
    ratio, lite, mrvl = transaction["exchange_ratio"], prices["lite"], prices["mrvl"]
    implied = ratio * mrvl
    effective_ratio = lite / mrvl
    return {
        "observed_at": prices["observed_at"],
        "currency": prices["currency"],
        "exchange_ratio": ratio,
        "lite_price": lite,
        "mrvl_price": mrvl,
        "implied_consideration": implied,
        "gross_spread_per_lite_share": implied - lite,
        "gross_spread_percent": implied / lite - 1,
        "effective_market_ratio": effective_ratio,
        "discount_to_contractual_ratio": 1 - effective_ratio / ratio,
        "mrvl_break_even_for_lite_price": lite / ratio,
        "limitation": "Static same-time arithmetic before time value, taxes, borrow, hedging, closing probability or break-case value; MRVL price is from a secondary source pending independent reconciliation.",
    }


def find_latest_desk(outputs=None):
    outputs = Path(outputs or ROOT / "outputs")
    candidates = sorted(
        (path for path in outputs.glob("desk-*") if (path / "manifest.json").is_file()),
        reverse=True,
    )
    if not candidates:
        raise ValueError(f"No generated desk found under {outputs}")
    return candidates[0].resolve()


class Desk:
    def __init__(self, path=None):
        self.path = Path(path).resolve() if path else find_latest_desk()
        manifest_path = self.path / "manifest.json"
        if not manifest_path.is_file():
            raise ValueError(f"Desk manifest not found: {manifest_path}")
        self.manifest = read_json(manifest_path)
        self.companies = {}
        self.status = {}
        for item in self.manifest.get("companies", []):
            symbol = str(item.get("symbol", "")).upper()
            if not symbol:
                continue
            self.status[symbol] = item
            run_path = self.path / symbol / "run.json"
            if item.get("status") == "ok" and run_path.is_file():
                run = read_json(run_path)
                if run.get("security", {}).get("ticker", "").upper() != symbol:
                    raise ValueError(f"Ticker mismatch in {run_path}")
                changes_path = self.path / symbol / "changes.json"
                self.companies[symbol] = {
                    "run": run,
                    "changes": read_json(changes_path) if changes_path.is_file() else {},
                }
        if not self.companies:
            raise ValueError(f"Desk contains no usable company runs: {self.path}")

    def company(self, symbol):
        symbol = symbol.upper()
        if symbol not in self.companies:
            available = ", ".join(sorted(self.companies))
            raise ValueError(f"Unknown ticker {symbol}. Available: {available}")
        return self.companies[symbol]


def quote(run):
    for item in run.get("earnings_analysis", []):
        observation = item.get("input", {}).get("price_observation")
        if observation:
            return observation
    return None


def release_results(run):
    rows = []
    for item in run.get("expectations", []):
        if item.get("kind") == "observed_result" and "release-" in item.get("id", ""):
            rows.append(item)
    return rows


def sensitivity_rows(run):
    rows = []
    for item in run.get("earnings_analysis", []):
        assumptions = item.get("input", {}).get("scenario")
        result = item.get("result")
        if assumptions and result and result.get("status") != "blocked":
            rows.append({"scenario": assumptions, "result": result})
    return rows


def management_outlook(run):
    """Current guidance plus a like-for-like latest-quarter reference."""
    releases = release_results(run)
    if not releases:
        return []
    latest_release_at = max(parse_iso(row["known_at"]) for row in releases)
    results = []
    for item in run.get("expectations", []):
        if item.get("kind") != "management_guidance" or parse_iso(item["known_at"]) < latest_release_at:
            continue
        row = dict(item)
        candidates = [
            actual for actual in releases
            if all(actual.get(key) == item.get(key) for key in ("metric", "basis", "unit"))
            and parse_iso(actual["known_at"]) <= parse_iso(item["known_at"])
        ]
        prior = max(candidates, key=lambda actual: parse_iso(actual["known_at"]), default=None)
        row["prior_actual"] = prior
        row["midpoint_change_percent"] = ((item["value"] / prior["value"] - 1) * 100
                                             if prior and prior.get("value", 0) > 0 else None)
        results.append(row)
    return sorted(results, key=lambda row: (row.get("period", ""), row.get("metric", "")))


def gaap_eps_hurdle(run, years=5, required_return=0.10, terminal_pe=25, share_factor=1):
    """Annualize one GAAP diluted quarter and compare it with a price hurdle."""
    observation = quote(run)
    if not observation:
        return {"status": "abstain", "reason": "no eligible checked price"}
    hurdle = scenario(observation["price"], years, required_return, terminal_pe, share_factor)
    candidates = [
        row for row in release_results(run)
        if row.get("metric", "").upper() == "EPS"
        and row.get("basis", "").strip().lower() == "gaap diluted"
        and row.get("unit") == f"{run['security']['currency']}/share"
        and "Q" in row.get("period", "").upper()
    ]
    if not candidates:
        return {**hurdle, "status": "abstain", "reason": "no comparable quarterly GAAP diluted EPS"}
    actual = max(candidates, key=lambda row: parse_iso(row["known_at"]))
    run_rate = actual["value"] * 4
    if run_rate <= 0:
        return {**hurdle, "status": "abstain", "reason": "GAAP diluted EPS run-rate is not positive", "latest_eps": actual}
    return {
        **hurdle,
        "status": "mechanical_context_not_forecast",
        "latest_eps": actual,
        "annualized_quarterly_eps_run_rate": run_rate,
        "implied_eps_cagr": (hurdle["required_terminal_eps"] / run_rate) ** (1 / years) - 1,
        "context_limitation": "Annualizes one reported GAAP diluted quarter; ignores seasonality and is not an earnings forecast.",
    }


def guidance_display(row):
    if "low" in row and "high" in row:
        return f"{format_value(row['low'], row['unit'])} to {format_value(row['high'], row['unit'])} (mid {format_value(row['value'], row['unit'])})"
    return format_value(row["value"], row["unit"])


def scenario(price, years, required_return, terminal_pe, share_factor):
    values = (price, years, required_return, terminal_pe, share_factor)
    if any(not isinstance(value, (int, float)) for value in values):
        raise ValueError("Scenario inputs must be numeric")
    if price <= 0 or years <= 0 or terminal_pe <= 0 or share_factor <= 0 or required_return <= -1:
        raise ValueError("Price, years, terminal P/E and share factor must be positive; return must exceed -100%")
    terminal_price = price * (1 + required_return) ** years
    terminal_eps = terminal_price / terminal_pe
    return {
        "current_price": price,
        "years": years,
        "required_return": required_return,
        "terminal_pe": terminal_pe,
        "future_share_factor": share_factor,
        "required_terminal_price": terminal_price,
        "required_terminal_eps": terminal_eps,
        "required_total_earnings_per_current_share": terminal_eps * share_factor,
        "status": "scenario_not_forecast",
        "limitation": DISCLAIMER,
    }


def format_value(value, unit=""):
    if not isinstance(value, (int, float)):
        return str(value)
    magnitude = abs(value)
    if magnitude >= 1_000_000_000:
        text = f"{value / 1_000_000_000:.2f}B"
    elif magnitude >= 1_000_000:
        text = f"{value / 1_000_000:.2f}M"
    elif magnitude >= 1_000:
        text = f"{value / 1_000:.2f}K"
    else:
        text = f"{value:.2f}"
    return f"{text} {unit}".rstrip()


def console_text(value):
    return str(value).replace("–", "-").replace("—", "-").replace("→", "->").replace("×", "x")


def table(headers, rows):
    string_rows = [[str(value) for value in row] for row in rows]
    widths = [len(str(header)) for header in headers]
    for row in string_rows:
        for index, value in enumerate(row):
            widths[index] = max(widths[index], len(value))
    lines = ["  ".join(str(value).ljust(widths[index]) for index, value in enumerate(headers))]
    lines.append("  ".join("-" * width for width in widths))
    lines.extend("  ".join(value.ljust(widths[index]) for index, value in enumerate(row)) for row in string_rows)
    return "\n".join(lines)


def as_json(value):
    print(json.dumps(value, indent=2, ensure_ascii=False))


def frontmatter(properties):
    lines = ["---"]
    for key, value in properties.items():
        if isinstance(value, list):
            lines.append(f"{key}:")
            lines.extend(f"  - {json.dumps(item, ensure_ascii=False)}" for item in value)
        elif isinstance(value, bool):
            lines.append(f"{key}: {'true' if value else 'false'}")
        elif isinstance(value, (int, float)):
            lines.append(f"{key}: {value}")
        else:
            lines.append(f"{key}: {json.dumps(str(value), ensure_ascii=False)}")
    return "\n".join(lines + ["---", ""])


def write_generated(path, content):
    path = Path(path)
    if path.exists() and GENERATED_MARKER not in path.read_text(encoding="utf-8-sig"):
        raise ValueError(f"Refusing to overwrite non-AutoNext note: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def write_immutable(path, content):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_text(encoding="utf-8-sig") != content:
            raise ValueError(f"Immutable snapshot conflict: {path}")
        return False
    path.write_text(content, encoding="utf-8")
    return True


def source_markdown(source):
    title = str(source.get("title") or source.get("id") or "Untitled source").replace("[", "\\[").replace("]", "\\]")
    locator = source.get("locator", "")
    heading = f"[{title}]({locator})" if str(locator).startswith(("https://", "http://")) else title
    excerpt = " ".join(str(source.get("excerpt", "")).split())
    return f"- {heading} — published {source.get('published_at', 'unknown')}\n  - {excerpt}"


def snapshot_note(symbol, data, snapshot_link):
    run, delta = data["run"], data["changes"]
    security, observation = run["security"], quote(run)
    date = (run.get("as_of") or "unknown")[:10]
    lines = [
        frontmatter({
            "title": f"{symbol} AutoNext snapshot {date}",
            "ticker": symbol,
            "company": security["company"],
            "sector": security.get("sector", "unknown"),
            "as_of": run.get("as_of", "unknown"),
            "run_id": run.get("run_id", "unknown"),
            "note_type": "autonext-snapshot",
            "autonext_generated": True,
            "tags": ["autonext/snapshot", f"company/{symbol.lower()}", f"sector/{security.get('sector', 'unknown').lower()}"],
        }),
        f"# {symbol} · {security['company']} · {date}",
        "",
        "> [!warning] Research boundary",
        f"> {DISCLAIMER}",
        "> This is an immutable evidence snapshot. A checked source is not proof of the investment conclusion.",
        "",
        f"- Company: [[Companies/{symbol}|{security['company']}]]",
        f"- Thesis: [[Theses/{symbol} Thesis|{symbol} thesis]]",
        f"- Run ID: `{run.get('run_id')}`",
        f"- Source count: {len(run.get('sources', []))}",
    ]
    if observation:
        lines.extend([
            f"- Dated price: {observation['price']:.2f} {observation['currency']}",
            f"- Price observed at: {observation['observed_at']}",
        ])
    else:
        lines.append("- Dated price: **ABSTAIN** — no eligible checked observation")

    lines.extend(["", "## Latest operating release", ""])
    releases = release_results(run)
    if releases:
        lines.extend(["| Metric | Basis | Period | Reported |", "|---|---|---|---:|"])
        lines.extend(f"| {row['metric']} | {row['basis']} | {row['period']} | {format_value(row['value'], row['unit'])} |" for row in releases)
    else:
        lines.append("No manually reviewed operating release in this snapshot.")

    lines.extend(["", "## Current management outlook", ""])
    outlook = management_outlook(run)
    if outlook:
        lines.extend(["| Metric | Basis | Guided period | Guidance | Versus latest reported quarter |", "|---|---|---|---:|---:|"])
        for row in outlook:
            change = f"{row['midpoint_change_percent']:+.1f}%" if row["midpoint_change_percent"] is not None else "not comparable"
            lines.append(f"| {row['metric']} | {row['basis']} | {row['period']} | {guidance_display(row)} | {change} |")
        lines.extend(["", "Guidance midpoint changes are mechanical comparisons, not forecasts or consensus surprises."])
    else:
        lines.append("No still-current structured management outlook in this snapshot.")

    lines.extend(["", "## Filed sequential changes", ""])
    changes = delta.get("sequential_changes", [])[:8]
    if changes:
        lines.extend(["| Metric | Old period | New period | Change |", "|---|---|---|---:|"])
        lines.extend(f"| {row['metric']} | {row['old_period']} | {row['new_period']} | {format_value(row['change'], row['unit'])} |" for row in changes)
    else:
        lines.append("No unambiguous sequential change calculated.")

    lines.extend(["", "## Published expectation checks", ""])
    comparisons = run.get("expectation_comparisons", [])
    if comparisons:
        lines.extend(["| Metric | Expected | Actual | Outcome |", "|---|---:|---:|---|"])
        for row in comparisons:
            outcome = row.get("range_outcome", format_value(row["difference"], row["unit"]))
            lines.append(f"| {row['metric']} | {format_value(row['expected'], row['unit'])} | {format_value(row['actual'], row['unit'])} | {outcome} |")
    else:
        lines.append("No like-for-like expectation comparison available; no beat/miss inferred.")

    lines.extend(["", "## Normalized GAAP EPS hurdle context", ""])
    context = gaap_eps_hurdle(run)
    if context["status"] == "mechanical_context_not_forecast":
        lines.extend([
            f"- Latest quarterly GAAP diluted EPS: {context['latest_eps']['value']:.2f} · {context['latest_eps']['period']}",
            f"- Mechanical annualized run-rate: {context['annualized_quarterly_eps_run_rate']:.2f}",
            f"- Required terminal EPS: {context['required_terminal_eps']:.2f} · {context['years']:g} years · {context['terminal_pe']:g}x terminal P/E",
            f"- Implied growth from that run-rate: {context['implied_eps_cagr']:.1%} annually",
            f"- Limitation: {context['context_limitation']}",
        ])
    else:
        lines.append(f"**ABSTAIN:** {context['reason']}.")

    lines.extend(["", "## Price-implied sensitivity", ""])
    analyses = [
        item for item in run.get("earnings_analysis", [])
        if item.get("input", {}).get("scenario") and item.get("result")
    ]
    if analyses:
        lines.extend(["| Terminal P/E | Future shares | Required terminal EPS | Total earnings/current share |", "|---:|---:|---:|---:|"])
        for item in analyses:
            assumptions, result = item["input"]["scenario"], item["result"]
            if result.get("status") == "blocked":
                continue
            lines.append(f"| {assumptions['terminal_pe']}x | {assumptions['future_share_factor']}x | {result['required_terminal_eps']:.2f} | {result['required_total_earnings_per_current_share']:.2f} |")
    else:
        lines.append("No eligible price; sensitivity abstains.")

    lines.extend(["", "## Recognition catalyst coverage", ""])
    catalysts = run.get("catalysts", [])
    if catalysts:
        for item in catalysts:
            lines.append(f"- **{item['event']}** · expected {item['expected_at']} · weakens: {item['weakens']}")
    else:
        lines.append("**Research gap:** no sourced, dated recognition catalyst is present in this snapshot.")

    lines.extend([
        "",
        "## Questions this evidence does not answer",
        "",
        "- Which qualified product bottleneck creates durable pricing power?",
        "- Does growth convert to cash after capex, working capital, tax and dilution?",
        "- Can a defensible operating forecast clear the price-implied hurdle?",
        "- What competitor, customer qualification or architecture change would break the case?",
        "",
        "## Retained evidence",
        "",
    ])
    lines.extend(source_markdown(source) for source in run.get("sources", []))
    lines.extend(["", f"%% AutoNext snapshot link: {snapshot_link} %%", ""])
    return "\n".join(lines)


def dossier_note(dossier):
    symbol = dossier["ticker"].upper()
    state = dossier["security_state"]
    math = merger_math(dossier) if state["mode"] == "pending_all_stock_merger" else None
    lines = [
        frontmatter({
            "title": f"{symbol} Investment Dossier",
            "ticker": symbol,
            "company": dossier["company"],
            "as_of": dossier["as_of"],
            "security_mode": state["mode"],
            "note_type": "autonext-dossier",
            "autonext_generated": True,
            "tags": ["autonext/dossier", f"company/{symbol.lower()}", "security-state/merger"],
        }),
        f"# {symbol} · transaction-first investment dossier",
        "",
        "> [!danger] Security state changed",
        f"> **{state['mode'].replace('_', ' ').upper()}** — {state['primary_question']}",
        f"> {dossier['executive_view']['boundary']}",
        "",
        "## Executive view",
        "",
        dossier["executive_view"]["summary"],
        "",
        f"**Why the ordinary screen is wrong:** {dossier['executive_view']['why_the_old_screen_is_wrong']}",
        "",
        f"**Correct decision frame:** {dossier['executive_view']['decision_frame']}",
    ]
    if math:
        lines.extend([
            "",
            "## Fixed-ratio transaction math",
            "",
            f"Price basis: {math['observed_at']} · {math['currency']} · static same-time observations.",
            "",
            "| Input or output | Value |",
            "|---|---:|",
            f"| Contractual exchange ratio | {math['exchange_ratio']:.3f} MRVL / LITE |",
            f"| LITE price | {math['lite_price']:.2f} |",
            f"| MRVL price | {math['mrvl_price']:.2f} |",
            f"| Implied consideration | {math['implied_consideration']:.2f} |",
            f"| Gross spread | {math['gross_spread_per_lite_share']:.2f} · {math['gross_spread_percent']:.2%} |",
            f"| Effective market ratio | {math['effective_market_ratio']:.3f} MRVL / LITE |",
            f"| Discount to contractual ratio | {math['discount_to_contractual_ratio']:.2%} |",
            f"| MRVL break-even for the dated LITE price | {math['mrvl_break_even_for_lite_price']:.2f} |",
            "",
            f"> [!warning] Arithmetic boundary\n> {math['limitation']}",
        ])
    transaction = dossier["transaction"]
    lines.extend([
        "",
        "## Closing path",
        "",
        f"- Company-stated expected close: **{transaction['expected_close_company_statement']}**",
        f"- Initial outside date: **{transaction['initial_outside_date']}**",
        f"- Possible regulatory extensions: {', '.join(transaction['possible_regulatory_extensions'])}",
        "- Required conditions:",
        *[f"  - {item}" for item in transaction["closing_conditions"]],
        "",
        "## The three clocks",
        "",
        f"**Discovery — {dossier['three_clocks']['discovery']['date']}:** {dossier['three_clocks']['discovery']['event']}. {dossier['three_clocks']['discovery']['meaning']}",
        "",
        "**Recognition events**",
        "",
        *[f"- **{item['window']} — {item['event']}:** {item['why_it_matters']}" for item in dossier["three_clocks"]["recognition"]],
        "",
        f"**Monetisation — {dossier['three_clocks']['monetisation']['window']}:** {dossier['three_clocks']['monetisation']['meaning']}",
        "",
        "## Reinforcing capability stack",
        "",
        "| Layer | Capability | Evidence boundary |",
        "|---|---|---|",
        *[f"| {item['layer']} | {item['lumentum_capability']} | {item['evidence_status']} |" for item in dossier["capability_stack"]],
        "",
        "## Standalone operating evidence",
        "",
        *[f"- **{item['period']} · {item['classification']}:** {item['fact']}" for item in dossier["operating_evidence"]],
        "",
        "## Strategic logic",
        "",
        f"- Physical bottleneck: {dossier['strategic_logic']['physical_bottleneck']}",
        f"- Reinforcement loop: {dossier['strategic_logic']['reinforcement_loop']}",
        f"- Value-capture question: {dossier['strategic_logic']['value_capture_question']}",
        f"- Labeled inference: {dossier['strategic_logic']['labeled_inference']}",
        "",
        "## Scenario tree",
        "",
        *[f"### {item['name']}\n\n{item['mechanics']}\n\nDominant variables: {', '.join(item['dominant_variables'])}." for item in dossier["scenarios"]],
        "",
        "## Disconfirmers",
        "",
        *[f"- {item}" for item in dossier["disconfirmers"]],
        "",
        "## Open questions",
        "",
        *[f"- [ ] {item}" for item in dossier["open_questions"]],
        "",
        "## Sources",
        "",
        *[f"- [{source['title']}]({source['url']}) · {source['type']}" for source in dossier["sources"]],
        "",
    ])
    return "\n".join(lines)


def company_note(symbol, data, snapshot_link):
    run = data["run"]
    security, observation = run["security"], quote(run)
    mode = security_mode(symbol)
    dossier = load_dossier(symbol, required=False)
    price_line = f"{observation['price']:.2f} {observation['currency']} at {observation['observed_at']}" if observation else "ABSTAIN — no eligible checked observation"
    releases = release_results(run)
    release_lines = [f"- **{row['metric']} ({row['basis']}):** {format_value(row['value'], row['unit'])} · {row['period']}" for row in releases]
    outlook_lines = []
    for row in management_outlook(run):
        change = f" · {row['midpoint_change_percent']:+.1f}% vs latest reported quarter" if row["midpoint_change_percent"] is not None else ""
        outlook_lines.append(f"- **{row['metric']} ({row['basis']}):** {guidance_display(row)} · {row['period']}{change}")
    context = gaap_eps_hurdle(run)
    if context["status"] == "mechanical_context_not_forecast":
        context_lines = [
            f"- Latest-quarter GAAP diluted EPS annualized mechanically: {context['annualized_quarterly_eps_run_rate']:.2f}",
            f"- Required terminal EPS at 25x / 10% return / five years: {context['required_terminal_eps']:.2f}",
            f"- Implied growth from that run-rate: {context['implied_eps_cagr']:.1%} annually",
            f"- Limitation: {context['context_limitation']}",
        ]
    else:
        context_lines = [f"- **ABSTAIN:** {context['reason']}."]
    if dossier:
        state_lines = [
            f"- Mode: **{mode.replace('_', ' ').upper()}**",
            f"- Primary question: {dossier['security_state']['primary_question']}",
            f"- Full transaction-first analysis: [[Dossiers/{symbol}|{symbol} investment dossier]]",
            "- The operating evidence below is secondary, counterfactual context for delay or deal break.",
        ]
        hurdle_heading = "## Standalone counterfactual: normalized price hurdle"
    else:
        state_lines = ["- Mode: **STANDALONE**"]
        hurdle_heading = "## Normalized price hurdle"
    catalyst_line = (f"{len(run.get('catalysts', []))} sourced, dated catalyst(s)"
                     if run.get("catalysts") else "**Research gap:** no sourced, dated recognition catalyst")
    return "\n".join([
        frontmatter({
            "title": f"{symbol} — {security['company']}",
            "ticker": symbol,
            "company": security["company"],
            "exchange": security["exchange"],
            "sector": security.get("sector", "unknown"),
            "as_of": run.get("as_of", "unknown"),
            "run_id": run.get("run_id", "unknown"),
            "note_type": "autonext-company",
            "autonext_generated": True,
            "tags": ["autonext/company", f"company/{symbol.lower()}", f"sector/{security.get('sector', 'unknown').lower()}"],
        }),
        f"# {symbol} · {security['company']}",
        "",
        "> [!warning] Generated research view",
        f"> {DISCLAIMER}",
        "> Edit the linked thesis note, not this generated company page.",
        "",
        f"- My working thesis: [[Theses/{symbol} Thesis|{symbol} Thesis]]",
        f"- Latest immutable snapshot: [[{snapshot_link}|{run.get('as_of', '')[:10]} evidence snapshot]]",
        f"- Dated price: {price_line}",
        f"- Retained sources: {len(run.get('sources', []))}",
        "",
        "## Security state",
        "",
        *state_lines,
        "",
        "## Latest operating release",
        "",
        *(release_lines or ["No manually reviewed operating release in this snapshot."]),
        "",
        "## Current management outlook",
        "",
        *(outlook_lines or ["No still-current structured management outlook in this snapshot."]),
        "",
        hurdle_heading,
        "",
        *context_lines,
        "",
        "## Recognition catalyst coverage",
        "",
        catalyst_line,
        "",
        "## Research loop",
        "",
        f"1. Read [[{snapshot_link}|the immutable evidence snapshot]].",
        f"2. Update [[Theses/{symbol} Thesis|the human-owned thesis]] with what changed and what would falsify it.",
        "3. Use the terminal for searches, comparisons and explicit sensitivities.",
        "4. Preserve the dated thesis decision before the next evidence refresh.",
        "",
    ])


def thesis_template(symbol, security):
    return "\n".join([
        frontmatter({
            "title": f"{symbol} Thesis",
            "ticker": symbol,
            "company": security["company"],
            "sector": security.get("sector", "unknown"),
            "status": "researching",
            "conviction": "unrated",
            "note_type": "human-thesis",
            "tags": ["autonext/thesis", f"company/{symbol.lower()}"],
        }),
        f"# {symbol} Thesis",
        "",
        "> [!info] Human-owned note",
        "> AutoNext creates this template once and never overwrites it. Record your judgment here; keep sourced evidence in the linked snapshots.",
        "",
        f"- Generated company page: [[Companies/{symbol}|{symbol} company research]]",
        "",
        "## Current view",
        "",
        "What do I believe, with what confidence, and as of what date?",
        "",
        "## Why might the market be wrong?",
        "",
        "What is mispriced, and why has it remained mispriced?",
        "",
        "## Technical bottleneck and capability",
        "",
        "What must work in nature, and what evidence shows the state changed?",
        "",
        "## Commercialisation and value capture",
        "",
        "Who pays, what must be qualified, and which company captures the economics?",
        "",
        "## Recognition catalysts",
        "",
        "| Catalyst | Window | Evidence required | Probability | What price may already imply |",
        "|---|---|---|---:|---|",
        "|  |  |  |  |  |",
        "",
        "## Bear case and falsifiers",
        "",
        "- ",
        "",
        "## Financing and survival",
        "",
        "Can the company reach recognition without destructive financing?",
        "",
        "## Open questions",
        "",
        "- [ ] ",
        "",
        "## Decision log",
        "",
        "| Date | Decision or view change | Evidence | What would reverse it? |",
        "|---|---|---|---|",
        "|  |  |  |  |",
        "",
    ])


def export_obsidian(desk, output, json_output=False, emit=True):
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    date = str(desk.manifest.get("created_at", "unknown"))[:10]
    exported, created_theses = [], []
    for symbol in sorted(desk.companies):
        data = desk.companies[symbol]
        run = data["run"]
        snapshot_name = f"{symbol} {run.get('run_id', 'unknown')[:8]}"
        snapshot_link = f"Snapshots/{date}/{snapshot_name}"
        snapshot_path = output / "Snapshots" / date / f"{snapshot_name}.md"
        write_immutable(snapshot_path, snapshot_note(symbol, data, snapshot_link))
        write_generated(output / "Companies" / f"{symbol}.md", company_note(symbol, data, snapshot_link))
        dossier = load_dossier(symbol, required=False)
        dossier_path = None
        if dossier:
            dossier_path = output / "Dossiers" / f"{symbol}.md"
            write_generated(dossier_path, dossier_note(dossier))
        thesis_path = output / "Theses" / f"{symbol} Thesis.md"
        if not thesis_path.exists():
            thesis_path.parent.mkdir(parents=True, exist_ok=True)
            thesis_path.write_text(thesis_template(symbol, run["security"]), encoding="utf-8")
            created_theses.append(str(thesis_path))
        exported.append({"ticker": symbol, "company_note": str(output / "Companies" / f"{symbol}.md"), "snapshot": str(snapshot_path), "thesis": str(thesis_path), "dossier": str(dossier_path) if dossier_path else None})

    home = [
        frontmatter({"title": "AutoNext Research", "as_of": desk.manifest.get("created_at", "unknown"), "note_type": "autonext-home", "autonext_generated": True, "tags": ["autonext/home"]}),
        "# AutoNext Research",
        "",
        "> [!warning] Research boundary",
        f"> {DISCLAIMER}",
        "",
        f"Evidence desk: `{desk.path}`",
        "",
        "## Companies",
        "",
        "| Company | Security-state dossier | Working thesis | Latest evidence |",
        "|---|---|---|---|",
    ]
    for item in exported:
        symbol = item["ticker"]
        snapshot_name = Path(item["snapshot"]).stem
        dossier_link = f"[[Dossiers/{symbol}|Dossier]]" if item["dossier"] else "—"
        home.append(f"| [[Companies/{symbol}|{symbol}]] | {dossier_link} | [[Theses/{symbol} Thesis|Thesis]] | [[Snapshots/{date}/{snapshot_name}|{date}]] |")
    home.extend([
        "",
        "## Workflow",
        "",
        "```text",
        "primary evidence → terminal checks → immutable snapshot → human thesis → dated decision → later calibration",
        "```",
        "",
        "Generated company pages may be refreshed. Thesis notes are human-owned and are never overwritten.",
        "",
    ])
    write_generated(output / "AutoNext Research.md", "\n".join(home))
    result = {"vault_folder": str(output), "desk": str(desk.path), "companies": exported, "created_theses": created_theses, "limitation": DISCLAIMER}
    if emit and json_output:
        as_json(result)
    elif emit:
        print(f"Obsidian research workspace exported to {output}")
        print(f"Companies: {len(exported)} | New human-owned thesis notes: {len(created_theses)}")
        print(f"Open: {output / 'AutoNext Research.md'}")
        print("Generated company pages can refresh; immutable snapshots and thesis notes are preserved.")
    return result


def parse_iso(value):
    if not value:
        raise ValueError("Missing timestamp")
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def doctor(desk, vault=None, json_output=False, emit=True):
    checks = []

    def add(symbol, level, check, detail):
        checks.append({"ticker": symbol, "level": level, "check": check, "detail": detail})

    for symbol, data in sorted(desk.companies.items()):
        run = data["run"]
        dossier = load_dossier(symbol, required=False)
        sources = run.get("sources", [])
        releases = release_results(run)
        observation = quote(run)
        if sources:
            add(symbol, "pass", "sources", f"{len(sources)} retained sources")
        else:
            add(symbol, "fail", "sources", "no retained sources")
        if releases:
            add(symbol, "pass", "operating_release", f"{len(releases)} reviewed release observations")
        else:
            add(symbol, "warn", "operating_release", "no manually reviewed operating release")
        catalysts = run.get("catalysts", [])
        if catalysts:
            add(symbol, "pass", "dated_catalyst", f"{len(catalysts)} sourced catalyst records")
        else:
            add(symbol, "warn", "dated_catalyst", "no sourced, dated recognition catalyst")
        if dossier:
            add(symbol, "pass", "security_state", f"{dossier['security_state']['mode']} dossier as of {dossier['as_of']}")
        if observation:
            age_days = (parse_iso(run["as_of"]) - parse_iso(observation["observed_at"])).total_seconds() / 86400
            if age_days < 0 or age_days > 7:
                add(symbol, "fail", "dated_price", f"observation age {age_days:.1f} days")
            else:
                add(symbol, "pass", "dated_price", f"{observation['price']} {observation['currency']}; age {age_days:.1f} days")
            hurdles = sensitivity_rows(run)
            add(symbol, "pass" if hurdles else "fail", "sensitivities", f"{len(hurdles)} explicit scenarios")
        else:
            add(symbol, "warn", "dated_price", "no eligible checked price; valuation abstains")
        for name in ("run.json", "report.md", "changes.json"):
            artifact = desk.path / symbol / name
            add(symbol, "pass" if artifact.is_file() else "fail", "artifact", str(artifact))

    if vault:
        vault = Path(vault).resolve()
        home_path = vault / "AutoNext Research.md"
        home_ok = home_path.is_file() and GENERATED_MARKER in home_path.read_text(encoding="utf-8-sig")
        add("VAULT", "pass" if home_ok else "fail", "home_note", str(home_path))
        for symbol in sorted(desk.companies):
            company_path = vault / "Companies" / f"{symbol}.md"
            thesis_path = vault / "Theses" / f"{symbol} Thesis.md"
            snapshot_count = len(list((vault / "Snapshots").glob(f"**/{symbol} *.md"))) if (vault / "Snapshots").exists() else 0
            add(symbol, "pass" if company_path.is_file() else "fail", "vault_company", str(company_path))
            add(symbol, "pass" if thesis_path.is_file() else "fail", "vault_thesis", str(thesis_path))
            add(symbol, "pass" if snapshot_count else "fail", "vault_snapshot", f"{snapshot_count} immutable snapshots")
            if load_dossier(symbol, required=False):
                dossier_path = vault / "Dossiers" / f"{symbol}.md"
                add(symbol, "pass" if dossier_path.is_file() else "fail", "vault_dossier", str(dossier_path))

    failures = sum(row["level"] == "fail" for row in checks)
    warnings = sum(row["level"] == "warn" for row in checks)
    status = "fail" if failures else "warn" if warnings else "pass"
    result = {"status": status, "failures": failures, "warnings": warnings, "checks": checks, "desk": str(desk.path), "vault": str(Path(vault).resolve()) if vault else None}
    if emit and json_output:
        as_json(result)
    elif emit:
        print(f"AutoNext doctor: {status.upper()} | {failures} failures | {warnings} warnings")
        problems = [row for row in checks if row["level"] != "pass"]
        if problems:
            print(table(("Level", "Ticker", "Check", "Detail"), [(row["level"].upper(), row["ticker"], row["check"], row["detail"]) for row in problems]))
        else:
            print(f"Validated {len(desk.companies)} companies and all required artifacts.")
    return result


def run_workflow(vault, output=None, offline=False, refresh_sec=False, sec_user_agent=None, json_output=False):
    if refresh_sec and not sec_user_agent:
        raise ValueError("--sec-user-agent is required with --refresh-sec")
    if output is None:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
        output = ROOT / "outputs" / f"desk-{stamp}"
    output = Path(output).resolve()
    sec_results = None
    if refresh_sec:
        from sec_adapter import refresh
        sec_results = refresh(None, ROOT / "outputs" / "sec", sec_user_agent, datetime.now(timezone.utc).isoformat())
        failed = [row for row in sec_results if row["status"] != "ok"]
        if failed:
            raise ValueError("SEC refresh failed: " + "; ".join(f"{row['symbol']}: {row['error']}" for row in failed))
    from research_desk import build
    manifest = build(output, refresh_prices=not offline)
    failed = [row for row in manifest["companies"] if row["status"] != "ok"]
    if failed:
        raise ValueError("Desk build failed: " + "; ".join(f"{row['symbol']}: {row['error']}" for row in failed))
    desk = Desk(output)
    vault_result = export_obsidian(desk, vault, emit=False)
    health = doctor(desk, vault, emit=False)
    result = {"status": health["status"], "desk": str(output), "vault": str(Path(vault).resolve()), "sec_refresh": sec_results, "price_mode": "offline_abstain" if offline else "single_provider_checked", "manifest": manifest, "export": vault_result, "doctor": health}
    if json_output:
        as_json(result)
    else:
        print(f"AutoNext workflow: {health['status'].upper()}")
        print(f"Desk:  {output}")
        print(f"Vault: {Path(vault).resolve()}")
        print(f"Companies: {len(manifest['companies'])} | Doctor failures: {health['failures']} | warnings: {health['warnings']}")
        print("Prices: offline abstention" if offline else "Prices: refreshed and single-provider checked")
        print("SEC: refreshed" if refresh_sec else "SEC: latest hash-verified local captures")
    return result


def universe(desk, json_output=False):
    result = []
    for symbol in sorted(desk.companies):
        run = desk.companies[symbol]["run"]
        security = run["security"]
        observation = quote(run)
        result.append(
            {
                "ticker": symbol,
                "company": security["company"],
                "security_mode": security_mode(symbol),
                "price": observation.get("price") if observation else None,
                "currency": observation.get("currency") if observation else security.get("currency"),
                "price_observed_at": observation.get("observed_at") if observation else None,
                "sources": len(run.get("sources", [])),
                "outlook_rows": len(management_outlook(run)),
                "dated_catalysts": len(run.get("catalysts", [])),
                "as_of": run.get("as_of"),
                "run_id": run.get("run_id"),
            }
        )
    if json_output:
        as_json({"desk": str(desk.path), "companies": result, "limitation": DISCLAIMER})
        return
    rows = [
        (
            item["ticker"],
            item["company"],
            item["security_mode"].replace("pending_all_stock_merger", "MERGER").replace("standalone", "standalone"),
            format_value(item["price"], item["currency"]) if item["price"] is not None else "ABSTAIN",
            item["sources"],
            item["outlook_rows"],
            item["dated_catalysts"],
            (item["as_of"] or "")[:10],
        )
        for item in result
    ]
    print(f"AutoNext research universe\nDesk: {desk.path}\n")
    print(table(("Ticker", "Company", "Mode", "Dated price", "Sources", "Outlook", "Catalysts", "As of"), rows))
    print(f"\n{DISCLAIMER}")


def company(desk, symbol, json_output=False):
    data = desk.company(symbol)
    run, delta = data["run"], data["changes"]
    security, observation = run["security"], quote(run)
    mode = security_mode(symbol)
    dossier = load_dossier(symbol, required=False)
    payload = {
        "security": security,
        "security_mode": mode,
        "security_state_dossier": dossier,
        "transaction_math": merger_math(dossier) if dossier and mode == "pending_all_stock_merger" else None,
        "as_of": run.get("as_of"),
        "run_id": run.get("run_id"),
        "price_observation": observation,
        "latest_operating_release": release_results(run),
        "management_outlook": management_outlook(run),
        "expectation_comparisons": run.get("expectation_comparisons", []),
        "sequential_changes": delta.get("sequential_changes", []),
        "price_hurdles": sensitivity_rows(run),
        "gaap_eps_hurdle": gaap_eps_hurdle(run),
        "catalysts": run.get("catalysts", []),
        "source_count": len(run.get("sources", [])),
        "latest_source_published_at": max((row.get("published_at", "") for row in run.get("sources", [])), default=None),
        "report": str(desk.path / symbol.upper() / "report.md"),
        "snapshot": str(desk.path / symbol.upper() / "run.json"),
        "limitation": DISCLAIMER,
    }
    if json_output:
        as_json(payload)
        return
    print(f"{symbol.upper()} | {security['company']}\n{'=' * (len(symbol) + len(security['company']) + 3)}")
    print(f"Security: {security['exchange']}:{security['ticker']} | {security['currency']} | {security.get('sector', 'n/a')}")
    print(f"Security mode: {mode.replace('_', ' ').upper()}")
    if dossier:
        math = payload["transaction_math"]
        print(f"PRIMARY FRAME: {dossier['security_state']['primary_question']}")
        print(f"Dated merger math: {math['lite_price']:.2f} LITE vs {math['exchange_ratio']:.3f} x {math['mrvl_price']:.2f} MRVL = {math['implied_consideration']:.2f}; gross spread {math['gross_spread_percent']:.2%}")
        print("Run `python research_cli.py dossier LITE` for closing conditions, clocks, capability stack and scenario tree.")
    print(f"Evidence as of: {run.get('as_of')} | {payload['source_count']} retained sources")
    if observation:
        print(f"Dated price: {format_value(observation['price'], observation['currency'])} observed {observation['observed_at']}")
    else:
        print("Dated price: ABSTAIN - no eligible checked observation")

    releases = payload["latest_operating_release"]
    operating_label = "Standalone operating release (counterfactual if the deal breaks)" if dossier else "Latest manually reviewed operating release"
    print(f"\n{operating_label}")
    if releases:
        print(table(
            ("Metric", "Basis", "Period", "Reported"),
            [(row["metric"], row["basis"], row["period"], format_value(row["value"], row["unit"])) for row in releases],
        ))
    else:
        print("No manually reviewed operating release in this snapshot.")

    print("\nCurrent management outlook")
    outlook = payload["management_outlook"]
    if outlook:
        print(table(
            ("Metric", "Basis", "Guided period", "Guidance", "Vs latest quarter"),
            [(
                row["metric"], row["basis"], row["period"], guidance_display(row),
                f"{row['midpoint_change_percent']:+.1f}%" if row["midpoint_change_percent"] is not None else "not comparable",
            ) for row in outlook],
        ))
        print("Midpoint changes are mechanical like-for-like comparisons, not forecasts or consensus surprises.")
    else:
        print("No still-current structured management outlook in this snapshot.")

    print("\nFiled sequential changes")
    changes = payload["sequential_changes"][:8]
    if changes:
        print(table(
            ("Metric", "Old period", "New period", "Change"),
            [(row["metric"], row["old_period"], row["new_period"], format_value(row["change"], row["unit"])) for row in changes],
        ))
    else:
        print("No unambiguous sequential change calculated.")

    comparisons = payload["expectation_comparisons"]
    print("\nPublished expectation checks")
    if comparisons:
        print(table(
            ("Metric", "Expected", "Actual", "Outcome"),
            [(row["metric"], format_value(row["expected"], row["unit"]), format_value(row["actual"], row["unit"]), row.get("range_outcome", format_value(row["difference"], row["unit"]))) for row in comparisons],
        ))
    else:
        print("No like-for-like expectation comparison available; no beat/miss inferred.")

    hurdle_label = "Standalone counterfactual: normalized GAAP EPS hurdle" if dossier else "Normalized GAAP EPS hurdle context"
    print(f"\n{hurdle_label}")
    context = payload["gaap_eps_hurdle"]
    if context["status"] == "mechanical_context_not_forecast":
        print(f"Latest quarterly GAAP diluted EPS: {context['latest_eps']['value']:.2f} ({context['latest_eps']['period']})")
        print(f"Mechanical annualized run-rate: {context['annualized_quarterly_eps_run_rate']:.2f}")
        print(f"Required terminal EPS: {context['required_terminal_eps']:.2f} | implied {context['years']:g}y growth: {context['implied_eps_cagr']:.1%} annually")
        print(context["context_limitation"])
    else:
        print(f"ABSTAIN - {context['reason']}.")

    print("\nPrice-implied sensitivity")
    hurdles = payload["price_hurdles"]
    if hurdles:
        print(table(
            ("Terminal P/E", "Future shares", "Required terminal EPS", "Total earnings/current share"),
            [
                (
                    f"{row['scenario']['terminal_pe']}x",
                    f"{row['scenario']['future_share_factor']}x",
                    f"{row['result']['required_terminal_eps']:.2f}",
                    f"{row['result']['required_total_earnings_per_current_share']:.2f}",
                )
                for row in hurdles
            ],
        ))
    else:
        print("No eligible checked price; sensitivity abstains.")

    print("\nRecognition catalyst coverage")
    if payload["catalysts"]:
        for item in payload["catalysts"]:
            print(f"- {item['event']} | expected {item['expected_at']} | weakens: {item['weakens']}")
    else:
        print("RESEARCH GAP - no sourced, dated recognition catalyst in this snapshot.")

    print("\nUnresolved diligence")
    print("- Which qualified product bottleneck creates durable pricing power?")
    print("- Does growth convert to cash after capex, working capital, tax and dilution?")
    print("- What dated evidence could force market recognition, and what would falsify the case first?")
    print("- Can the company reach that event without destructive financing?")

    print("\nAudit trail")
    print(f"Report:   {payload['report']}\nSnapshot: {payload['snapshot']}")
    print(f"\n{DISCLAIMER}")


def dossier(desk, symbol, json_output=False):
    record = load_dossier(symbol)
    symbol = record["ticker"].upper()
    state = record["security_state"]
    math = merger_math(record) if state["mode"] == "pending_all_stock_merger" else None
    desk_quote = quote(desk.company(symbol)["run"]) if symbol in desk.companies else None
    payload = {
        "dossier": record,
        "transaction_math": math,
        "desk_target_quote": desk_quote,
        "limitation": DISCLAIMER,
    }
    if json_output:
        as_json(payload)
        return

    print(f"{symbol} | transaction-first investment dossier | as of {record['as_of']}")
    print("=" * 72)
    print(f"Security mode: {state['mode'].replace('_', ' ').upper()}")
    print(f"Primary question: {state['primary_question']}")
    print(f"\n{record['executive_view']['summary']}")
    print(f"Why the ordinary screen is wrong: {record['executive_view']['why_the_old_screen_is_wrong']}")

    if math:
        print("\nFixed-ratio transaction math")
        print(table(
            ("Measure", "Value"),
            [
                ("Price basis", math["observed_at"]),
                ("Contractual ratio", f"{math['exchange_ratio']:.3f} MRVL / LITE"),
                ("LITE price", f"{math['lite_price']:.2f} {math['currency']}"),
                ("MRVL price", f"{math['mrvl_price']:.2f} {math['currency']}"),
                ("Implied consideration", f"{math['implied_consideration']:.2f} {math['currency']}"),
                ("Gross spread", f"{math['gross_spread_per_lite_share']:.2f} / {math['gross_spread_percent']:.2%}"),
                ("Effective market ratio", f"{math['effective_market_ratio']:.3f} MRVL / LITE"),
                ("Discount to contractual ratio", f"{math['discount_to_contractual_ratio']:.2%}"),
                ("MRVL break-even", f"{math['mrvl_break_even_for_lite_price']:.2f} {math['currency']}"),
            ],
        ))
        print(math["limitation"])
        if desk_quote and desk_quote.get("observed_at") != math["observed_at"]:
            print(f"Desk note: a separate LITE quote exists at {desk_quote['observed_at']}; it is not mixed with the dated MRVL input above.")

    transaction = record["transaction"]
    print("\nClosing path")
    print(f"Expected close (company statement): {transaction['expected_close_company_statement']}")
    print(f"Initial outside date: {transaction['initial_outside_date']} | possible regulatory extensions: {', '.join(transaction['possible_regulatory_extensions'])}")
    for condition in transaction["closing_conditions"]:
        print(f"- {condition}")

    print("\nThree clocks")
    discovery = record["three_clocks"]["discovery"]
    print(f"Discovery: {discovery['date']} | {discovery['event']}")
    for item in record["three_clocks"]["recognition"]:
        print(f"Recognition: {item['window']} | {item['event']} | {item['why_it_matters']}")
    monetisation = record["three_clocks"]["monetisation"]
    print(f"Monetisation: {monetisation['window']} | {monetisation['event']}")

    print("\nReinforcing capability stack")
    print(table(
        ("Layer", "Lumentum / combined capability"),
        [(item["layer"], item["lumentum_capability"]) for item in record["capability_stack"]],
    ))

    print("\nScenario tree")
    for item in record["scenarios"]:
        print(f"- {item['name']}: {item['mechanics']}")
        print(f"  Dominant variables: {', '.join(item['dominant_variables'])}")

    print("\nNext disconfirming evidence")
    for item in record["disconfirmers"]:
        print(f"- {item}")

    print("\nOpen questions")
    for item in record["open_questions"]:
        print(f"- [ ] {item}")

    print(f"\nSources: {len(record['sources'])} | full linked list exports to Obsidian Dossiers/{symbol}.md")
    print(f"{record['executive_view']['boundary']}\n{DISCLAIMER}")


def compare(desk, terminal_pe, share_factor, years, required_return, sort_by, json_output=False):
    result = []
    for symbol, data in desk.companies.items():
        run = data["run"]
        mode = security_mode(symbol)
        if mode != "standalone":
            result.append({
                "ticker": symbol,
                "company": run["security"]["company"],
                "status": "corporate_action",
                "security_mode": mode,
                "reason": f"Standalone EPS screen is not primary; run dossier {symbol}",
            })
            continue
        observation = quote(run)
        if not observation:
            result.append({"ticker": symbol, "status": "abstain", "reason": "no eligible checked price"})
            continue
        row = scenario(observation["price"], years, required_return, terminal_pe, share_factor)
        context = gaap_eps_hurdle(run, years, required_return, terminal_pe, share_factor)
        revenue_outlook = next((item for item in management_outlook(run) if item.get("metric") == "revenue"), None)
        row.update(
            ticker=symbol,
            company=run["security"]["company"],
            currency=observation["currency"],
            price_observed_at=observation["observed_at"],
            gaap_eps_run_rate=context.get("annualized_quarterly_eps_run_rate"),
            implied_eps_cagr=context.get("implied_eps_cagr"),
            gaap_eps_context_reason=context.get("reason"),
            revenue_guidance_change_percent=revenue_outlook.get("midpoint_change_percent") if revenue_outlook else None,
        )
        result.append(row)
    available = [row for row in result if row.get("status") not in ("abstain", "corporate_action")]
    missing = [row for row in result if row.get("status") in ("abstain", "corporate_action")]
    if sort_by == "hurdle":
        available.sort(key=lambda row: (row.get("implied_eps_cagr") is None, row.get("implied_eps_cagr", float("inf"))))
    elif sort_by == "price":
        available.sort(key=lambda row: row["current_price"])
    else:
        available.sort(key=lambda row: row["ticker"])
    result = available + missing
    if json_output:
        as_json({"desk": str(desk.path), "scenario": {"years": years, "required_return": required_return, "terminal_pe": terminal_pe, "future_share_factor": share_factor}, "companies": result, "limitation": DISCLAIMER})
        return
    print(f"Transparent price-hurdle screen | {years:g}y | return {required_return:.1%} | terminal P/E {terminal_pe:g}x | future shares {share_factor:g}x\n")
    print(table(
        ("Ticker", "Dated price", "GAAP EPS run-rate", "Required terminal EPS", "Implied EPS CAGR", "Revenue guide vs latest"),
        [
            (
                row["ticker"], format_value(row["current_price"], row["currency"]),
                f"{row['gaap_eps_run_rate']:.2f}" if row.get("gaap_eps_run_rate") is not None else "ABSTAIN",
                f"{row['required_terminal_eps']:.2f}",
                f"{row['implied_eps_cagr']:.1%}" if row.get("implied_eps_cagr") is not None else "ABSTAIN",
                f"{row['revenue_guidance_change_percent']:+.1f}%" if row.get("revenue_guidance_change_percent") is not None else "not available",
            )
            if row.get("status") not in ("abstain", "corporate_action")
            else (row["ticker"], "CORPORATE ACTION", "-", "-", "-", row["reason"])
            if row.get("status") == "corporate_action"
            else (row["ticker"], "ABSTAIN", "-", "-", "-", row["reason"])
            for row in result
        ],
    ))
    print("\nPending corporate actions are excluded from the standalone EPS screen and routed to a transaction-first dossier.")
    print("GAAP EPS run-rate annualizes one latest quarter and ignores seasonality. Guidance uses management's range midpoint.")
    print(f"Sorting changes presentation only; neither column is an attractiveness ranking.\n{DISCLAIMER}")


def one_scenario(desk, symbol, years, required_return, terminal_pe, share_factor, json_output=False):
    mode = security_mode(symbol)
    if mode != "standalone":
        raise ValueError(f"{symbol.upper()} is {mode}; run `python research_cli.py dossier {symbol.upper()}` instead of a standalone EPS scenario")
    run = desk.company(symbol)["run"]
    observation = quote(run)
    if not observation:
        raise ValueError(f"{symbol.upper()} has no eligible checked price; scenario abstains")
    result = scenario(observation["price"], years, required_return, terminal_pe, share_factor)
    result.update(ticker=symbol.upper(), company=run["security"]["company"], currency=observation["currency"], price_observed_at=observation["observed_at"])
    if json_output:
        as_json(result)
        return
    print(f"{result['ticker']} | custom price-hurdle sensitivity")
    print(f"Dated price: {format_value(result['current_price'], result['currency'])} observed {result['price_observed_at']}")
    print(f"Inputs: {years:g} years | required return {required_return:.1%} | terminal P/E {terminal_pe:g}x | future shares {share_factor:g}x")
    print(f"Required terminal price: {format_value(result['required_terminal_price'], result['currency'])}")
    print(f"Required terminal EPS: {format_value(result['required_terminal_eps'], result['currency'])}")
    print(f"Required total earnings per current share: {format_value(result['required_total_earnings_per_current_share'], result['currency'])}")
    print(f"\n{DISCLAIMER}")


def search(desk, terms, symbol=None, limit=20, match="all", json_output=False):
    words = [word.lower() for word in terms if word.strip()]
    if not words:
        raise ValueError("Provide at least one search term")
    symbols = [symbol.upper()] if symbol else sorted(desk.companies)
    matches = []
    for ticker in symbols:
        run = desk.company(ticker)["run"]
        for source in run.get("sources", []):
            haystack = " ".join(str(source.get(key, "")) for key in ("title", "excerpt", "locator")).lower()
            matched = all(word in haystack for word in words) if match == "all" else any(word in haystack for word in words)
            if matched:
                matches.append({"ticker": ticker, "id": source.get("id"), "title": source.get("title"), "published_at": source.get("published_at"), "locator": source.get("locator"), "excerpt": source.get("excerpt")})
                if len(matches) >= limit:
                    break
        if len(matches) >= limit:
            break
    if json_output:
        as_json({"query": terms, "match": match, "matches": matches, "limitation": "Searches retained excerpts only; absence is not evidence of absence."})
        return
    print(f"Evidence search ({match} terms): {' '.join(terms)} | {len(matches)} retained-source matches\n")
    for index, item in enumerate(matches, 1):
        excerpt = console_text(" ".join((item.get("excerpt") or "").split()))
        if len(excerpt) > 240:
            excerpt = excerpt[:237] + "..."
        print(f"{index}. [{item['ticker']}] {item['title']} ({item['published_at']})\n   {excerpt}\n   {item['locator']}")
    if not matches:
        print(f"No retained excerpts matched {match} terms.")
    print("\nSearches retained excerpts only; absence is not evidence of absence.")


def parser():
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--desk", help="Generated desk directory; defaults to the newest outputs/desk-*")
    result.add_argument("--json", action="store_true", help="Machine-readable output")
    commands = result.add_subparsers(dest="command", required=True)
    commands.add_parser("universe", help="List available companies and dated observations")
    company_parser = commands.add_parser("company", help="Inspect one company's evidence and operating changes")
    company_parser.add_argument("ticker")
    dossier_parser = commands.add_parser("dossier", help="Inspect a transaction-first, sourced investment dossier")
    dossier_parser.add_argument("ticker")
    compare_parser = commands.add_parser("compare", help="Compare an explicit price-hurdle sensitivity across companies")
    scenario_parser = commands.add_parser("scenario", help="Calculate a custom price-hurdle sensitivity for one company")
    scenario_parser.add_argument("ticker")
    for command in (compare_parser, scenario_parser):
        command.add_argument("--years", type=float, default=5)
        command.add_argument("--return-rate", type=float, default=0.10)
        command.add_argument("--terminal-pe", type=float, default=25)
        command.add_argument("--share-factor", type=float, default=1.0)
    compare_parser.add_argument("--sort", choices=("ticker", "hurdle", "price"), default="ticker")
    search_parser = commands.add_parser("search", help="Search retained source titles and excerpts")
    search_parser.add_argument("terms", nargs="+")
    search_parser.add_argument("--ticker")
    search_parser.add_argument("--limit", type=int, default=20)
    search_parser.add_argument("--match", choices=("all", "any"), default="all", help="Require all terms or accept any term")
    obsidian_parser = commands.add_parser("obsidian", help="Export generated research and human-owned thesis notes to an Obsidian folder")
    obsidian_parser.add_argument("--output", required=True, help="Destination folder inside an Obsidian vault, or a preview folder")
    doctor_parser = commands.add_parser("doctor", help="Validate evidence freshness, analysis artifacts and optional Obsidian export")
    doctor_parser.add_argument("--vault", help="Optional AutoNext folder inside an Obsidian vault")
    workflow_parser = commands.add_parser("workflow", help="Build, export and validate the complete local research workflow")
    workflow_parser.add_argument("--vault", required=True, help="AutoNext folder inside an Obsidian vault")
    workflow_parser.add_argument("--output", help="New desk output directory; defaults to a timestamped outputs/desk-* path")
    workflow_parser.add_argument("--offline", action="store_true", help="Do not fetch prices; valuation explicitly abstains")
    workflow_parser.add_argument("--refresh-sec", action="store_true", help="Refresh public SEC captures before building")
    workflow_parser.add_argument("--sec-user-agent", help="Descriptive SEC application/contact string; required with --refresh-sec")
    return result


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        if args.command == "workflow":
            result = run_workflow(args.vault, args.output, args.offline, args.refresh_sec, args.sec_user_agent, args.json)
            return 2 if result["doctor"]["failures"] else 0
        desk = Desk(args.desk)
        if args.command == "universe":
            universe(desk, args.json)
        elif args.command == "company":
            company(desk, args.ticker, args.json)
        elif args.command == "dossier":
            dossier(desk, args.ticker, args.json)
        elif args.command == "compare":
            compare(desk, args.terminal_pe, args.share_factor, args.years, args.return_rate, args.sort, args.json)
        elif args.command == "scenario":
            one_scenario(desk, args.ticker, args.years, args.return_rate, args.terminal_pe, args.share_factor, args.json)
        elif args.command == "search":
            if args.limit <= 0:
                raise ValueError("Search limit must be positive")
            search(desk, args.terms, args.ticker, args.limit, args.match, args.json)
        elif args.command == "obsidian":
            export_obsidian(desk, args.output, args.json)
        else:
            result = doctor(desk, args.vault, args.json)
            return 2 if result["failures"] else 0
        return 0
    except (ValueError, KeyError, OSError, json.JSONDecodeError) as exc:
        print(f"AutoNext research: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
