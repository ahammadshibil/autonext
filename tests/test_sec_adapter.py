import copy
import unittest
from sec_adapter import build_research, filing_rows
class SecTests(unittest.TestCase):
 def setUp(self):
  self.sub={"cik":1,"name":"Test","tickers":["T"],"filings":{"recent":{"accessionNumber":["0000000001-26-000001"],"acceptanceDateTime":["2026-02-10T15:00:00Z"],"form":["10-Q"],"primaryDocument":["q.htm"],"reportDate":["2025-12-31"]}}}
  self.f={"cik":1,"facts":{"us-gaap":{"Revenues":{"units":{"USD":[{"accn":"0000000001-26-000001","end":"2025-12-31","start":"2025-10-01","val":10,"form":"10-Q"}]}}}}}
  self.rec=[{"captured_at":"2026-03-01T00:00:00Z"}]
 def run_at(self,date="2026-02-11T00:00:00Z",mode="published"):
  return build_research(self.sub,self.f,self.rec,date,mode)
 def test_pre_release_excluded(self):
  self.assertEqual(self.run_at("2026-02-10T14:59:59Z")["metrics"]["revenue"],[])
 def test_exact_release_included(self):
  self.assertEqual(self.run_at("2026-02-10T15:00:00Z")["metrics"]["revenue"][0]["val"],10)
 def test_captured_blocks_hindsight(self):
  with self.assertRaises(ValueError): self.run_at(mode="captured")
 def test_durations_not_summed(self):
  f=copy.deepcopy(self.f["facts"]["us-gaap"]["Revenues"]["units"]["USD"][0]); f["start"]="2025-01-01";f["val"]=30
  self.f["facts"]["us-gaap"]["Revenues"]["units"]["USD"].append(f)
  self.assertEqual(len(self.run_at()["metrics"]["revenue"]),2)
 def test_unknown_accession_excluded(self):
  self.f["facts"]["us-gaap"]["Revenues"]["units"]["USD"][0]["accn"]="missing"
  self.assertEqual(self.run_at()["metrics"]["revenue"],[])
 def test_no_invented_price(self):
  self.assertIsNone(self.run_at()["price"])
 def test_identity_mismatch(self):
  self.f["cik"]=2
  with self.assertRaises(ValueError): self.run_at()
 def test_malformed_columns(self):
  self.sub["filings"]["recent"]["form"]=[]
  with self.assertRaises(ValueError): self.run_at()
 def test_bad_path(self):
  self.sub["filings"]["recent"]["primaryDocument"]=["../bad"]
  with self.assertRaises(ValueError): self.run_at()
 def test_naive_cutoff(self):
  with self.assertRaises(ValueError): self.run_at("2026-02-11")


 def test_legitimate_nested_sec_path(self):
  self.sub["filings"]["recent"]["primaryDocument"]=["xslF345X06/form.xml"]
  self.assertIn("xslF345X06/form.xml",self.run_at()["filings"][0]["url"])
