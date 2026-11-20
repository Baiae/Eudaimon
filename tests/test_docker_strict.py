"""Strict Docker evaluator: stdlib-only fail-closed unit tests (no Docker needed)."""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from engine.engine import (
    CampaignEngine, DOCKER_IMAGE, EngineConfig, EvaluationError,
    TRUSTED_REFERENCE_EVALUATOR_SHA256,
)


class StrictBackendContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="eudaimon-strict-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        reference = Path(__file__).resolve().parent.parent / "campaigns" / "rr_engine"
        for name in ("eval_runner.py", "rr_policy.py", "program.md"):
            shutil.copy2(reference / name, self.root / name)
        (self.root / "proposals").mkdir()
        self.engine = CampaignEngine(
            EngineConfig(self.root, evaluator_backend="docker-strict")
        )

    def test_docker_mode_is_explicit_opt_in(self):
        self.assertEqual(EngineConfig(self.root).evaluator_backend, "trusted-local")

    def test_unsupported_backend_rejected_before_writing_state(self):
        bad = CampaignEngine(EngineConfig(self.root, evaluator_backend="magic"))
        with self.assertRaisesRegex(Exception, "unsupported evaluator backend"):
            bad.run()
        self.assertFalse((self.root / ".autoresearch").exists())

    def test_strict_mode_rejects_custom_evaluator_pin(self):
        bad = CampaignEngine(EngineConfig(
            self.root, evaluator_backend="docker-strict",
            trusted_evaluator_sha256="0" * 64,
        ))
        with self.assertRaisesRegex(Exception, "untrusted evaluator|reviewed reference"):
            bad.run()
        self.assertFalse((self.root / ".autoresearch").exists())

    def test_remote_docker_context_rejected_before_image_lookup(self):
        def run(command, **kwargs):
            self.assertEqual(command[1:3], ["context", "inspect"])
            return subprocess.CompletedProcess(
                command, 0, stdout="tcp://remote.example.invalid:2376\n", stderr=""
            )
        with patch("engine.engine.shutil.which", return_value="/usr/local/bin/docker"), \
             patch("engine.engine.subprocess.run", side_effect=run):
            result = self.engine.run()
        self.assertEqual(result.reason, "baseline_evaluation_error")
        self.assertFalse(any(e["event"] == "baseline" for e in [
            json.loads(x) for x in self.engine.ledger.read_text().splitlines()
        ]))

    def test_docker_host_override_rejected(self):
        with patch.dict("engine.engine.os.environ", {"DOCKER_HOST": "tcp://remote.invalid:2376"}), \
             patch("engine.engine.shutil.which", return_value="/usr/local/bin/docker"), \
             patch("engine.engine.subprocess.run") as run:
            result = self.engine.run()
        self.assertEqual(result.reason, "baseline_evaluation_error")
        run.assert_not_called()

    def test_missing_docker_halts_without_fallback_or_promotion(self):
        with patch("engine.engine.shutil.which", return_value=None):
            result = self.engine.run()
        self.assertEqual((result.exit_code, result.reason), (2, "baseline_evaluation_error"))
        events = [json.loads(x) for x in self.engine.ledger.read_text().splitlines()]
        self.assertEqual(events[-2]["event"], "evaluation_error")
        self.assertIn("docker CLI not found", events[-2]["error"])
        self.assertEqual(events[-1]["event"], "halt")
        self.assertEqual((self.root / "program.md").read_bytes(),
                         (Path(__file__).resolve().parent.parent / "campaigns" / "rr_engine" / "program.md").read_bytes())

    def test_missing_pinned_image_never_creates_or_pulls(self):
        calls = []
        def run(command, **kwargs):
            calls.append(command)
            if command[1:3] == ["context", "inspect"]:
                return subprocess.CompletedProcess(
                    command, 0, stdout="unix:///var/run/docker.sock\n", stderr=""
                )
            return subprocess.CompletedProcess(command, 1, stdout=b"", stderr=b"missing")
        with patch("engine.engine.shutil.which", return_value="/usr/local/bin/docker"), \
             patch("engine.engine.subprocess.run", side_effect=run):
            result = self.engine.run()
        self.assertEqual(result.reason, "baseline_evaluation_error")
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[0][1:3], ["context", "inspect"])
        self.assertEqual(calls[1][1:3], ["image", "inspect"])
        self.assertEqual(calls[1][-1], DOCKER_IMAGE)

    def test_create_command_mounts_only_three_reviewed_inputs(self):
        calls = []
        def run(command, **kwargs):
            calls.append(command)
            if command[1:3] == ["context", "inspect"]:
                return subprocess.CompletedProcess(
                    command, 0, stdout="unix:///var/run/docker.sock\n", stderr=""
                )
            if command[1:3] == ["image", "inspect"]:
                return subprocess.CompletedProcess(command, 0, stdout=b"[]", stderr=b"")
            if command[1] == "create":
                return subprocess.CompletedProcess(command, 1, stdout="", stderr="synthetic failure")
            if command[1] == "rm":
                return subprocess.CompletedProcess(command, 1, stdout="", stderr="No such container")
            if command[1] == "inspect":
                return subprocess.CompletedProcess(command, 1, stdout="", stderr="error: no such object")
            raise AssertionError(command)
        with patch("engine.engine.shutil.which", return_value="/usr/local/bin/docker"), \
             patch("engine.engine.subprocess.run", side_effect=run):
            result = self.engine.run()
        self.assertEqual(result.reason, "baseline_evaluation_error")
        create = next(c for c in calls if c[1] == "create")
        for flag in ("--pull=never", "--network", "--read-only", "--cap-drop",
                     "--security-opt", "--pids-limit", "--memory", "--cpus",
                     "--user", "--tmpfs"):
            self.assertIn(flag, create)
        self.assertEqual(create[create.index("--network") + 1], "none")
        self.assertEqual(create[create.index("--cap-drop") + 1], "ALL")
        self.assertEqual(create[create.index("--security-opt") + 1], "no-new-privileges")
        self.assertEqual(create[-6:], [
            DOCKER_IMAGE, "-I", "-B", "/eval_runner.py", "--candidate", "/candidate.md"
        ])
        mounts = [create[i+1] for i, arg in enumerate(create[:-1]) if arg == "--mount"]
        self.assertEqual(len(mounts), 3)
        self.assertEqual({m.split(",dst=")[1].split(",")[0] for m in mounts},
                         {"/eval_runner.py", "/rr_policy.py", "/candidate.md"})
        self.assertTrue(all(m.endswith(",readonly") for m in mounts))
        self.assertFalse(any(str(self.root) == m.split(",src=")[1].split(",")[0] for m in mounts))
        self.assertFalse(any(c[1] == "pull" for c in calls))

    def test_failed_start_still_removes_container(self):
        calls = []
        def run(command, **kwargs):
            calls.append(command)
            if command[1:3] == ["context", "inspect"]:
                return subprocess.CompletedProcess(
                    command, 0, stdout="unix:///var/run/docker.sock\n", stderr=""
                )
            if command[1:3] == ["image", "inspect"]:
                return subprocess.CompletedProcess(command, 0, stdout=b"[]", stderr=b"")
            if command[1] == "create":
                return subprocess.CompletedProcess(command, 0, stdout="a" * 64 + "\n", stderr="")
            if command[1] == "rm":
                return subprocess.CompletedProcess(command, 0, stdout="", stderr="")
            if command[1] == "inspect":
                return subprocess.CompletedProcess(command, 1, stdout="", stderr="No such object")
            raise AssertionError(command)
        with patch("engine.engine.shutil.which", return_value="/usr/local/bin/docker"), \
             patch("engine.engine.subprocess.run", side_effect=run), \
             patch("engine.engine.subprocess.Popen", side_effect=OSError("synthetic attach error")):
            result = self.engine.run()
        self.assertEqual(result.reason, "baseline_evaluation_error")
        self.assertTrue(any(c[1:3] == ["rm", "-f"] for c in calls))
        self.assertTrue(any(c[1] == "inspect" for c in calls))

    def test_cleanup_uncertainty_refuses_valid_evaluator_output(self):
        calls = []
        def run(command, **kwargs):
            calls.append(command)
            if command[1:3] == ["context", "inspect"]:
                return subprocess.CompletedProcess(
                    command, 0, stdout="unix:///var/run/docker.sock\n", stderr=""
                )
            if command[1:3] == ["image", "inspect"]:
                return subprocess.CompletedProcess(command, 0, stdout=b"[]", stderr=b"")
            if command[1] == "create":
                return subprocess.CompletedProcess(command, 0, stdout="a" * 64 + "\n", stderr="")
            if command[1:3] == ["inspect", "--format"]:
                return subprocess.CompletedProcess(
                    command, 0,
                    stdout=json.dumps({"Status": "exited", "Running": False, "ExitCode": 0}),
                    stderr="",
                )
            if command[1] == "rm":
                return subprocess.CompletedProcess(command, 0, stdout="", stderr="")
            if command[1] == "inspect":
                return subprocess.CompletedProcess(command, 1, stdout="", stderr="permission denied")
            raise AssertionError(command)

        class FakeProcess:
            def __init__(self, *args, **kwargs):
                kwargs["stdout"].write(b'{"protect_pass":true,"score":0.8}\n')
                kwargs["stdout"].flush()
            def wait(self, timeout=None):
                return 0
            def poll(self):
                return 0

        with patch("engine.engine.shutil.which", return_value="/usr/local/bin/docker"), \
             patch("engine.engine.subprocess.run", side_effect=run), \
             patch("engine.engine.subprocess.Popen", side_effect=FakeProcess), \
             patch.object(self.engine, "_terminate_evaluator_group"):
            result = self.engine.run()
        self.assertEqual(result.reason, "baseline_evaluation_error")
        self.assertTrue(any("cleanup failed" in e.get("error", "") for e in
                            [json.loads(x) for x in self.engine.ledger.read_text().splitlines()]))
        self.assertFalse(any(e["event"] == "baseline" for e in
                             [json.loads(x) for x in self.engine.ledger.read_text().splitlines()]))

    def test_timeout_attempts_container_removal_and_halts(self):
        calls = []
        def run(command, **kwargs):
            calls.append(command)
            if command[1:3] == ["context", "inspect"]:
                return subprocess.CompletedProcess(
                    command, 0, stdout="unix:///var/run/docker.sock\n", stderr=""
                )
            if command[1:3] == ["image", "inspect"]:
                return subprocess.CompletedProcess(command, 0, stdout=b"[]", stderr=b"")
            if command[1] == "create":
                return subprocess.CompletedProcess(command, 0, stdout="b" * 64 + "\n", stderr="")
            if command[1] == "rm":
                return subprocess.CompletedProcess(command, 0, stdout="", stderr="")
            if command[1] == "inspect":
                return subprocess.CompletedProcess(command, 1, stdout="", stderr="No such object")
            raise AssertionError(command)

        class FakeTimedOutProcess:
            def __init__(self, *args, **kwargs):
                self.pid = 999999
            def wait(self, timeout=None):
                raise subprocess.TimeoutExpired("docker start", timeout)
            def poll(self):
                return 0

        with patch("engine.engine.shutil.which", return_value="/usr/local/bin/docker"), \
             patch("engine.engine.subprocess.run", side_effect=run), \
             patch("engine.engine.subprocess.Popen", side_effect=FakeTimedOutProcess), \
             patch.object(self.engine, "_terminate_evaluator_group"):
            result = self.engine.run()
        self.assertEqual(result.reason, "baseline_evaluation_error")
        self.assertTrue(any(c[1:3] == ["rm", "-f"] for c in calls))

    def test_stage_rejects_source_modified_after_review(self):
        destination = self.root / "staged.py"
        with self.assertRaisesRegex(EvaluationError, "changed while staging"):
            self.engine._stage_docker_input(
                self.root / "eval_runner.py", destination, "0" * 64
            )

    def test_reviewed_adapter_digest_matches_constant(self):
        digest = hashlib.sha256((self.root / "eval_runner.py").read_bytes()).hexdigest()
        self.assertEqual(digest, TRUSTED_REFERENCE_EVALUATOR_SHA256)


if __name__ == "__main__":
    unittest.main()
