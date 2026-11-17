import json
import unittest
from pathlib import Path
import autonext as a

class OperatingEvidenceTests(unittest.TestCase):
 def load(self,ticker):
  return json.loads((Path(__file__).resolve().parents[1]/'examples'/'primary_operating_20261117'/(ticker+'.json')).read_text())
 def test_five_public_valid_bundles(self):
  for ticker in ['COHR','LITE','FN','AAOI','IPGP']:
   b=self.load(ticker);a.validate(b)
   self.assertFalse(b['valuations'])
   self.assertTrue(all(x['kind'] in ['observed_result','management_guidance'] for x in b['expectations']))
 def test_basic_not_diluted(self):
  b=self.load('AAOI');eps=[x for x in b['expectations'] if x['metric']=='EPS' and x['kind']=='observed_result']
  self.assertEqual([x['basis'] for x in eps],['GAAP basic','issuer-defined non-GAAP diluted'])
 def test_next_quarter_guidance_not_actual(self):
  for ticker in ['LITE','FN','AAOI','IPGP']:
   b=self.load(ticker);db=a.connect(':memory:')
   try:
    a.ingest(db,b);r=a.build_run(db,b['security']['id'],'2027-01-01T00:00:00Z')
    self.assertEqual(r['expectation_comparisons'],[])
    self.assertIsNone(r['valuation'])
    self.assertEqual(r['earnings_analysis'],[])
   finally:db.close()
 def test_no_pretend_historical_capture(self):
  b=self.load('LITE');db=a.connect(':memory:')
  try:
   a.ingest(db,b);r=a.build_run(db,b['security']['id'],'2026-11-03T00:00:00Z','captured')
   self.assertEqual(r['expectations'],[])
  finally:db.close()
