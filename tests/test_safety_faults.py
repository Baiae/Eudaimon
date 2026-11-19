"""Failure-injection and explicit evaluator-trust regressions; temp fixtures only."""
from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from engine.engine import (
    CampaignEngine, EngineConfig, EngineError, EvaluationError,
    TRUSTED_REFERENCE_EVALUATOR_SHA256,
)


EVALUATOR = """
import json
import sys
from pathlib import Path
source = Path(sys.argv[sys.argv.index('--candidate') + 1]).read_text()
print(json.dumps({'protect_pass': True, 'score': .9 if source == 'BETTER' else .1}))
"""


class SafetyFaultTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="eudaimon-fault-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "proposals").mkdir()
        (self.root / "program.md").write_text("BASELINE")
        (self.root / "eval_runner.py").write_text(EVALUATOR)

    def _engine(self):
        trusted = hashlib.sha256((self.root / "eval_runner.py").read_bytes()).hexdigest()
        return CampaignEngine(EngineConfig(self.root, trusted_evaluator_sha256=trusted))

    def _proposal(self):
        proposal = self.root / "proposals" / "better.md"
        proposal.write_text("BETTER")
        return proposal

    def _events(self, engine):
        return [json.loads(line) for line in engine.ledger.read_text().splitlines()]

    def _intent(self, engine):
        engine._append_ledger({
            "event": "promotion_intent", "transaction_id": "tx-1",
            "run_id": "run-1", "timestamp": "test",
            "target": engine.config.target,
            "old_target_sha256": hashlib.sha256(b"BASELINE").hexdigest(),
            "candidate_sha256": hashlib.sha256(b"BETTER").hexdigest(),
        })

    def test_default_does_not_trust_arbitrary_evaluator_or_write_state(self):
        engine = CampaignEngine(EngineConfig(self.root))
        with self.assertRaisesRegex(EngineError, "untrusted evaluator"):
            engine.run()
        self.assertEqual(engine.target.read_text(), "BASELINE")
        self.assertFalse(engine.state_dir.exists())

    def test_modified_evaluator_refused_immediately_before_execution(self):
        engine = self._engine()
        engine._validate_campaign()
        (self.root / "eval_runner.py").write_text("raise RuntimeError('UNTRUSTED')")
        candidate = self._proposal()
        with self.assertRaisesRegex(EngineError, "untrusted evaluator"):
            engine._evaluate(candidate)
        self.assertFalse(engine.state_dir.exists())
        self.assertEqual(engine.target.read_text(), "BASELINE")

    def test_bundled_reference_evaluator_pin_matches_reviewed_file(self):
        bundled = Path(__file__).resolve().parent.parent / "campaigns/rr_engine/eval_runner.py"
        self.assertEqual(hashlib.sha256(bundled.read_bytes()).hexdigest(),
                         TRUSTED_REFERENCE_EVALUATOR_SHA256)

    def test_bad_evaluator_pin_is_rejected(self):
        engine = CampaignEngine(EngineConfig(self.root, trusted_evaluator_sha256="invalid"))
        with self.assertRaisesRegex(EngineError, "invalid trusted evaluator"):
            engine._validate_campaign()

    def test_intent_append_failure_refuses_promotion_and_releases_lock(self):
        self._proposal()
        engine = self._engine()
        original = engine._append_ledger

        def fail_intent(event):
            if event["event"] == "promotion_intent":
                raise OSError("injected intent append error")
            original(event)

        with patch.object(engine, "_append_ledger", side_effect=fail_intent):
            with self.assertRaisesRegex(OSError, "intent append"):
                engine.run()
        self.assertEqual(engine.target.read_text(), "BASELINE")
        self.assertFalse((engine.state_dir / "run.lock").exists())
        self.assertFalse(any(e["event"] == "promotion_commit" for e in self._events(engine)))

    def test_partial_intent_line_requires_operator_review(self):
        self._proposal()
        engine = self._engine()
        original = engine._append_ledger

        def partial_intent(event):
            if event["event"] == "promotion_intent":
                with engine.ledger.open("ab") as handle:
                    handle.write(b'{"event":"promotion_intent"')
                    handle.flush()
                raise OSError("injected torn intent write")
            original(event)

        with patch.object(engine, "_append_ledger", side_effect=partial_intent):
            with self.assertRaisesRegex(OSError, "torn intent"):
                engine.run()
        evidence = engine.ledger.read_bytes()
        with self.assertRaisesRegex(EngineError, "partial|malformed"):
            self._engine().run()
        self.assertEqual(engine.ledger.read_bytes(), evidence)
        self.assertEqual(engine.target.read_text(), "BASELINE")
        self.assertFalse((engine.state_dir / "run.lock").exists())

    def test_commit_append_failure_reconciles_promoted_target_on_restart(self):
        self._proposal()
        engine = self._engine()
        original = engine._append_ledger

        def fail_commit(event):
            if event["event"] == "promotion_commit":
                raise OSError("injected commit append error")
            original(event)

        with patch.object(engine, "_append_ledger", side_effect=fail_commit):
            with self.assertRaisesRegex(OSError, "commit append"):
                engine.run()
        self.assertEqual(engine.target.read_text(), "BETTER")
        self.assertFalse((engine.state_dir / "run.lock").exists())
        self.assertEqual(len(engine._pending_promotion_transactions()), 1)
        engine._recover_incomplete_promotions()
        self.assertEqual(engine._pending_promotion_transactions(), {})
        self.assertEqual(self._events(engine)[-1]["event"], "promotion_recovered_commit")

    def test_failure_after_replace_before_commit_reconciles_from_intent(self):
        self._proposal()
        engine = self._engine()
        promote = engine._promote

        def fail_after_replace(*args):
            promote(*args)
            raise OSError("injected failure after atomic replace")

        with patch.object(engine, "_promote", side_effect=fail_after_replace):
            with self.assertRaisesRegex(OSError, "after atomic replace"):
                engine.run()
        self.assertEqual(engine.target.read_text(), "BETTER")
        self.assertEqual(len(engine._pending_promotion_transactions()), 1)
        engine._recover_incomplete_promotions()
        self.assertEqual(self._events(engine)[-1]["event"], "promotion_recovered_commit")

    def test_failed_recovery_append_preserves_intent_and_target(self):
        engine = self._engine()
        self._intent(engine)
        (self.root / "program.md").write_text("BETTER")
        with patch.object(engine, "_append_ledger", side_effect=OSError("recovery write blocked")):
            with self.assertRaisesRegex(OSError, "recovery write blocked"):
                engine.run()
        self.assertEqual(engine.target.read_text(), "BETTER")
        self.assertEqual(len(engine._pending_promotion_transactions()), 1)
        self.assertFalse((engine.state_dir / "run.lock").exists())
        engine._recover_incomplete_promotions()
        self.assertEqual(engine._pending_promotion_transactions(), {})

    def test_state_failure_after_baseline_does_not_fabricate_promotion(self):
        engine = self._engine()
        self._proposal()
        original = engine._write_state
        calls = 0

        def fail_second(state):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError("injected baseline state failure")
            original(state)

        with patch.object(engine, "_write_state", side_effect=fail_second):
            with self.assertRaisesRegex(OSError, "baseline state"):
                engine.run()
        self.assertEqual(engine.target.read_text(), "BASELINE")
        self.assertFalse((engine.state_dir / "run.lock").exists())
        self.assertFalse(any(e["event"] == "promotion_commit" for e in self._events(engine)))

    def test_reused_completed_transaction_id_halts_recovery(self):
        engine = self._engine()
        self._intent(engine)
        engine._append_ledger({
            "event": "promotion_commit", "transaction_id": "tx-1", "run_id": "run-1",
            "target_sha256": hashlib.sha256(b"BETTER").hexdigest(), "timestamp": "test"
        })
        self._intent(engine)  # replay after an apparently successful outcome
        before = engine.ledger.read_bytes()
        with self.assertRaisesRegex(EngineError, "reused|duplicate|invalid"):
            engine.run()
        self.assertEqual(engine.target.read_text(), "BASELINE")
        self.assertEqual(engine.ledger.read_bytes(), before)
        self.assertFalse((engine.state_dir / "run.lock").exists())

    def test_commit_digest_mismatch_halts_recovery(self):
        engine = self._engine()
        self._intent(engine)
        engine._append_ledger({
            "event": "promotion_commit", "transaction_id": "tx-1", "run_id": "run-1",
            "target_sha256": "c" * 64, "timestamp": "test"
        })
        before = engine.ledger.read_bytes()
        with self.assertRaisesRegex(EngineError, "digest|invalid|mismatch"):
            engine.run()
        self.assertEqual(engine.ledger.read_bytes(), before)
        self.assertEqual(engine.target.read_text(), "BASELINE")

    def test_bundled_policy_change_is_refused_even_when_adapter_is_pinned(self):
        from shutil import copyfile
        bundled = Path(__file__).resolve().parent.parent / "campaigns/rr_engine"
        copyfile(bundled / "eval_runner.py", self.root / "eval_runner.py")
        copyfile(bundled / "rr_policy.py", self.root / "rr_policy.py")
        engine = CampaignEngine(EngineConfig(self.root))
        engine._validate_campaign()  # trusted reference bytes and policy
        (self.root / "rr_policy.py").write_text("print('unreviewed behavior')")
        with self.assertRaisesRegex(EngineError, "untrusted evaluator policy"):
            engine._validate_campaign()
        self.assertFalse(engine.state_dir.exists())

    def test_valid_json_without_newline_blocks_restart(self):
        engine = self._engine()
        engine.state_dir.mkdir()
        raw = b'{"event":"halt","run_id":"run-1","timestamp":"test","reason":"test","state":{}}'
        engine.ledger.write_bytes(raw)
        with self.assertRaisesRegex(EngineError, "partial ledger"):
            engine.run()
        self.assertEqual(engine.ledger.read_bytes(), raw)
        self.assertEqual(engine.target.read_text(), "BASELINE")
        self.assertFalse((engine.state_dir / "run.lock").exists())

    def test_duplicate_json_keys_block_recovery(self):
        engine = self._engine()
        engine.state_dir.mkdir()
        raw = b'{"event":"halt","event":"baseline","run_id":"run-1","timestamp":"test"}\n'
        engine.ledger.write_bytes(raw)
        with self.assertRaisesRegex(EngineError, "malformed ledger"):
            engine.run()
        self.assertEqual(engine.ledger.read_bytes(), raw)
        self.assertEqual(engine.target.read_text(), "BASELINE")
        self.assertFalse((engine.state_dir / "run.lock").exists())

    def test_partial_commit_line_preserves_promoted_target_but_blocks_recovery(self):
        self._proposal()
        engine = self._engine()
        original = engine._append_ledger

        def torn_commit(event):
            if event["event"] == "promotion_commit":
                with engine.ledger.open("ab") as handle:
                    handle.write(b'{"event":"promotion_commit"')
                    handle.flush()
                raise OSError("torn commit record")
            original(event)

        with patch.object(engine, "_append_ledger", side_effect=torn_commit):
            with self.assertRaisesRegex(OSError, "torn commit"):
                engine.run()
        self.assertEqual(engine.target.read_text(), "BETTER")
        before = engine.ledger.read_bytes()
        with self.assertRaisesRegex(EngineError, "partial ledger|malformed"):
            self._engine().run()
        self.assertEqual(engine.ledger.read_bytes(), before)
        self.assertEqual(engine.target.read_text(), "BETTER")
        self.assertFalse((engine.state_dir / "run.lock").exists())

    def test_atomic_state_replace_failure_retains_previous_state(self):
        engine = self._engine()
        engine.state_dir.mkdir()
        engine.state_path.write_text('{"status":"previous"}\n')
        before = engine.state_path.read_bytes()
        with patch("engine.engine.os.replace", side_effect=OSError("state replace failed")):
            with self.assertRaisesRegex(OSError, "replace failed"):
                engine._write_state({"status": "new"})
        self.assertEqual(engine.state_path.read_bytes(), before)
        self.assertEqual(list(engine.state_dir.glob(".state.*")), [])

    def test_atomic_target_replace_failure_reconciles_to_abort(self):
        import os
        self._proposal()
        engine = self._engine()
        original_replace = os.replace

        def fail_target_replace(source, destination):
            if Path(destination) == engine.target:
                raise OSError("injected target replace failure")
            return original_replace(source, destination)

        with patch("engine.engine.os.replace", side_effect=fail_target_replace):
            with self.assertRaisesRegex(OSError, "target replace failure"):
                engine.run()
        self.assertEqual(engine.target.read_text(), "BASELINE")
        self.assertFalse((engine.state_dir / "run.lock").exists())
        self.assertEqual(len(engine._pending_promotion_transactions()), 1)
        engine._recover_incomplete_promotions()
        self.assertEqual(self._events(engine)[-1]["event"], "promotion_recovered_abort")

    def test_state_failure_after_rejected_candidate_does_not_promote(self):
        (self.root / "proposals" / "same.md").write_text("BASELINE")
        engine = self._engine()
        original = engine._write_state
        calls = 0

        def fail_third(state):
            nonlocal calls
            calls += 1
            if calls == 3:
                raise OSError("injected candidate state failure")
            original(state)

        with patch.object(engine, "_write_state", side_effect=fail_third):
            with self.assertRaisesRegex(OSError, "candidate state failure"):
                engine.run()
        self.assertEqual(engine.target.read_text(), "BASELINE")
        self.assertFalse((engine.state_dir / "run.lock").exists())
        events = self._events(engine)
        self.assertEqual(len([e for e in events if e["event"] == "candidate"]), 1)
        self.assertFalse(any(e["event"].startswith("promotion_") for e in events))

    def test_failed_recovery_abort_append_preserves_old_target(self):
        engine = self._engine()
        self._intent(engine)
        before = engine.ledger.read_bytes()
        with patch.object(engine, "_append_ledger", side_effect=OSError("injected abort write failure")):
            with self.assertRaisesRegex(OSError, "abort write failure"):
                engine.run()
        self.assertEqual(engine.target.read_text(), "BASELINE")
        self.assertEqual(engine.ledger.read_bytes(), before)
        self.assertFalse((engine.state_dir / "run.lock").exists())
        engine._recover_incomplete_promotions()
        self.assertEqual(self._events(engine)[-1]["event"], "promotion_recovered_abort")

    def test_structural_auditor_accepts_complete_temp_promotion(self):
        from tools.audit_ledger import audit_ledger
        self._proposal()
        engine = self._engine()
        result = engine.run()
        self.assertEqual(result.exit_code, 0)
        report = audit_ledger(engine.ledger)
        self.assertEqual(report["issues"], [])
        self.assertEqual(report["pending_transactions"], [])
        self.assertTrue(any(event["event"] == "promotion_commit"
                            for event in self._events(engine)))
