import copy
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
import autonext as a

FIXTURE = Path(__file__).resolve().parents[1] / "examples/photonics_demo.json"

class ResearchTests(unittest.TestCase):
    def setUp(self):
        self.b = json.loads(FIXTURE.read_text(encoding="utf-8-sig"))
        self.db = a.connect(":memory:")
        a.ingest(self.db, self.b)

    def tearDown(self):
        self.db.close()

    def run_at(self, date="2026-03-01T00:00:00Z", mode="published"):
        return a.build_run(self.db, self.b["security"]["id"], date, mode)

    def test_no_future_claims_or_results(self):
        r = self.run_at("2025-12-31T23:59:59Z")
        self.assertEqual([c["id"] for c in r["claims"]], ["c1"])
        self.assertEqual(r["expectation_comparisons"], [])
        self.assertNotIn("s2", [s["id"] for s in r["sources"]])

    def test_comparison_is_exact_and_typed(self):
        r = self.run_at()
        c = r["expectation_comparisons"][0]
        self.assertEqual(c["difference"], -10000000)
        self.assertEqual(c["kind"], "management_guidance")

    def test_incompatible_basis_is_not_compared(self):
        b = copy.deepcopy(self.b)
        b["expectations"][1]["basis"] = "non-GAAP"
        db = a.connect(":memory:"); a.ingest(db,b)
        self.assertEqual(a.build_run(db,b["security"]["id"],"2026-03-01T00:00:00Z")["expectation_comparisons"], [])
        db.close()

    def test_reverse_valuation_accounts_for_dilution(self):
        v = self.b["valuations"][0]
        expected = (10 * 1.12**5 * 120000000 + 20000000 - 30000000)/5
        self.assertAlmostEqual(a.reverse_valuation(v)["implied_terminal_revenue"], expected)
        less_dilution = dict(v, future_shares=100000000)
        self.assertLess(a.reverse_valuation(less_dilution)["implied_terminal_revenue"], expected)

    def test_zero_multiple_rejected(self):
        self.b["valuations"][0]["terminal_revenue_multiple"] = 0
        with self.assertRaises(ValueError): a.validate(self.b)

    def test_nan_rejected(self):
        self.b["valuations"][0]["price"] = float("nan")
        with self.assertRaises(ValueError): a.validate(self.b)

    def test_mixed_units_rejected(self):
        self.b["valuations"][0]["units"] = "millions"
        with self.assertRaises(ValueError): a.validate(self.b)

    def test_missing_sources_rejected(self):
        self.b["claims"][0]["source_ids"] = ["missing"]
        with self.assertRaises(ValueError): a.validate(self.b)

    def test_private_material_rejected(self):
        self.b["sources"][0]["visibility"] = "confidential"
        with self.assertRaises(ValueError): a.validate(self.b)

    def test_timezone_required(self):
        with self.assertRaises(ValueError): self.run_at("2026-03-01")

    def test_known_before_source_rejected(self):
        self.b["claims"][1]["known_at"] = "2025-01-01T00:00:00Z"
        with self.assertRaises(ValueError): a.validate(self.b)

    def test_retained_snapshot_mode(self):
        self.b["sources"][0]["captured_at"] = "2026-03-01T00:00:00Z"
        db = a.connect(":memory:"); a.ingest(db,self.b)
        r = a.build_run(db,self.b["security"]["id"],"2025-12-31T00:00:00Z","captured")
        self.assertEqual(r["claims"], [])
        db.close()

    def test_deterministic_run(self):
        self.assertEqual(self.run_at()["run_id"], self.run_at()["run_id"])

    def test_idempotent_import(self):
        a.ingest(self.db,self.b)
        self.assertEqual(self.db.execute("SELECT count(*) FROM bundles").fetchone()[0],1)

    def test_conflicting_immutable_source_rejected(self):
        b=copy.deepcopy(self.b); b["sources"][0]["excerpt"] += " changed"
        a.ingest(self.db,b)
        with self.assertRaisesRegex(ValueError,"Immutable"): self.run_at()

    def test_run_diff(self):
        old=self.run_at("2025-12-31T00:00:00Z"); new=self.run_at()
        d=a.difference(old,new)
        self.assertEqual([c["id"] for c in d["changes"]["claims"]["added"]],["c2"])
        self.assertEqual(d["changes"]["claims"]["removed"],[])

    def test_net_cash_edge_case(self):
        v=dict(self.b["valuations"][0],future_cash=1e12)
        self.assertIsNone(a.reverse_valuation(v)["implied_terminal_revenue"])

    def test_no_unsupported_rank_or_target(self):
        r=self.run_at()
        self.assertNotIn("rank",r)
        self.assertIn("Scenario inversion, not a forecast",a.report(r))

    def test_security_conflict_rejected(self):
        b=copy.deepcopy(self.b); b["security"]["currency"]="EUR"
        a.ingest(self.db,b)
        with self.assertRaisesRegex(ValueError,"identity"): self.run_at()

    def test_real_primary_source_example_preserves_ranges(self):
        b=json.loads((FIXTURE.parent/"coherent_primary_sources.json").read_text())
        with a.closing(a.connect(":memory:")) as db:
            a.ingest(db,b)
            early=a.build_run(db,b["security"]["id"],"2026-09-01T00:00:00Z")
            self.assertEqual(len(early["expectations"]),2)
            self.assertEqual(early["claims"],[])
            late=a.build_run(db,b["security"]["id"],"2026-11-16T02:05:00Z")
            by_metric={r["metric"]:r for r in late["expectation_comparisons"]}
            self.assertEqual(by_metric["revenue"]["range_outcome"],"within range")
            self.assertEqual(by_metric["diluted EPS"]["range_outcome"],"above range")
            self.assertIsNone(late["valuation"])

    def test_invalid_range_rejected(self):
        self.b["expectations"][0].update(low=200000000,high=300000000)
        with self.assertRaises(ValueError): a.validate(self.b)

    def test_wrong_collection_type_rejected(self):
        self.b["claims"]={}
        with self.assertRaises(ValueError): a.validate(self.b)

    def test_wrong_root_type_rejected(self):
        with self.assertRaises(ValueError): a.validate([])

    def test_cli_works(self):
        with tempfile.TemporaryDirectory() as d:
            db=str(Path(d)/"demo.db")
            self.assertEqual(a.main(["--db",db,"ingest",str(FIXTURE)]),0)
            self.assertEqual(a.main(["--db",db,"run",self.b["security"]["id"],"--as-of","2025-12-31T00:00:00Z"]),0)

if __name__ == "__main__":
    unittest.main()
