import unittest
from datetime import date,timedelta
from historical_pilot import events,outcomes

def fact(id,start,end,known,value):
 return dict(id=id,start=start,end=end,known_at=known,value=value,kind='observed_result',metric='revenue',unit='USD',basis='us-gaap:Revenue')
class PilotTests(unittest.TestCase):
 def bundle(self):
  return {'expectations':[fact('prior','2019-01-01','2019-03-31','2019-05-01T20:00:00Z',100),fact('now','2020-01-01','2020-03-31','2020-05-01T20:00:00Z',120)]}
 def test_future_revision_excluded(self):
  b=self.bundle(); b['expectations'].append(fact('later','2019-01-01','2019-03-31','2021-05-01T20:00:00Z',200))
  self.assertAlmostEqual(list(events(b))[0]['growth'],.2)
 def test_next_session_and_costs(self):
  p={date(2020,5,1)+timedelta(days=i):100+i for i in range(100)}
  s={d:100 for d in p}
  r=outcomes(self.bundle(),p,s)[0]
  self.assertEqual(r['entry'],'2020-05-02')
  self.assertEqual(r['exit'],'2020-07-04')
  self.assertLess(r['net_return'],r['gross_return'])
 def test_unmatured_excluded(self):
  p={date(2020,5,1):100,date(2020,5,4):101}
  self.assertEqual(outcomes(self.bundle(),p,p),[])
 def test_half_year_excluded(self):
  b=self.bundle();b['expectations'][1]['start']='2019-10-01'
  self.assertEqual(list(events(b)),[])
