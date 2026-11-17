import json
from pathlib import Path
import tempfile
import unittest
import autonext
from backtest_audit import audit

class ReplayTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/'ledger.sqlite'
        db=autonext.connect(self.path)
        bundle=json.loads((Path(__file__).resolve().parents[1]/'examples/coherent_primary_sources.json').read_text())
        autonext.ingest(db,bundle)
        db.close()
    def test_published_then_actual_without_capture_leak(self):
        before=self.path.read_bytes()
        r=audit(self.path,['2026-09-01T00:00:00Z','2026-11-05T23:59:59Z'])
        published=[x for x in r['snapshots'] if x['mode']=='published']
        self.assertEqual([x['expectation_count'] for x in published],[2,4])
        self.assertEqual([x['comparison_count'] for x in published],[0,2])
        self.assertTrue(all(x['expectation_count']==0 for x in r['snapshots'] if x['mode']=='captured'))
        self.assertIsNone(r['portfolio_return'])
        self.assertEqual(before,self.path.read_bytes())
    def test_capture_boundary(self):
        r=audit(self.path,['2026-11-16T02:04:32Z','2026-11-16T02:04:33Z'])
        self.assertEqual([x['expectation_count'] for x in r['snapshots'] if x['mode']=='captured'],[0,4])
    def test_empty_dates_rejected(self):
        with self.assertRaises(ValueError): audit(self.path,[])
    def test_naive_dates_rejected(self):
        with self.assertRaises(ValueError): audit(self.path,['2026-09-01'])
