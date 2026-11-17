import copy,json,unittest
from pathlib import Path
import sector_analysis as s
class SectorTests(unittest.TestCase):
 def setUp(self):self.d=json.loads(Path("examples/photonics_sector.json").read_text())
 def test_five_companies(self):self.assertEqual(len(s.validate(self.d)["companies"]),5)
 def test_ipgp_not_datacenter_peer(self):
  pairs=s.pairs(self.d)
  self.assertFalse(any(p["a"]=="IPGP" or p["b"]=="IPGP" for p in pairs if "datacenter-components" in p["overlap"]))
 def test_manufacturer_not_automatic_competitor(self):
  self.assertFalse(any("FN" in (p["a"],p["b"]) for p in s.pairs(self.d)))
 def test_unknown_not_monopoly(self):
  self.assertEqual(s.bottleneck(self.d["companies"][0])["result"],"unproven")
 def test_physical_difficulty_not_enough(self):
  c=self.d["companies"][0];c["bottleneck_evidence"]["physical_difficulty"]="supported"
  self.assertEqual(s.bottleneck(c)["result"],"unproven")
 def test_missing_source_rejected(self):
  self.d["companies"][0]["source_ids"]=["absent"]
  with self.assertRaises(ValueError):s.validate(self.d)
 def test_causal_forecast_not_invented(self):
  self.d["scenarios"][0]["probability"]=.9
  with self.assertRaises(ValueError):s.validate(self.d)
 def test_falsifier_required(self):
  self.d["scenarios"][0]["steps"][0]["falsifier"]=""
  with self.assertRaises(ValueError):s.validate(self.d)
 def test_all_gates_not_monopoly(self):
  c=self.d["companies"][0];c["bottleneck_evidence"]={g:"supported" for g in s.GATES}
  self.assertEqual(s.bottleneck(c)["result"],"supported_candidate_not_monopoly")

