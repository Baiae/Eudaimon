"""Merge-gate regressions for evaluator trust, promotion, and durable evidence."""
from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from engine.engine import (
    CampaignEngine, EngineConfig, EngineError, EvaluationError,
    validate_evaluation,
)
from tools.audit_ledger import audit_ledger
def approved_config(root: Path, **options) -> EngineConfig:
    return EngineConfig(
        root,
        trusted_evaluator_sha256=hashlib.sha256((root / "eval_runner.py").read_bytes()).hexdigest(),
        **options,
    )


EVALUATOR = """
import json
import sys
from pathlib import Path
text = Path(sys.argv[sys.argv.index('--candidate') + 1]).read_text()
print(json.dumps({'protect_pass': True, 'score': .9 if text == 'BETTER' else .1}))
"""


class MergeSafetyTests(unittest.TestCase):
    def _engine(self, evaluator: str = EVALUATOR) -> tuple[CampaignEngine, Path]:
        root = Path(tempfile.mkdtemp(prefix="eudaimon-merge-gate-"))
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        (root / "program.md").write_text("BASELINE")
        (root / "eval_runner.py").write_text(evaluator)
        (root / "proposals").mkdir()
        return CampaignEngine(approved_config(root)), root

    def _events(self, engine: CampaignEngine) -> list[dict]:
        return [json.loads(line) for line in engine.ledger.read_text().splitlines()]

    def test_safe_candidate_still_promotes_and_intent_binds_target(self):
        engine, root = self._engine()
        (root / "proposals" / "better.md").write_text("BETTER")
        result = engine.run()
        self.assertEqual((result.exit_code, result.reason), (0, "proposal_exhausted"))
        self.assertEqual(engine.target.read_text(), "BETTER")
        intent = next(e for e in self._events(engine) if e["event"] == "promotion_intent")
        self.assertEqual(intent["target"], "program.md")
        self.assertEqual(intent["old_target_sha256"], hashlib.sha256(b"BASELINE").hexdigest())

    def test_untrusted_baseline_error_records_terminal_halt(self):
        engine, _ = self._engine()
        with patch.object(engine, "_evaluate", side_effect=EngineError("trust check failed")):
            result = engine.run()
        self.assertEqual((result.exit_code, result.reason), (2, "baseline_evaluation_error"))
        self.assertEqual(json.loads(engine.state_path.read_text())["status"], "halted")
        self.assertEqual([e["event"] for e in self._events(engine)][-2:], ["evaluation_error", "halt"])

    def test_untrusted_candidate_error_records_terminal_halt(self):
        engine, root = self._engine()
        (root / "proposals" / "candidate.md").write_text("BETTER")
        baseline = {"protect_pass": True, "score": 0.1,
                    "candidate_sha256": hashlib.sha256(b"BASELINE").hexdigest()}
        with patch.object(engine, "_evaluate", side_effect=[baseline, EngineError("trust check failed")]):
            result = engine.run()
        self.assertEqual((result.exit_code, result.reason), (2, "candidate_evaluation_error"))
        self.assertEqual(json.loads(engine.state_path.read_text())["status"], "halted")
        self.assertEqual([e["event"] for e in self._events(engine)][-2:], ["evaluation_error", "halt"])
        self.assertEqual(engine.target.read_text(), "BASELINE")

    def test_nested_nonfinite_diagnostics_rejected(self):
        for bad in (float("nan"), float("inf"), float("-inf")):
            with self.subTest(bad=repr(bad)):
                with self.assertRaisesRegex(EvaluationError, "non-finite"):
                    validate_evaluation({
                        "protect_pass": True, "score": 0.8,
                        "components": {"nested": [{"diagnostic": bad}]},
                    })

    def test_nonfinite_evaluator_result_never_enters_ledger(self):
        engine, _ = self._engine('print(\'{"protect_pass":true,"score":1,"components":{"x":NaN}}\')')
        result = engine.run()
        self.assertEqual(result.reason, "baseline_evaluation_error")
        self.assertNotIn("NaN", engine.ledger.read_text())
        self.assertEqual(self._events(engine)[-1]["event"], "halt")

    def test_pending_transaction_cannot_recover_different_target(self):
        engine, root = self._engine()
        (root / "other.md").write_text("BASELINE")
        engine._append_ledger({
            "event": "promotion_intent", "run_id": "old-run", "timestamp": "test",
            "transaction_id": "tx-1", "target": "program.md",
            "old_target_sha256": hashlib.sha256(b"BASELINE").hexdigest(),
            "candidate_sha256": hashlib.sha256(b"BETTER").hexdigest(),
        })
        other = CampaignEngine(approved_config(root, target="other.md"))
        before = engine.ledger.read_bytes()
        with self.assertRaisesRegex(EngineError, "target identity"):
            other._recover_incomplete_promotions()
        self.assertEqual(engine.ledger.read_bytes(), before)
        self.assertEqual((root / "other.md").read_text(), "BASELINE")
        self.assertEqual((root / "program.md").read_text(), "BASELINE")

    def test_targetless_legacy_pending_intent_requires_operator_review(self):
        engine, _ = self._engine()
        engine._append_ledger({
            "event": "promotion_intent", "run_id": "old-run", "timestamp": "test",
            "transaction_id": "tx-legacy",
            "old_target_sha256": hashlib.sha256(b"BASELINE").hexdigest(),
            "candidate_sha256": hashlib.sha256(b"BETTER").hexdigest(),
        })
        with self.assertRaisesRegex(EngineError, "target identity"):
            engine._recover_incomplete_promotions()

    def test_incumbent_modified_after_evaluation_cannot_be_replaced(self):
        engine, root = self._engine()
        (root / "proposals" / "better.md").write_text("BETTER")
        baseline = {"protect_pass": True, "score": .1,
                    "candidate_sha256": hashlib.sha256(b"BASELINE").hexdigest()}
        candidate = {"protect_pass": True, "score": .9,
                     "candidate_sha256": hashlib.sha256(b"BETTER").hexdigest()}
        def evaluate(path):
            if path == engine.target:
                return baseline
            engine.target.write_text("EXTERNAL CHANGE")
            return candidate
        with patch.object(engine, "_evaluate", side_effect=evaluate):
            result = engine.run()
        self.assertEqual((result.exit_code, result.reason), (2, "incumbent_changed_since_evaluation"))
        self.assertEqual(engine.target.read_text(), "EXTERNAL CHANGE")
        self.assertFalse(any(e["event"] == "promotion_intent" for e in self._events(engine)))

    def test_new_ledger_and_state_directory_are_synced(self):
        engine, _ = self._engine()
        original = engine._fsync_directory
        calls = []
        def record(directory, *, required=False):
            calls.append((directory, required))
            return original(directory, required=required)
        with patch.object(engine, "_fsync_directory", side_effect=record):
            engine.run()
        self.assertIn((engine.campaign, True), calls)
        self.assertIn((engine.state_dir, True), calls)

    def test_ledger_directory_sync_failure_prevents_promotion(self):
        engine, root = self._engine()
        (root / "proposals" / "better.md").write_text("BETTER")
        original = engine._fsync_directory
        def reject_first_ledger_creation(directory, *, required=False):
            if directory == engine.state_dir and required and engine.ledger.exists():
                raise EngineError("cannot durably synchronize ledger directory")
            return original(directory, required=required)
        with patch.object(engine, "_fsync_directory", side_effect=reject_first_ledger_creation):
            with self.assertRaisesRegex(EngineError, "durably synchronize"):
                engine.run()
        self.assertEqual(engine.target.read_text(), "BASELINE")
        self.assertFalse((engine.state_dir / "run.lock").exists())

    def test_reference_evaluator_ignores_shadowing_policy_package(self):
        bundled = Path(__file__).resolve().parent.parent / "campaigns" / "rr_engine"
        root = Path(tempfile.mkdtemp(prefix="eudaimon-policy-shadow-"))
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        shutil.copy2(bundled / "eval_runner.py", root / "eval_runner.py")
        shutil.copy2(bundled / "rr_policy.py", root / "rr_policy.py")
        shutil.copy2(bundled / "program.md", root / "program.md")
        (root / "proposals").mkdir()
        (root / "rr_policy").mkdir()
        (root / "rr_policy" / "__init__.py").write_text(
            "from pathlib import Path\nPath(__file__).parent.parent.joinpath('PWNED').write_text('executed')\n"
        )
        engine = CampaignEngine(EngineConfig(root))
        result = engine._evaluate(engine.target)
        self.assertTrue(result["protect_pass"])
        self.assertFalse((root / "PWNED").exists())

    def test_auditor_does_not_accept_aborted_promotion_as_success(self):
        engine, root = self._engine()
        old = hashlib.sha256(b"BASELINE").hexdigest()
        new = hashlib.sha256(b"BETTER").hexdigest()
        events = [
            {"event": "promotion_intent", "run_id": "r", "timestamp": "t",
             "transaction_id": "tx", "target": "program.md",
             "old_target_sha256": old, "candidate_sha256": new},
            {"event": "promotion_recovered_abort", "run_id": "r", "timestamp": "t",
             "transaction_id": "tx", "recovered_target_sha256": old},
            {"event": "candidate", "run_id": "r", "timestamp": "t",
             "candidate": "better.md", "iteration": 1, "decision": "promoted",
             "transaction_id": "tx", "evaluation": {
                 "protect_pass": True, "score": 0.9, "candidate_sha256": new}},
        ]
        ledger = root / "sample.jsonl"
        ledger.write_text("".join(json.dumps(event) + "\n" for event in events))
        report = audit_ledger(ledger)
        self.assertTrue(any("without successful" in issue for issue in report["issues"]))
        self.assertEqual(report["pending_transactions"], [])


if __name__ == "__main__":
    unittest.main()

