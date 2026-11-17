import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

import research_cli as cli


class ResearchCliTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.desk = Path(self.temp.name) / "desk-20260101T000000"
        company = self.desk / "TEST"
        company.mkdir(parents=True)
        manifest = {"created_at": "2026-01-01T00:00:00Z", "companies": [{"symbol": "TEST", "status": "ok", "sources": 1}]}
        run = {
            "security": {"id": "NASDAQ:TEST:COMMON", "company": "Test Photonics", "ticker": "TEST", "exchange": "NASDAQ", "currency": "USD", "sector": "photonics"},
            "as_of": "2026-01-01T00:00:00Z",
            "run_id": "run-1",
            "sources": [{"id": "s1", "title": "Test release", "excerpt": "Customer qualification reached volume production", "locator": "https://example.test", "published_at": "2025-12-31T00:00:00Z"}],
            "expectations": [{"id": "test-release-1", "kind": "observed_result", "metric": "revenue", "basis": "GAAP", "period": "Q4", "value": 1000000, "unit": "USD"}],
            "expectation_comparisons": [],
            "earnings_analysis": [{
                "input": {
                    "price_observation": {"price": 100, "currency": "USD", "observed_at": "2025-12-31T21:00:00Z"},
                    "scenario": {"years": 5, "required_return": 0.10, "terminal_pe": 25, "future_share_factor": 1},
                },
                "result": {"status": "scenario_not_forecast", "required_terminal_eps": 6.44204, "required_total_earnings_per_current_share": 6.44204},
            }],
        }
        (self.desk / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        (company / "run.json").write_text(json.dumps(run), encoding="utf-8")
        (company / "changes.json").write_text(json.dumps({"sequential_changes": []}), encoding="utf-8")
        (company / "report.md").write_text("# Test report\n", encoding="utf-8")

    def tearDown(self):
        self.temp.cleanup()

    def test_scenario_math(self):
        result = cli.scenario(100, 5, 0.10, 25, 1.2)
        self.assertAlmostEqual(result["required_terminal_price"], 161.051)
        self.assertAlmostEqual(result["required_terminal_eps"], 6.44204)
        self.assertAlmostEqual(result["required_total_earnings_per_current_share"], 7.730448)
        self.assertEqual(result["status"], "scenario_not_forecast")

    def test_latest_desk_and_company_load(self):
        found = cli.find_latest_desk(Path(self.temp.name))
        desk = cli.Desk(found)
        self.assertEqual(desk.company("test")["run"]["security"]["company"], "Test Photonics")

    def test_search_retained_evidence(self):
        desk = cli.Desk(self.desk)
        output = io.StringIO()
        with redirect_stdout(output):
            cli.search(desk, ["qualification", "volume"])
        self.assertIn("Test release", output.getvalue())

    def test_search_any_term(self):
        desk = cli.Desk(self.desk)
        output = io.StringIO()
        with redirect_stdout(output):
            cli.search(desk, ["qualification", "missing"], match="any")
        self.assertIn("Test release", output.getvalue())

    def test_doctor_validates_complete_fixture(self):
        result = cli.doctor(cli.Desk(self.desk), emit=False)
        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["failures"], 0)

    def test_terminal_commands(self):
        for arguments in (
            ["--desk", str(self.desk), "universe"],
            ["--desk", str(self.desk), "company", "TEST"],
            ["--desk", str(self.desk), "compare"],
            ["--desk", str(self.desk), "scenario", "TEST", "--terminal-pe", "20"],
            ["--desk", str(self.desk), "search", "customer"],
        ):
            with redirect_stdout(io.StringIO()):
                self.assertEqual(cli.main(arguments), 0)

    def test_obsidian_export_preserves_human_thesis(self):
        desk = cli.Desk(self.desk)
        vault = Path(self.temp.name) / "vault" / "AutoNext"
        with redirect_stdout(io.StringIO()):
            cli.export_obsidian(desk, vault)
        thesis = vault / "Theses" / "TEST Thesis.md"
        thesis.write_text("my independent thesis", encoding="utf-8")
        with redirect_stdout(io.StringIO()):
            cli.export_obsidian(desk, vault)
        self.assertEqual(thesis.read_text(encoding="utf-8"), "my independent thesis")
        self.assertTrue((vault / "Companies" / "TEST.md").exists())
        self.assertEqual(len(list((vault / "Snapshots").rglob("*.md"))), 1)

    def test_generated_export_refuses_user_owned_company_note(self):
        desk = cli.Desk(self.desk)
        vault = Path(self.temp.name) / "vault" / "AutoNext"
        company = vault / "Companies" / "TEST.md"
        company.parent.mkdir(parents=True)
        company.write_text("user note", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Refusing to overwrite"):
            cli.export_obsidian(desk, vault)

    def test_full_offline_workflow(self):
        output = Path(self.temp.name) / "workflow-desk"
        vault = Path(self.temp.name) / "workflow-vault"
        with redirect_stdout(io.StringIO()):
            result = cli.run_workflow(vault, output=output, offline=True)
        self.assertEqual(result["doctor"]["failures"], 0)
        self.assertEqual(len(result["manifest"]["companies"]), 5)
        self.assertTrue((vault / "AutoNext Research.md").is_file())

    def test_sec_refresh_requires_identity(self):
        with self.assertRaisesRegex(ValueError, "sec-user-agent"):
            cli.run_workflow(Path(self.temp.name) / "vault", output=Path(self.temp.name) / "desk", offline=True, refresh_sec=True)

    def test_unknown_company_fails_cleanly(self):
        with redirect_stdout(io.StringIO()):
            self.assertEqual(cli.main(["--desk", str(self.desk), "company", "NOPE"]), 2)


if __name__ == "__main__":
    unittest.main()
