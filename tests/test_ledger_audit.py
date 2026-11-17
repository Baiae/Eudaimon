import json
import tempfile
import unittest
from pathlib import Path

from tools.audit_ledger import audit_ledger


class LegacyLedgerAuditTests(unittest.TestCase):
    def test_detects_partial_line_without_mutation(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = Path(directory) / 'ledger.jsonl'
            ledger.write_bytes(b'{"event":"halt"}\n{"event":"incomplete"')
            before = ledger.read_bytes()
            result = audit_ledger(ledger)
            self.assertTrue(any('newline-terminated' in issue for issue in result['issues']))
            self.assertEqual(ledger.read_bytes(), before)

    def test_detects_orphan_promotion_outcome(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = Path(directory) / 'ledger.jsonl'
            ledger.write_text(json.dumps({'event': 'promotion_commit', 'transaction_id': 'orphan'}) + '\n')
            result = audit_ledger(ledger)
            self.assertTrue(any('unmatched' in issue for issue in result['issues']))

    def test_valid_legacy_events_are_not_claimed_tamper_proof(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = Path(directory) / 'ledger.jsonl'
            ledger.write_text(json.dumps({'event': 'halt', 'reason': 'test', 'run_id': 'run-1', 'timestamp': 'test', 'state': {}}) + '\n')
            result = audit_ledger(ledger)
            self.assertEqual(result['issues'], [])
            self.assertEqual(result['integrity_level'], 'STRUCTURAL_ONLY_NOT_TAMPER_PROOF')

    def test_detects_duplicate_promotion_intent(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = Path(directory) / 'ledger.jsonl'
            line = json.dumps({'event': 'promotion_intent', 'transaction_id': 'duplicate'}) + '\n'
            ledger.write_text(line + line)
            report = audit_ledger(ledger)
            self.assertTrue(any('duplicate' in issue for issue in report['issues']))

    def test_detects_malformed_json_without_mutation(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = Path(directory) / 'ledger.jsonl'
            ledger.write_bytes(b'not-json\n')
            before = ledger.read_bytes()
            report = audit_ledger(ledger)
            self.assertTrue(any('invalid JSON' in issue for issue in report['issues']))
            self.assertEqual(ledger.read_bytes(), before)

    def _inspect(self, events):
        with tempfile.TemporaryDirectory() as directory:
            ledger = Path(directory) / "ledger.jsonl"
            ledger.write_text("".join(json.dumps(event) + "\n" for event in events))
            original = ledger.read_bytes()
            report = audit_ledger(ledger)
            self.assertEqual(ledger.read_bytes(), original)
            return report

    def _intent(self, tid="tx-1"):
        return {
            "event": "promotion_intent", "transaction_id": tid,
            "run_id": "run-1", "timestamp": "test",
            "old_target_sha256": "a" * 64, "candidate_sha256": "b" * 64,
        }

    def test_rejects_duplicate_json_keys_and_non_finite_values(self):
        for record in (b'{"event":"halt","event":"baseline"}\n',
                       b'{"event":"baseline","score":NaN}\n'):
            with self.subTest(record=record):
                with tempfile.TemporaryDirectory() as directory:
                    ledger = Path(directory) / "ledger.jsonl"
                    ledger.write_bytes(record)
                    report = audit_ledger(ledger)
                    self.assertTrue(report["issues"])

    def test_rejects_invalid_intent_sha256(self):
        intent = self._intent()
        intent["candidate_sha256"] = "NOT_A_DIGEST"
        report = self._inspect([intent])
        self.assertTrue(any("candidate_sha256" in issue for issue in report["issues"]))

    def test_rejects_commit_hash_not_matching_intent(self):
        report = self._inspect([
            self._intent(),
            {"event": "promotion_commit", "run_id": "run-1", "timestamp": "test",
             "transaction_id": "tx-1", "target_sha256": "c" * 64}
        ])
        self.assertTrue(any("target_sha256" in issue or "digest" in issue for issue in report["issues"]))

    def test_rejects_reused_transaction_id_after_completion(self):
        intent = self._intent()
        outcome = {"event": "promotion_commit", "run_id": "run-1", "timestamp": "test",
                   "transaction_id": "tx-1", "target_sha256": "b" * 64}
        report = self._inspect([intent, outcome, intent])
        self.assertTrue(any("duplicate" in issue or "reused" in issue for issue in report["issues"]))

    def test_rejects_wrong_recovery_digest(self):
        report = self._inspect([
            self._intent(),
            {"event": "promotion_recovered_abort", "run_id": "run-1", "timestamp": "test",
             "transaction_id": "tx-1", "recovered_target_sha256": "b" * 64}
        ])
        self.assertTrue(any("recovered_target_sha256" in issue or "digest" in issue for issue in report["issues"]))

    def test_rejects_orphan_promoted_candidate(self):
        report = self._inspect([{
            "event": "candidate", "run_id": "run-1", "timestamp": "test",
            "iteration": 1, "candidate": "good.md", "decision": "promoted",
            "transaction_id": "unknown", "evaluation": {"protect_pass": True, "score": 0.9}
        }])
        self.assertTrue(any("promoted" in issue or "transaction" in issue for issue in report["issues"]))

    def test_rejects_incomplete_required_event_fields(self):
        report = self._inspect([{"event": "baseline"}])
        self.assertTrue(any("run_id" in issue or "timestamp" in issue for issue in report["issues"]))

    def test_legacy_campaign_is_structurally_valid_without_mutation(self):
        ledger = Path(__file__).resolve().parent.parent / "campaigns/rr_engine/.autoresearch/ledger.jsonl"
        if not ledger.exists():
            self.skipTest("historical campaign evidence not available")
        before = ledger.read_bytes()
        report = audit_ledger(ledger)
        self.assertEqual(report["issues"], [])
        self.assertEqual(report["pending_transactions"], [])
        self.assertEqual(report["integrity_level"], "STRUCTURAL_ONLY_NOT_TAMPER_PROOF")
        self.assertEqual(ledger.read_bytes(), before)

    def test_unrepresentably_large_score_is_reported_not_crashed(self):
        report = self._inspect([{
            "event": "baseline", "run_id": "run-1", "timestamp": "test",
            "candidate": "baseline.md",
            "evaluation": {"protect_pass": True, "score": 10 ** 1000}
        }])
        self.assertTrue(any("score" in issue for issue in report["issues"]))

    def test_pending_transaction_is_reported_without_false_completion(self):
        report = self._inspect([self._intent()])
        self.assertEqual(report["pending_transactions"], ["tx-1"])
        self.assertEqual(report["issues"], [])
