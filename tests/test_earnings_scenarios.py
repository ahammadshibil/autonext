import copy
import json
import unittest
from pathlib import Path
import autonext as a


class EarningsTests(unittest.TestCase):
    def setUp(self):
        self.b = json.loads(Path('examples/photonics_demo.json').read_text(encoding='utf-8-sig'))
        self.row = dict(id='earnings1', known_at='2025-01-02T00:00:00Z', source_ids=['price'],
            price_observation=dict(price=100, observed_at='2025-01-01T00:00:00Z',
                captured_at='2025-01-03T00:00:00Z', security_id=self.b['security']['id'],
                currency='USD', source_id='price', verified=True,
                adjustment_basis='unadjusted_per_current_share'),
            scenario=dict(years=5, required_return=.1, terminal_pe=20, future_share_factor=1.2,
                rationale='Synthetic demonstration only. Not a real-company forecast.'))
        self.b['earnings_scenarios'] = [self.row]

    def run_case(self, cutoff='2026-03-01T00:00:00Z', mode='published'):
        db = a.connect(':memory:')
        try:
            a.ingest(db, self.b)
            return a.build_run(db, self.b['security']['id'], cutoff, mode)
        finally:
            db.close()

    def test_integrated_hurdle(self):
        r = self.run_case()
        result = r['earnings_analysis'][0]['result']
        self.assertAlmostEqual(result['required_terminal_eps'], 8.05255)
        self.assertAlmostEqual(result['required_total_earnings_per_current_share'], 9.66306)
        self.assertIn('Per-share earnings scenarios', a.report(r))
        self.assertIn('Synthetic demonstration', a.report(r))

    def test_dilution_does_not_double_count_eps(self):
        first = self.run_case()['earnings_analysis'][0]['result']
        self.row['scenario']['future_share_factor'] = 1.5
        second = self.run_case()['earnings_analysis'][0]['result']
        self.assertEqual(first['required_terminal_eps'], second['required_terminal_eps'])
        self.assertGreater(second['required_total_earnings_per_current_share'], first['required_total_earnings_per_current_share'])

    def test_unverified_abstains(self):
        self.row['price_observation']['verified'] = False
        r = self.run_case()
        self.assertEqual(r['earnings_analysis'][0]['result']['status'], 'blocked')
        self.assertIn('Blocked:', a.report(r))

    def test_adjustment_abstains(self):
        self.row['price_observation']['adjustment_basis'] = 'unknown'
        self.assertEqual(self.run_case()['earnings_analysis'][0]['result']['status'], 'blocked')

    def test_as_of_and_diff(self):
        earlier = self.run_case('2025-01-01T00:00:00Z')
        later = self.run_case()
        self.assertEqual(earlier['earnings_analysis'], [])
        self.assertEqual(len(a.difference(earlier, later)['changes']['earnings_scenarios']['added']), 1)

    def test_capture_cutoff(self):
        self.assertEqual(self.run_case('2025-01-02T00:00:00Z', 'captured')['earnings_analysis'], [])
        self.assertEqual(len(self.run_case('2025-01-03T00:00:00Z', 'captured')['earnings_analysis']), 1)

    def test_identity_currency_and_source(self):
        for key, value in [('security_id', 'OTHER'), ('currency', 'EUR'), ('source_id', 'missing')]:
            with self.subTest(key=key):
                old = self.row['price_observation'][key]
                self.row['price_observation'][key] = value
                with self.assertRaises(ValueError): a.validate(self.b)
                self.row['price_observation'][key] = old

    def test_missing_rationale_and_nonfinite(self):
        self.row['scenario']['rationale'] = ''
        with self.assertRaises(ValueError): a.validate(self.b)
        self.row['scenario']['rationale'] = 'Synthetic'
        for key in ['years', 'terminal_pe', 'required_return', 'future_share_factor']:
            old = self.row['scenario'][key]
            self.row['scenario'][key] = float('nan')
            with self.assertRaises(ValueError): a.validate(self.b)
            self.row['scenario'][key] = old

    def test_observation_time_and_timezone(self):
        self.row['price_observation']['observed_at'] = '2025-01-04T00:00:00Z'
        with self.assertRaises(ValueError): a.validate(self.b)
        self.row['price_observation']['observed_at'] = '2025-01-01'
        with self.assertRaises(ValueError): a.validate(self.b)

    def test_scenario_eps_basis(self):
        self.row['scenario']['terminal_eps'] = 10
        with self.assertRaises(ValueError): a.validate(self.b)
        self.row['scenario']['terminal_eps_basis'] = 'net_income_per_future_diluted_share'
        result = self.run_case()['earnings_analysis'][0]['result']
        self.assertAlmostEqual(result['scenario_annualized_return'], 2 ** .2 - 1)
        self.assertGreater(result['eps_above_hurdle'], 0)

    def test_immutable_scenario_and_old_run_diff(self):
        db = a.connect(':memory:')
        try:
            a.ingest(db, self.b)
            self.row['scenario']['terminal_pe'] = 30
            a.ingest(db, self.b)
            with self.assertRaises(ValueError):
                a.build_run(db, self.b['security']['id'], '2026-03-01T00:00:00Z')
        finally: db.close()
        r = self.run_case()
        old = copy.deepcopy(r)
        old.pop('earnings_scenarios')
        self.assertEqual(len(a.difference(old, r)['changes']['earnings_scenarios']['added']), 1)


if __name__ == '__main__': unittest.main()
