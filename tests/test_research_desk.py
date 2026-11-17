import copy,json,tempfile,unittest
from pathlib import Path
from datetime import datetime,timezone
from unittest.mock import patch
import research_desk as d

class DeskTests(unittest.TestCase):
 def setUp(self):
  self.s=dict(id='NYSE:FN:COMMON',company='Fabrinet',ticker='FN',exchange='NYSE',share_class='common',currency='USD',sector='photonics')
  self.now='2026-11-17T12:00:00+00:00'
  self.meta=dict(symbol='FN',currency='USD',exchangeName='NYQ',instrumentType='EQUITY',regularMarketPrice=100,regularMarketTime=int(datetime(2026,11,16,21,tzinfo=timezone.utc).timestamp()))
 def raw(self):return json.dumps({'chart':{'result':[{'meta':self.meta}]}}).encode()
 def fixture_archive(self,symbol,_archive):
  source=d.read_json(d.ROOT/'examples/primary_operating_20261117'/(symbol+'.json'))
  return {'security':source['security'],'sources':[],'claims':[],'expectations':[],
          'catalysts':[],'valuations':[],'earnings_scenarios':[]}
 def test_quote_grid(self):
  b=d.quote_bundle(self.s,self.raw(),self.now)
  self.assertEqual(len(b['earnings_scenarios']),6)
  self.assertTrue(all(r['price_observation']['price']==100 for r in b['earnings_scenarios']))
 def test_wrong_symbol_rejected(self):
  self.meta['symbol']='FAKE'
  with self.assertRaises(ValueError):d.quote_bundle(self.s,self.raw(),self.now)
 def test_stale_quote_rejected(self):
  with self.assertRaises(ValueError):d.quote_bundle(self.s,self.raw(),'2026-12-01T00:00:00Z')
 def test_future_quote_rejected(self):
  with self.assertRaises(ValueError):d.quote_bundle(self.s,self.raw(),'2026-11-01T00:00:00Z')
 def test_exchange_rejected(self):
  self.meta['exchangeName']='NMS'
  with self.assertRaises(ValueError):d.quote_bundle(self.s,self.raw(),self.now)
 def test_bad_price_rejected(self):
  self.meta['regularMarketPrice']=float('nan')
  with self.assertRaises(ValueError):d.quote_bundle(self.s,self.raw(),self.now)
 def test_links_escaped(self):
  self.assertEqual(d.safe_link('javascript:alert(1)','<hi>'),'&lt;hi&gt;')
 def test_existing_output_not_overwritten(self):
  with tempfile.TemporaryDirectory() as folder:
   p=Path(folder)/'sentinel';p.write_text('keep')
   with self.assertRaises(FileExistsError):d.build(folder)
   self.assertEqual(p.read_text(),'keep')
 def test_missing_archive_explains_refresh(self):
  with tempfile.TemporaryDirectory() as folder:
   with self.assertRaisesRegex(ValueError,'--refresh-sec'):
    d.archived_bundle('FN',Path(folder))
 def test_offline_pipeline(self):
  with tempfile.TemporaryDirectory() as folder:
   with patch('research_desk.archived_bundle',side_effect=self.fixture_archive):
    result=d.build(Path(folder)/'desk')
   self.assertEqual(len(result['companies']),5)
   self.assertTrue(all(r['status']=='ok' for r in result['companies']))
   self.assertTrue(all(r['quote_status'].startswith('Price refresh not') for r in result['companies']))
   self.assertTrue((Path(folder)/'desk/index.html').exists())
