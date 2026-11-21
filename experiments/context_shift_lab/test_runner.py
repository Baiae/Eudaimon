"""Behavioral checks for the public paired-case instrument."""

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("context_shift_runner", HERE / "runner.py")
lab = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lab)


class ContextShiftTests(unittest.TestCase):
    def setUp(self):
        self.suite = lab.load_suite(HERE / "demo_suite.json")
        self.illustrative = json.loads((HERE / "illustrative_predictions.json").read_text())

    def test_switch_requires_both_contexts_and_baseline_is_deterministic(self):
        result = lab.score(self.suite, self.illustrative)
        self.assertEqual(result["pairs_total"], 8)
        self.assertEqual(result["pairs_correct"], 6)
        baseline = lab.lexical_baseline(self.suite)
        self.assertEqual(baseline, lab.lexical_baseline(self.suite))
        self.assertEqual(lab.score(self.suite, baseline)["pairs_correct"], 2)
        failed = [pair for pair in result["pairs"] if not pair["switch_success"]]
        self.assertEqual({p["pair_id"] for p in failed}, {"replication-safety", "sample-integrity"})

    def test_rejects_missing_and_duplicate_rankings(self):
        partial = {**self.illustrative, "predictions": self.illustrative["predictions"][:-1]}
        with self.assertRaisesRegex(ValueError, "missing="):
            lab.score(self.suite, partial)
        duplicate = {**self.illustrative, "predictions": self.illustrative["predictions"] + self.illustrative["predictions"][:1]}
        with self.assertRaisesRegex(ValueError, "duplicate prediction"):
            lab.score(self.suite, duplicate)
        invalid = json.loads(json.dumps(self.illustrative))
        invalid["predictions"][0]["ranked_ids"] = ["b", "b", "c"]
        with self.assertRaisesRegex(ValueError, "exact permutation"):
            lab.score(self.suite, invalid)

    def test_report_is_standalone_and_embedded_data_cannot_close_script_tag(self):
        malicious = {**self.illustrative, "model_name": "</script><script>alert('x')</script>"}
        report = lab.build_report(HERE / "demo_suite.json", malicious)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "report.html"
            lab.write_html(report, path)
            html = path.read_text()
        self.assertNotIn("</script><script>alert", html)
        self.assertIn("\\u003c/script\\u003e", html)
        self.assertIn(report["suite_sha256"], html)
        self.assertIn("PUBLIC DEMO · PROVISIONAL LABELS", html)


if __name__ == "__main__":
    unittest.main()
