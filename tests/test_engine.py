from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

from unittest.mock import patch

from engine.engine import CampaignEngine, EngineConfig, EngineError, EvaluationError, RunLock, lexicographically_better


def approved_config(root: Path, **options) -> EngineConfig:
    """Only ephemeral test fixtures get explicit programmatic evaluator approval."""
    digest = hashlib.sha256((root / "eval_runner.py").read_bytes()).hexdigest()
    return EngineConfig(root, trusted_evaluator_sha256=digest, **options)


class EngineContractTests(unittest.TestCase):
    def test_huge_integer_score_fails_closed_as_evaluation_error(self) -> None:
        from engine.engine import validate_evaluation
        with self.assertRaisesRegex(EvaluationError, "finite scalar score"):
            validate_evaluation({"protect_pass": True, "score": 10 ** 1000})

    def test_boolean_score_is_not_accepted_as_numeric(self) -> None:
        from engine.engine import validate_evaluation
        with self.assertRaisesRegex(EvaluationError, "finite scalar score"):
            validate_evaluation({"protect_pass": True, "score": True})

    def test_protect_gate_precedes_score(self) -> None:
        self.assertFalse(
            lexicographically_better(
                {"protect_pass": False, "score": 100},
                {"protect_pass": True, "score": 0.1},
            )
        )
        self.assertTrue(
            lexicographically_better(
                {"protect_pass": True, "score": 0.2},
                {"protect_pass": False, "score": 100},
            )
        )
        self.assertFalse(
            lexicographically_better(
                {"protect_pass": True, "score": 0.2},
                {"protect_pass": True, "score": 0.2},
            )
        )

    def _campaign(self, evaluator_source: str, baseline: str = "BASELINE") -> Path:
        root = Path(tempfile.mkdtemp(prefix="eudaimon-test-"))
        (root / "proposals").mkdir()
        (root / "program.md").write_text(baseline, encoding="utf-8")
        (root / "eval_runner.py").write_text(evaluator_source, encoding="utf-8")
        return root

    def test_promotes_only_strict_protected_improvement(self) -> None:
        evaluator = """
import json
import sys
from pathlib import Path
candidate = Path(sys.argv[sys.argv.index('--candidate') + 1]).read_text()
if candidate == 'BASELINE':
    score, protect = 0.2, True
elif candidate == 'UNSAFE_HIGH_SCORE':
    score, protect = 100.0, False
else:
    score, protect = 0.8, True
print(json.dumps({'protect_pass': protect, 'score': score, 'components': {}}))
"""
        root = self._campaign(evaluator)
        (root / "proposals" / "a-unsafe.md").write_text("UNSAFE_HIGH_SCORE", encoding="utf-8")
        (root / "proposals" / "b-good.md").write_text("GOOD", encoding="utf-8")

        result = CampaignEngine(approved_config(root, max_no_improvement=5)).run()

        self.assertEqual(result.exit_code, 0)
        self.assertEqual(result.reason, "proposal_exhausted")
        self.assertEqual((root / "program.md").read_text(encoding="utf-8"), "GOOD")
        events = [json.loads(line) for line in (root / ".autoresearch" / "ledger.jsonl").read_text().splitlines()]
        decisions = [event["decision"] for event in events if event["event"] == "candidate"]
        self.assertEqual(decisions, ["rejected", "promoted"])
        intents = [event for event in events if event["event"] == "promotion_intent"]
        commits = [event for event in events if event["event"] == "promotion_commit"]
        self.assertEqual(len(intents), 1)
        self.assertEqual(len(commits), 1)
        self.assertEqual(intents[0]["transaction_id"], commits[0]["transaction_id"])
        self.assertEqual(commits[0]["target_sha256"], hashlib.sha256(b"GOOD").hexdigest())
        self.assertFalse((root / ".autoresearch" / "run.lock").exists())

    def test_evaluator_error_halts_without_promotion(self) -> None:
        evaluator = """
import sys
from pathlib import Path
candidate = Path(sys.argv[sys.argv.index('--candidate') + 1]).read_text()
if candidate == 'BAD':
    raise SystemExit(7)
print('{\"protect_pass\": true, \"score\": 0.1}')
"""
        root = self._campaign(evaluator)
        (root / "proposals" / "bad.md").write_text("BAD", encoding="utf-8")

        result = CampaignEngine(approved_config(root)).run()

        self.assertEqual(result.exit_code, 2)
        self.assertEqual(result.reason, "candidate_evaluation_error")
        self.assertEqual((root / "program.md").read_text(encoding="utf-8"), "BASELINE")
        state = json.loads((root / ".autoresearch" / "state.json").read_text(encoding="utf-8"))
        self.assertEqual(state["halt_reason"], "candidate_evaluation_error")
        self.assertFalse((root / ".autoresearch" / "run.lock").exists())



class RunLockTests(unittest.TestCase):
    def test_existing_lock_refuses_second_acquisition_without_replacement(self) -> None:
        with tempfile.TemporaryDirectory(prefix="eudaimon-lock-") as directory:
            path = Path(directory) / "run.lock"
            first = RunLock(path, "owner-a")
            first.acquire()
            original = path.read_bytes()
            original_stat = path.stat()

            with self.assertRaises(EngineError):
                RunLock(path, "owner-b").acquire()

            self.assertEqual(path.read_bytes(), original)
            self.assertEqual(path.stat().st_ino, original_stat.st_ino)
            first.release()
            self.assertFalse(path.exists())

    def test_non_owner_cannot_release_lock(self) -> None:
        with tempfile.TemporaryDirectory(prefix="eudaimon-lock-") as directory:
            path = Path(directory) / "run.lock"
            owner = RunLock(path, "owner-a")
            owner.acquire()

            with self.assertRaisesRegex(EngineError, "another run"):
                RunLock(path, "owner-b").release()

            self.assertEqual(json.loads(path.read_text())["run_id"], "owner-a")
            owner.release()

    def test_owner_can_release_lock(self) -> None:
        with tempfile.TemporaryDirectory(prefix="eudaimon-lock-") as directory:
            path = Path(directory) / "run.lock"
            lock = RunLock(path, "owner-a")
            lock.acquire()
            lock.release()
            self.assertFalse(path.exists())

    def test_failed_lock_initialization_removes_only_its_created_file(self) -> None:
        with tempfile.TemporaryDirectory(prefix="eudaimon-lock-") as directory:
            path = Path(directory) / "run.lock"
            with patch("engine.engine.os.fsync", side_effect=OSError("simulated fsync failure")):
                with self.assertRaises(OSError):
                    RunLock(path, "owner-a").acquire()
            self.assertFalse(path.exists())


    def test_malformed_lock_is_preserved_on_release(self) -> None:
        with tempfile.TemporaryDirectory(prefix="eudaimon-lock-") as directory:
            path = Path(directory) / "run.lock"
            path.write_text("not-json", encoding="utf-8")

            with self.assertRaisesRegex(EngineError, "malformed"):
                RunLock(path, "owner-a").release()

            self.assertEqual(path.read_text(encoding="utf-8"), "not-json")

    def test_release_refuses_lock_with_changed_inode(self) -> None:
        with tempfile.TemporaryDirectory(prefix="eudaimon-lock-") as directory:
            path = Path(directory) / "run.lock"
            lock = RunLock(path, "owner-a")
            lock.acquire()
            replacement = path.with_suffix(".replacement")
            replacement.write_text(json.dumps({"run_id": "owner-a"}))
            replacement.replace(path)

            with self.assertRaisesRegex(EngineError, "inode changed"):
                lock.release()

            self.assertTrue(path.exists())



class PathContainmentTests(unittest.TestCase):
    def _engine(self, root: Path, target: str = "program.md") -> CampaignEngine:
        return CampaignEngine(approved_config(root, target=target))

    def test_accepts_normal_campaign_paths(self) -> None:
        root = EngineContractTests()._campaign(
            "import json\nprint(json.dumps({'protect_pass': True, 'score': 1.0}))"
        )
        engine = self._engine(root)
        engine._validate_campaign()
        self.assertEqual(engine.target, root.resolve() / "program.md")

    def test_rejects_target_symlink_to_outside_campaign(self) -> None:
        root = EngineContractTests()._campaign("print('{}')")
        outside = root.parent / "eudaimon-outside-target.txt"
        outside.write_text("OUTSIDE", encoding="utf-8")
        (root / "program.md").unlink()
        (root / "program.md").symlink_to(outside)

        with self.assertRaisesRegex(EngineError, "target.*symlink"):
            self._engine(root)._validate_campaign()


    def test_rejects_symlink_in_intermediate_target_directory(self) -> None:
        root = EngineContractTests()._campaign("print('{}')")
        outside = root.parent / f"{root.name}-outside-nested"
        outside.mkdir()
        (outside / "program.md").write_text("OUTSIDE", encoding="utf-8")
        (root / "nested").symlink_to(outside, target_is_directory=True)

        with self.assertRaisesRegex(EngineError, "target.*symlink"):
            self._engine(root, "nested/program.md")._validate_campaign()

    def test_rejects_evaluator_symlink_to_outside_campaign(self) -> None:
        root = EngineContractTests()._campaign("print('{}')")
        outside = root.parent / "eudaimon-outside-evaluator.py"
        outside.write_text("print('{}')", encoding="utf-8")
        (root / "eval_runner.py").unlink()
        (root / "eval_runner.py").symlink_to(outside)

        with self.assertRaisesRegex(EngineError, "evaluator.*symlink"):
            self._engine(root)._validate_campaign()

    def test_rejects_symlinked_proposals_directory(self) -> None:
        root = EngineContractTests()._campaign("print('{}')")
        outside = root.parent / f"{root.name}-outside-proposals"
        outside.mkdir()
        (root / "proposals").rmdir()
        (root / "proposals").symlink_to(outside, target_is_directory=True)

        with self.assertRaisesRegex(EngineError, "proposals directory.*symlink"):
            self._engine(root)._validate_campaign()

    def test_rejects_parent_directory_traversal_target(self) -> None:
        root = EngineContractTests()._campaign("print('{}')")
        outside = root.parent / "eudaimon-outside-target.md"
        outside.write_text("OUTSIDE", encoding="utf-8")

        with self.assertRaisesRegex(EngineError, "must not contain"):
            self._engine(root, "../eudaimon-outside-target.md")._validate_campaign()

    def test_rejects_absolute_target_path(self) -> None:
        root = EngineContractTests()._campaign("print('{}')")

        with self.assertRaisesRegex(EngineError, "must be relative"):
            self._engine(root, str(root / "program.md"))._validate_campaign()

    def test_rejects_candidate_symlink_immediately_before_evaluation(self) -> None:
        root = EngineContractTests()._campaign("print('{}')")
        outside = root.parent / "eudaimon-outside-candidate.md"
        outside.write_text("OUTSIDE", encoding="utf-8")
        engine = self._engine(root)
        candidate = engine.proposals / "linked.md"
        candidate.symlink_to(outside)
        engine._validate_campaign()

        with self.assertRaisesRegex(EvaluationError, "symlink"):
            engine._evaluate(candidate)



class EvaluationSnapshotTests(unittest.TestCase):
    def _campaign(self, evaluator_source: str) -> Path:
        root = EngineContractTests()._campaign(evaluator_source)
        return root

    def test_evaluator_reads_read_only_snapshot_and_digest_matches_evaluated_bytes(self) -> None:
        evaluator = """
import hashlib
import json
import sys
from pathlib import Path
candidate = Path(sys.argv[sys.argv.index('--candidate') + 1])
data = candidate.read_bytes()
(Path(__file__).parent / 'snapshot-path.txt').write_text(str(candidate))
try:
    candidate.write_bytes(b'MUTATED BY EVALUATOR')
    write_blocked = False
except PermissionError:
    write_blocked = True
print(json.dumps({
    'protect_pass': True,
    'score': 1.0,
    'seen_sha256': hashlib.sha256(data).hexdigest(),
    'seen_bytes': len(data),
    'write_blocked': write_blocked
}))
"""
        root = self._campaign(evaluator)
        engine = CampaignEngine(approved_config(root))
        candidate = engine.proposals / "candidate.md"
        original = b"candidate bytes that must remain unchanged"
        candidate.write_bytes(original)
        result = engine._evaluate(candidate)

        snapshot = Path((root / "snapshot-path.txt").read_text(encoding="utf-8"))
        self.assertEqual(result["candidate_sha256"], hashlib.sha256(original).hexdigest())
        self.assertEqual(result["candidate_sha256"], result["seen_sha256"])
        self.assertEqual(result["candidate_bytes"], len(original))
        self.assertEqual(result["seen_bytes"], len(original))
        self.assertTrue(result["write_blocked"])
        self.assertEqual(candidate.read_bytes(), original)
        self.assertFalse(snapshot.exists())

    def test_snapshot_is_removed_when_evaluator_fails(self) -> None:
        evaluator = """
import json
import sys
from pathlib import Path
candidate = Path(sys.argv[sys.argv.index('--candidate') + 1])
(Path(__file__).parent / 'snapshot-path.txt').write_text(str(candidate))
raise SystemExit(9)
"""
        root = self._campaign(evaluator)
        engine = CampaignEngine(approved_config(root))
        candidate = engine.proposals / "candidate.md"
        candidate.write_text("candidate", encoding="utf-8")

        with self.assertRaisesRegex(EvaluationError, "exited 9"):
            engine._evaluate(candidate)

        snapshot = Path((root / "snapshot-path.txt").read_text(encoding="utf-8"))
        self.assertFalse(snapshot.exists())
        self.assertEqual(candidate.read_text(encoding="utf-8"), "candidate")



class PromotionTransactionTests(unittest.TestCase):
    def _engine(self, baseline: bytes = b"BASELINE") -> tuple[CampaignEngine, Path]:
        root = EngineContractTests()._campaign("print('{}')", baseline.decode())
        engine = CampaignEngine(approved_config(root))
        return engine, root

    def _intent(self, engine: CampaignEngine, transaction_id: str, old: bytes, candidate: bytes) -> None:
        engine.state_dir.mkdir(parents=True, exist_ok=True)
        engine._append_ledger({
            "event": "promotion_intent",
            "transaction_id": transaction_id,
            "run_id": "interrupted-run",
            "old_target_sha256": hashlib.sha256(old).hexdigest(),
            "candidate_sha256": hashlib.sha256(candidate).hexdigest(),
            "timestamp": "test",
        })

    def test_restart_recovers_commit_when_target_has_candidate_digest(self) -> None:
        engine, root = self._engine()
        old, candidate = b"BASELINE", b"PROMOTED"
        (root / "program.md").write_bytes(candidate)
        self._intent(engine, "tx-commit", old, candidate)

        engine._recover_incomplete_promotions()

        events = [json.loads(line) for line in engine.ledger.read_text().splitlines()]
        self.assertEqual(events[-1]["event"], "promotion_recovered_commit")
        self.assertEqual(events[-1]["transaction_id"], "tx-commit")
        self.assertEqual((root / "program.md").read_bytes(), candidate)
        self.assertEqual(engine._pending_promotion_transactions(), {})

    def test_restart_records_abort_when_target_is_still_old(self) -> None:
        engine, root = self._engine()
        old, candidate = b"BASELINE", b"PROMOTED"
        self._intent(engine, "tx-abort", old, candidate)

        engine._recover_incomplete_promotions()

        events = [json.loads(line) for line in engine.ledger.read_text().splitlines()]
        self.assertEqual(events[-1]["event"], "promotion_recovered_abort")
        self.assertEqual((root / "program.md").read_bytes(), old)

    def test_restart_halts_without_mutation_when_target_matches_neither_digest(self) -> None:
        engine, root = self._engine()
        old, candidate = b"BASELINE", b"PROMOTED"
        unknown = b"THIRD VERSION"
        (root / "program.md").write_bytes(unknown)
        self._intent(engine, "tx-ambiguous", old, candidate)

        with self.assertRaisesRegex(EngineError, "neither old nor candidate"):
            engine._recover_incomplete_promotions()

        self.assertEqual((root / "program.md").read_bytes(), unknown)
        self.assertEqual(len(engine.ledger.read_text().splitlines()), 1)

    def test_equal_old_and_candidate_digests_are_ambiguous(self) -> None:
        engine, root = self._engine()
        same = b"SAME"
        (root / "program.md").write_bytes(same)
        self._intent(engine, "tx-same", same, same)

        with self.assertRaisesRegex(EngineError, "ambiguous"):
            engine._recover_incomplete_promotions()
        self.assertEqual((root / "program.md").read_bytes(), same)

    def test_promotion_refuses_candidate_changed_since_evaluation(self) -> None:
        engine, root = self._engine()
        candidate = root / "proposals" / "candidate.md"
        candidate.write_bytes(b"ORIGINAL CANDIDATE")
        expected = hashlib.sha256(candidate.read_bytes()).hexdigest()
        candidate.write_bytes(b"CHANGED AFTER EVALUATION")

        with self.assertRaisesRegex(EngineError, "changed after evaluation"):
            engine._promote(candidate, expected, hashlib.sha256(b"BASELINE").hexdigest())
        self.assertEqual((root / "program.md").read_bytes(), b"BASELINE")

    def test_initial_state_write_failure_still_releases_run_lock(self) -> None:
        engine, root = self._engine()
        with patch.object(engine, "_write_state", side_effect=OSError("injected state failure")):
            with self.assertRaisesRegex(OSError, "injected state failure"):
                engine.run()
        self.assertFalse((root / ".autoresearch" / "run.lock").exists())

    def test_restart_recovers_after_replace_before_commit_record(self) -> None:
        engine, root = self._engine()
        old, candidate = b"BASELINE", b"PROMOTED"
        self._intent(engine, "tx-after-replace", old, candidate)
        (root / "program.md").write_bytes(candidate)  # simulated crash immediately after atomic replace

        engine._recover_incomplete_promotions()
        events = [json.loads(line) for line in engine.ledger.read_text().splitlines()]
        self.assertEqual(events[-1]["event"], "promotion_recovered_commit")
        self.assertEqual((root / "program.md").read_bytes(), candidate)


    def test_failure_before_replace_recovers_as_abort(self) -> None:
        evaluator = """
import json
import sys
from pathlib import Path
text = Path(sys.argv[sys.argv.index('--candidate') + 1]).read_text()
score = 0.1 if text == 'BASELINE' else 0.9
print(json.dumps({'protect_pass': True, 'score': score}))
"""
        root = EngineContractTests()._campaign(evaluator)
        proposal = root / "proposals" / "better.md"
        proposal.write_text("BETTER")
        engine = CampaignEngine(approved_config(root))
        with patch.object(engine, "_promote", side_effect=EngineError("injected before replace")):
            with self.assertRaisesRegex(EngineError, "injected before replace"):
                engine.run()
        self.assertEqual((root / "program.md").read_text(), "BASELINE")
        engine._recover_incomplete_promotions()
        events = [json.loads(line) for line in engine.ledger.read_text().splitlines()]
        self.assertEqual(events[-1]["event"], "promotion_recovered_abort")

    def test_state_write_failure_after_commit_keeps_ledger_and_target_consistent(self) -> None:
        evaluator = """
import json
import sys
from pathlib import Path
text = Path(sys.argv[sys.argv.index('--candidate') + 1]).read_text()
score = 0.1 if text == 'BASELINE' else 0.9
print(json.dumps({'protect_pass': True, 'score': score}))
"""
        root = EngineContractTests()._campaign(evaluator)
        (root / "proposals" / "better.md").write_text("BETTER")
        engine = CampaignEngine(approved_config(root))
        original_write_state = engine._write_state
        calls = {"count": 0}
        def fail_after_promotion(state):
            calls["count"] += 1
            if calls["count"] == 3:
                raise OSError("injected post-commit state failure")
            original_write_state(state)
        with patch.object(engine, "_write_state", side_effect=fail_after_promotion):
            with self.assertRaisesRegex(OSError, "post-commit state failure"):
                engine.run()
        self.assertEqual((root / "program.md").read_text(), "BETTER")
        self.assertFalse((root / ".autoresearch" / "run.lock").exists())
        events = [json.loads(line) for line in engine.ledger.read_text().splitlines()]
        self.assertTrue(any(event["event"] == "promotion_commit" for event in events))
        engine._recover_incomplete_promotions()
        self.assertEqual((root / "program.md").read_text(), "BETTER")

if __name__ == "__main__":
    unittest.main()


class EvaluatorContainmentTests(unittest.TestCase):
    def _engine(self, source: str, timeout: float = 2.0):
        root = EngineContractTests()._campaign(source)
        engine = CampaignEngine(approved_config(root, evaluator_timeout=timeout))
        candidate = engine.proposals / 'candidate.md'
        candidate.write_text('TEST', encoding='utf-8')
        return engine, candidate

    def test_oversized_stdout_fails_closed(self) -> None:
        engine, candidate = self._engine("import sys\nsys.stdout.write('x' * 200000)\n")
        with self.assertRaisesRegex(EvaluationError, 'output exceeded'):
            engine._evaluate(candidate)

    def test_oversized_stderr_fails_closed(self) -> None:
        engine, candidate = self._engine("import sys\nsys.stderr.write('x' * 200000)\n")
        with self.assertRaisesRegex(EvaluationError, 'output exceeded'):
            engine._evaluate(candidate)

    def test_timeout_kills_descendant_process_group(self) -> None:
        import os
        import time
        from pathlib import Path
        source = """
import subprocess
import sys
import time
from pathlib import Path
child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])
(Path(__file__).parent / 'descendant.pid').write_text(str(child.pid))
time.sleep(60)
"""
        engine, candidate = self._engine(source, timeout=0.8)
        with self.assertRaisesRegex(EvaluationError, 'timeout'):
            engine._evaluate(candidate)
        pid = int((engine.campaign / 'descendant.pid').read_text())
        # A killed descendant may briefly remain a zombie until reaped.
        time.sleep(0.1)
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return
        status = subprocess_status(pid)
        self.assertIn(status, ('Z', 'X', None), f'descendant still running: {status}')

    def test_timeout_kills_descendants_when_killpg_is_denied(self) -> None:
        import os
        import time
        source = """
import subprocess
import sys
import time
from pathlib import Path
child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])
(Path(__file__).parent / 'descendant.pid').write_text(str(child.pid))
time.sleep(60)
"""
        engine, candidate = self._engine(source, timeout=0.8)
        with patch("engine.engine.os.killpg", side_effect=PermissionError(1, "not permitted")):
            with self.assertRaisesRegex(EvaluationError, "timeout"):
                engine._evaluate(candidate)
        pid = int((engine.campaign / 'descendant.pid').read_text())
        time.sleep(0.1)
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return
        self.assertIn(subprocess_status(pid), ('Z', 'X', None))

    def test_successful_evaluator_cleans_descendants_when_killpg_is_denied(self) -> None:
        import os
        import time
        source = """
import subprocess
import sys
from pathlib import Path
child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])
(Path(__file__).parent / 'descendant.pid').write_text(str(child.pid))
print('{"protect_pass": true, "score": 1}')
"""
        engine, candidate = self._engine(source)
        with patch("engine.engine.os.killpg", side_effect=PermissionError(1, "not permitted")):
            result = engine._evaluate(candidate)
        self.assertTrue(result["protect_pass"])
        pid = int((engine.campaign / 'descendant.pid').read_text())
        time.sleep(0.1)
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return
        self.assertIn(subprocess_status(pid), ('Z', 'X', None))

    def test_permission_denied_without_group_listing_fails_closed(self) -> None:
        engine, candidate = self._engine("print('{\"protect_pass\": true, \"score\": 1}')")
        with patch("engine.engine.os.killpg", side_effect=PermissionError(1, "not permitted")):
            with patch("engine.engine.subprocess.run", side_effect=OSError("ps unavailable")):
                with self.assertRaisesRegex(EvaluationError, "cannot enumerate evaluator group"):
                    engine._evaluate(candidate)


def subprocess_status(pid: int) -> str | None:
    import subprocess
    result = subprocess.run(['ps', '-o', 'stat=', '-p', str(pid)], capture_output=True, text=True)
    if result.returncode != 0:
        return None
    return result.stdout.strip()[:1]


class AdversarialProtocolTests(unittest.TestCase):
    def _evaluate(self, source: str):
        root = EngineContractTests()._campaign(source)
        engine = CampaignEngine(approved_config(root))
        candidate = engine.proposals / 'adversarial.md'
        candidate.write_text('SAFE', encoding='utf-8')
        return engine._evaluate(candidate)

    def test_malformed_final_json_is_rejected(self) -> None:
        with self.assertRaisesRegex(EvaluationError, 'not JSON'):
            self._evaluate("print('not-json')")

    def test_non_finite_score_is_rejected(self) -> None:
        with self.assertRaisesRegex(EvaluationError, 'finite scalar score'):
            self._evaluate("print('{\"protect_pass\": true, \"score\": NaN}')")

    def test_missing_protect_gate_is_rejected(self) -> None:
        with self.assertRaisesRegex(EvaluationError, 'boolean protect_pass'):
            self._evaluate("print('{\"score\": 0.9}')")

    def test_evaluator_nonzero_exit_is_rejected(self) -> None:
        with self.assertRaisesRegex(EvaluationError, 'exited 7'):
            self._evaluate("raise SystemExit(7)")

    def test_evaluator_empty_output_is_rejected(self) -> None:
        with self.assertRaisesRegex(EvaluationError, 'no stdout'):
            self._evaluate("pass")


class LedgerFailureInjectionTests(unittest.TestCase):
    def test_ledger_write_failure_releases_lock_and_preserves_target(self) -> None:
        evaluator = "print('{\"protect_pass\": true, \"score\": 0.5}')"
        root = EngineContractTests()._campaign(evaluator)
        engine = CampaignEngine(approved_config(root))
        with patch.object(engine, "_append_ledger", side_effect=OSError("injected ledger failure")):
            with self.assertRaisesRegex(OSError, "injected ledger failure"):
                engine.run()
        self.assertEqual((root / "program.md").read_text(), "BASELINE")
        self.assertFalse((engine.state_dir / "run.lock").exists())

    def test_malformed_ledger_halts_recovery_without_rewriting_it(self) -> None:
        root = EngineContractTests()._campaign("print('{}')")
        engine = CampaignEngine(approved_config(root))
        engine.state_dir.mkdir(parents=True, exist_ok=True)
        malformed = b'{"event":"promotion_intent", bad json}\n'
        engine.ledger.write_bytes(malformed)
        with self.assertRaisesRegex(EngineError, "malformed ledger line"):
            engine.run()
        self.assertEqual(engine.ledger.read_bytes(), malformed)
        self.assertEqual((root / "program.md").read_text(), "BASELINE")
        self.assertFalse((engine.state_dir / "run.lock").exists())
