"""Explicit Docker integration tests. Never part of the default stdlib CI suite.

Requires preinstalled pinned image; synthetic files only. Run with:
python3 -B -m unittest discover -s tests_docker -v
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import unittest
import uuid
from pathlib import Path

from engine.engine import CampaignEngine, DOCKER_IMAGE, EngineConfig


def docker(*args: str, timeout: float = 30) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["docker", *args], capture_output=True, text=True, timeout=timeout,
    )


class DockerStrictIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if shutil.which("docker") is None:
            raise RuntimeError("Docker is required for explicit strict integration tests")
        probe = docker("image", "inspect", DOCKER_IMAGE)
        if probe.returncode != 0:
            raise RuntimeError("Pinned Python OCI image must be installed before integration tests")

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="eudaimon-docker-integration-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        reference = Path(__file__).resolve().parent.parent / "campaigns" / "rr_engine"
        for name in ("eval_runner.py", "rr_policy.py", "program.md"):
            shutil.copy2(reference / name, self.root / name)
        (self.root / "proposals").mkdir()
        self.engine = CampaignEngine(
            EngineConfig(self.root, evaluator_backend="docker-strict", evaluator_timeout=20)
        )

    def _events(self):
        return [json.loads(line) for line in self.engine.ledger.read_text().splitlines()]

    def test_reference_baseline_executes_in_pinned_container(self):
        result = self.engine.run()
        self.assertEqual((result.exit_code, result.reason), (0, "no_proposals"))
        baseline = next(e for e in self._events() if e["event"] == "baseline")
        self.assertTrue(baseline["evaluation"]["protect_pass"])
        self.assertEqual(baseline["evaluation"]["evaluator_backend"], "docker-strict")
        self.assertEqual(baseline["evaluation"]["image_digest"], DOCKER_IMAGE.split("@")[1])
        self.assertEqual(docker("ps", "-aq", "--filter", "name=eudaimon-strict-").stdout.strip(), "")

    def test_unsafe_proposal_halts_without_promotion(self):
        original = (self.root / "program.md").read_bytes()
        (self.root / "proposals" / "unsafe.md").write_bytes(original + b"\nPROTECT_GATE_BYPASS\n")
        result = self.engine.run()
        self.assertEqual((result.exit_code, result.reason), (3, "candidate_protect_failed"))
        self.assertEqual((self.root / "program.md").read_bytes(), original)
        self.assertFalse(any(e["event"] == "promotion_intent" for e in self._events()))

    def test_safe_improvement_promotes_with_transaction_evidence(self):
        original = (self.root / "program.md").read_text()
        (self.root / "program.md").write_text(original.replace("geometric mean", "arithmetic mean"))
        (self.root / "proposals" / "better.md").write_text(original)
        result = self.engine.run()
        self.assertEqual((result.exit_code, result.reason), (0, "proposal_exhausted"))
        self.assertEqual((self.root / "program.md").read_text(), original)
        self.assertEqual(len([e for e in self._events() if e["event"] == "promotion_commit"]), 1)

    def test_synthetic_container_cannot_read_host_secret_write_host_or_network(self):
        # Test the exact Docker security flags independently of the pinned
        # reference evaluator; no arbitrary code is routed through Eudaimon.
        secret = self.root / "host-secret.txt"
        secret.write_text("SYNTHETIC_ONLY")
        candidate = self.root / "candidate.txt"
        candidate.write_text("CANDIDATE_UNMODIFIED")
        probe = self.root / "probe.py"
        probe.write_text(
            "import json, pathlib, socket, os\n"
            "results={}\n"
            "for key,fn in [\n"
            " ('host_secret',lambda: pathlib.Path('/host-secret.txt').read_text()),\n"
            " ('root_write',lambda: pathlib.Path('/created-by-probe').write_text('x')),\n"
            " ('candidate_write',lambda: pathlib.Path('/candidate.txt').write_text('CHANGED')),\n"
            " ('network',lambda: socket.create_connection(('1.1.1.1',443),timeout=1))]:\n"
            " try:\n"
            "  fn();results[key]='ALLOWED'\n"
            " except Exception as exc:\n"
            "  results[key]=type(exc).__name__\n"
            "print(json.dumps({'uid':os.getuid(),'checks':results}))\n"
        )
        name = "eudaimon-synthetic-probe-" + uuid.uuid4().hex
        cmd = [
            "create", "--pull=never", "--name", name, "--network", "none",
            "--read-only", "--cap-drop", "ALL",
            "--security-opt", "no-new-privileges", "--pids-limit", "32",
            "--memory", "256m", "--cpus", "1",
            "--user", f"{os.getuid()}:{os.getgid()}",
            "--workdir", "/", "--tmpfs", "/tmp:rw,nosuid,nodev,size=16m",
            "--mount", f"type=bind,src={probe},dst=/probe.py,readonly",
            "--mount", f"type=bind,src={candidate},dst=/candidate.txt,readonly",
            "--entrypoint", "python3", DOCKER_IMAGE, "-I", "-B", "/probe.py",
        ]
        try:
            creation = docker(*cmd)
            self.assertEqual(creation.returncode, 0, creation.stderr)
            execution = docker("start", "-a", name, timeout=15)
            self.assertEqual(execution.returncode, 0, execution.stderr)
            result = json.loads(execution.stdout.strip().splitlines()[-1])
            self.assertNotEqual(result["uid"], 0)
            for check in ("host_secret", "root_write", "candidate_write", "network"):
                self.assertNotEqual(result["checks"][check], "ALLOWED", check)
            self.assertEqual(secret.read_text(), "SYNTHETIC_ONLY")
            self.assertEqual(candidate.read_text(), "CANDIDATE_UNMODIFIED")
        finally:
            removal = docker("rm", "-f", name)
            inspection = docker("inspect", name)
            self.assertNotEqual(inspection.returncode, 0)
            self.assertIn("No such", inspection.stderr)


if __name__ == "__main__":
    unittest.main()
