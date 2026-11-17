import unittest
from sec_ledger import changes
class LedgerChangesTests(unittest.TestCase):
 def row(self,id,start,end,value,known="2026-11-01T00:00:00Z",basis="us-gaap:Revenue"):
  return {"id":id,"kind":"observed_result","metric":"revenue","period":str(start)+"/"+end,"basis":basis,"unit":"USD","value":value,"start":start,"end":end,"known_at":known}
 def run_rows(self,*rows):
  return changes({"as_of":"2026-11-16T00:00:00Z","expectations":list(rows)})
 def test_ytd_not_compared_to_quarter(self):
  r=self.run_rows(self.row("a","2026-01-01","2026-06-30",20),self.row("b","2026-07-01","2026-09-30",10))
  self.assertEqual(r["sequential_changes"],[])
 def test_quarter_comparison(self):
  r=self.run_rows(self.row("a","2026-04-01","2026-06-30",10),self.row("b","2026-07-01","2026-09-30",15))
  self.assertEqual(r["sequential_changes"][0]["percent"],50)
 def test_stale_legacy_tag_excluded(self):
  r=self.run_rows(self.row("a","2018-01-01","2018-03-31",10),self.row("b","2018-04-01","2018-06-30",15),self.row("c","2026-07-01","2026-09-30",20,basis="newtag"))
  self.assertEqual(r["sequential_changes"],[])
 def test_revision_retained(self):
  r=self.run_rows(self.row("a","2026-04-01","2026-06-30",10,known="2026-08-01T00:00:00Z"),self.row("b","2026-04-01","2026-06-30",11))
  self.assertEqual(len(r["revisions"]),1)
 def test_conflicting_same_time_excluded(self):
  r=self.run_rows(self.row("a","2026-04-01","2026-06-30",10),self.row("b","2026-04-01","2026-06-30",11))
  self.assertEqual(len(r["ambiguous_facts"]),1)
 def test_negative_denominator_no_percent(self):
  r=self.run_rows(self.row("a","2026-04-01","2026-06-30",-10),self.row("b","2026-07-01","2026-09-30",15))
  self.assertIsNone(r["sequential_changes"][0]["percent"])

