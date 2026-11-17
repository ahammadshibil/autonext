"""Dated per-share scenarios. Assumptions are never consensus or recommendations."""
import math
from datetime import datetime


def _time(value):
    t = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if t.tzinfo is None:
        raise ValueError('Timezone required for price provenance')
    return t


def _positive(value, name, zero=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(name + ' must be finite')
    if value < 0 or (not zero and value == 0):
        raise ValueError(name + ' outside valid domain')
    return value


def validate_scenario(row, security):
    p, a = row['price_observation'], row['scenario']
    _positive(p['price'], 'price')
    observed, captured = _time(p['observed_at']), _time(p['captured_at'])
    if captured < observed or _time(row['known_at']) < observed:
        raise ValueError('Price chronology is inconsistent')
    if p['security_id'] != security['id'] or p['currency'] != security['currency']:
        raise ValueError('Price security or currency mismatch')
    if p['source_id'] not in row['source_ids']:
        raise ValueError('Price source must be a retained row source')
    if type(p['verified']) is not bool or not str(p['adjustment_basis']).strip():
        raise ValueError('Explicit price verification and adjustment basis required')
    for key in ('years', 'terminal_pe', 'future_share_factor'):
        _positive(a[key], key)
    _positive(a['required_return'], 'required_return', zero=True)
    if a['years'] > 30 or a['required_return'] > 1:
        raise ValueError('Scenario horizon or return outside valid domain')
    if not isinstance(a.get('rationale'), str) or not a['rationale'].strip():
        raise ValueError('Explicit assumption rationale required')
    if 'terminal_eps' in a:
        if a.get('terminal_eps_basis') != 'net_income_per_future_diluted_share':
            raise ValueError('Operating case must use future diluted net-income EPS')
        _positive(a['terminal_eps'], 'terminal_eps', zero=True)


def evaluate(row):
    p, a = row['price_observation'], row['scenario']
    if not p['verified']:
        return {'status': 'blocked', 'reason': 'Price is reference-only, not verified for valuation'}
    if p['adjustment_basis'] != 'unadjusted_per_current_share':
        return {'status': 'blocked', 'reason': 'Resolve price split/adjustment basis before valuation'}
    hurdle = p['price'] * (1 + a['required_return']) ** a['years'] / a['terminal_pe']
    total = hurdle * a['future_share_factor']
    if not math.isfinite(hurdle) or not math.isfinite(total):
        raise ValueError('Scenario produces non-finite output')
    result = {'status': 'scenario_not_forecast', 'required_terminal_eps': hurdle,
              'required_total_earnings_per_current_share': total,
              'currency': p['currency'], 'price_observed_at': p['observed_at'],
              'limitation': 'Scenario assumptions, not market consensus, a forecast, price target or ranking. No interim distributions. EPS must reflect tax, interest and future dilution.'}
    if 'terminal_eps' in a:
        result['assumed_terminal_eps'] = a['terminal_eps']
        result['eps_above_hurdle'] = a['terminal_eps'] - hurdle
        try:
            annual = (a['terminal_eps'] * a['terminal_pe'] / p['price']) ** (1 / a['years']) - 1
        except OverflowError as exc:
            raise ValueError('Scenario return exceeds numeric range') from exc
        if not math.isfinite(annual):
            raise ValueError('Scenario return is not finite')
        result['scenario_annualized_return'] = annual
    return result
