#!/usr/bin/env python3
"""Small, harness-agnostic AutoResearch-W campaign engine.

The engine deliberately does not generate proposals. It evaluates complete
candidate files supplied by a campaign, applies the fixed lexicographic rule,
and owns campaign halts. It is a reference sketch, not a security sandbox.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import signal
import resource
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ENGINE_VERSION = "autoresearch-w-reference-0.1"
DEFAULT_TARGET = "program.md"
DEFAULT_MAX_ITERATIONS = 20
DEFAULT_MAX_NO_IMPROVEMENT = 5
DEFAULT_EVALUATOR_TIMEOUT = 30.0
MAX_EVALUATOR_OUTPUT_BYTES = 65_536
DEFAULT_EVALUATOR_BACKEND = "trusted-local"
DOCKER_IMAGE = (
    "docker.io/library/python@sha256:"
    "593bd06efe90efa80dc4eee3948be7c0fde4134606dd40d8dd8dbcade98e669c"
)
# Reviewed official Python 3.12.12 slim-bookworm multi-arch OCI index.
# Strict mode never pulls images automatically. Runtime digest requires approval
# for each future update; a digest pin is not a container-escape guarantee.
# Reviewed, bundled reference evaluator only. Updates require an explicit source review.
# This is an integrity pin, NOT a sandbox or an authentication mechanism.
TRUSTED_REFERENCE_EVALUATOR_SHA256 = "dbad5763e68b66c40dbfd852ea80ca041ffa0811c788bdcadc13ee0e5095cff5"
TRUSTED_REFERENCE_POLICY_SHA256 = "bc6c31a850e7a99723eb96d94098591d8ade287ff6c765b3ebff60d5a2db4b37"


class EngineError(RuntimeError):
    """A fail-closed engine or campaign-contract error."""


class EvaluationError(EngineError):
    """The evaluator did not produce a trustworthy result."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _is_finite_number(value: Any) -> bool:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    try:
        return math.isfinite(float(value))
    except (OverflowError, ValueError, TypeError):
        return False


def validate_evaluation(payload: Any) -> dict[str, Any]:
    """Validate the stable evaluator protocol and return a normalized copy."""

    if not isinstance(payload, dict):
        raise EvaluationError("evaluator output must be a JSON object")
    if not isinstance(payload.get("protect_pass"), bool):
        raise EvaluationError("evaluator output must contain boolean protect_pass")
    if not _is_finite_number(payload.get("score")):
        raise EvaluationError("evaluator output must contain a finite scalar score")
    result = dict(payload)
    result["score"] = float(payload["score"])
    if "components" in result and not isinstance(result["components"], dict):
        raise EvaluationError("components must be an object when present")
    # json.loads permits NaN/Infinity and huge exponents can become infinity.
    # Reject non-finite numbers at every depth before writing any ledger event.
    try:
        json.dumps(result, allow_nan=False)
    except (ValueError, TypeError, OverflowError) as exc:
        raise EvaluationError("evaluator output contains non-finite or invalid JSON values") from exc
    return result


def lexicographically_better(candidate: dict[str, Any], incumbent: dict[str, Any]) -> bool:
    """Apply the fixed Protect Gate, then scalar-score ordering."""

    candidate_protect = bool(candidate["protect_pass"])
    incumbent_protect = bool(incumbent["protect_pass"])
    if candidate_protect != incumbent_protect:
        return candidate_protect
    if not candidate_protect:
        return False
    return float(candidate["score"]) > float(incumbent["score"])


@dataclass(frozen=True)
class EngineConfig:
    campaign: Path
    target: str = DEFAULT_TARGET
    max_iterations: int = DEFAULT_MAX_ITERATIONS
    max_no_improvement: int = DEFAULT_MAX_NO_IMPROVEMENT
    evaluator_timeout: float = DEFAULT_EVALUATOR_TIMEOUT
    # A programmatic caller may pin its own previously reviewed evaluator (e.g. tests).
    # The CLI intentionally does not expose a self-approval switch.
    trusted_evaluator_sha256: str | None = None
    evaluator_backend: str = DEFAULT_EVALUATOR_BACKEND


@dataclass(frozen=True)
class RunResult:
    run_id: str
    status: str
    reason: str
    iterations: int
    promoted: int
    exit_code: int


class RunLock:
    """Atomic lock with ownership-checked release and no implicit stale recovery."""

    def __init__(self, path: Path, run_id: str):
        self.path = path
        self.run_id = run_id
        self._inode: tuple[int, int] | None = None

    def acquire(self) -> None:
        flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
        try:
            fd = os.open(self.path, flags, 0o600)
        except FileExistsError as exc:
            raise EngineError(f"run lock already exists: {self.path}") from exc

        created = os.fstat(fd)
        self._inode = (created.st_dev, created.st_ino)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump({"run_id": self.run_id}, handle, sort_keys=True)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
        except Exception:
            self._unlink_if_created_inode()
            raise

    def _unlink_if_created_inode(self) -> None:
        if self._inode is None:
            return
        try:
            current = self.path.lstat()
        except FileNotFoundError:
            return
        if (current.st_dev, current.st_ino) == self._inode:
            self.path.unlink(missing_ok=True)

    def release(self) -> None:
        try:
            with self.path.open("r", encoding="utf-8") as handle:
                lock_data = json.load(handle)
            current = self.path.lstat()
        except FileNotFoundError as exc:
            raise EngineError("run lock disappeared before release") from exc
        except (OSError, json.JSONDecodeError) as exc:
            raise EngineError("run lock is unreadable or malformed; refusing release") from exc

        if not stat.S_ISREG(current.st_mode):
            raise EngineError("run lock is not a regular file; refusing release")
        if not isinstance(lock_data, dict):
            raise EngineError("run lock metadata is malformed; refusing release")
        if lock_data.get("run_id") != self.run_id:
            raise EngineError("run lock is owned by another run; refusing release")
        if self._inode is not None and (current.st_dev, current.st_ino) != self._inode:
            raise EngineError("run lock inode changed; refusing release")
        self.path.unlink()
        self._inode = None


class CampaignEngine:
    def __init__(self, config: EngineConfig):
        self.config = config
        self.campaign = config.campaign.resolve()
        target_relative = Path(config.target)
        self.target = self.campaign / target_relative
        self.evaluator = self.campaign / "eval_runner.py"
        self.proposals = self.campaign / "proposals"
        self.state_dir = self.campaign / ".autoresearch"
        self.ledger = self.state_dir / "ledger.jsonl"
        self.state_path = self.state_dir / "state.json"

    def _validate_path_components(
        self,
        path: Path,
        root: Path,
        label: str,
        expected_type: str,
    ) -> None:
        try:
            relative = path.relative_to(root)
        except ValueError as exc:
            raise EngineError(f"{label} escapes campaign directory: {path}") from exc

        if not relative.parts or any(part in (".", "..") for part in relative.parts):
            raise EngineError(f"{label} has an invalid campaign-relative path: {path}")

        current = root
        for index, part in enumerate(relative.parts):
            current = current / part
            try:
                mode = current.lstat().st_mode
            except OSError as exc:
                raise EngineError(f"{label} path component is unavailable: {current}") from exc

            if stat.S_ISLNK(mode):
                raise EngineError(f"{label} path contains a symlink: {current}")

            is_final = index == len(relative.parts) - 1
            if not is_final and not stat.S_ISDIR(mode):
                raise EngineError(f"{label} parent component is not a directory: {current}")

            if is_final:
                valid = stat.S_ISREG(mode) if expected_type == "file" else stat.S_ISDIR(mode)
                if not valid:
                    raise EngineError(f"{label} must be a regular {expected_type}: {current}")

    def _validate_candidate_path(self, candidate: Path) -> None:
        if candidate == self.target:
            self._validate_path_components(candidate, self.campaign, "target candidate", "file")
            return

        try:
            relative = candidate.relative_to(self.proposals)
        except ValueError as exc:
            raise EvaluationError(f"candidate is outside the authorized target/proposals paths: {candidate}") from exc

        if len(relative.parts) != 1:
            raise EvaluationError(f"candidate must be a direct child of proposals: {candidate}")

        try:
            self._validate_path_components(self.proposals, self.campaign, "proposals directory", "directory")
            self._validate_path_components(candidate, self.proposals, "candidate", "file")
        except EngineError as exc:
            raise EvaluationError(str(exc)) from exc

    def _validate_evaluator_trust(self) -> None:
        """Refuse execution unless the evaluator bytes match an explicit trust pin."""
        self._validate_path_components(self.evaluator, self.campaign, "evaluator", "file")
        expected = self.config.trusted_evaluator_sha256 or TRUSTED_REFERENCE_EVALUATOR_SHA256
        if not isinstance(expected, str) or len(expected) != 64 or any(c not in "0123456789abcdef" for c in expected):
            raise EngineError("invalid trusted evaluator SHA-256 pin")
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
        try:
            fd = os.open(self.evaluator, flags)
            with os.fdopen(fd, "rb") as handle:
                if not stat.S_ISREG(os.fstat(handle.fileno()).st_mode):
                    raise EngineError("evaluator is not a regular file")
                digest = hashlib.sha256()
                for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                    digest.update(chunk)
        except OSError as exc:
            raise EngineError("cannot verify trusted evaluator bytes") from exc
        if digest.hexdigest() != expected:
            raise EngineError("untrusted evaluator: SHA-256 does not match reviewed pin")
        if expected == TRUSTED_REFERENCE_EVALUATOR_SHA256:
            # The reviewed adapter imports this campaign-local module. Pin it too.
            policy = self.campaign / "rr_policy.py"
            self._validate_path_components(policy, self.campaign, "evaluator policy", "file")
            try:
                fd = os.open(policy, flags)
                with os.fdopen(fd, "rb") as handle:
                    if not stat.S_ISREG(os.fstat(handle.fileno()).st_mode):
                        raise EngineError("evaluator policy is not a regular file")
                    policy_digest = hashlib.sha256()
                    for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                        policy_digest.update(chunk)
            except OSError as exc:
                raise EngineError("cannot verify trusted evaluator policy bytes") from exc
            if policy_digest.hexdigest() != TRUSTED_REFERENCE_POLICY_SHA256:
                raise EngineError("untrusted evaluator policy: SHA-256 does not match reviewed pin")

    def _validate_campaign(self) -> None:
        if not self.campaign.is_dir():
            raise EngineError(f"campaign directory not found: {self.campaign}")

        target_relative = Path(self.config.target)
        if target_relative.is_absolute():
            raise EngineError("target path must be relative to the campaign directory")
        if not target_relative.parts or any(part in (".", "..") for part in target_relative.parts):
            raise EngineError("target path must not contain empty, current-directory, or parent-directory components")

        self._validate_path_components(self.target, self.campaign, "target", "file")
        self._validate_path_components(self.evaluator, self.campaign, "evaluator", "file")
        self._validate_path_components(self.proposals, self.campaign, "proposals directory", "directory")
        self._validate_evaluator_trust()

        if self.config.max_iterations < 0:
            raise EngineError("max_iterations must be non-negative")
        if self.config.max_no_improvement <= 0:
            raise EngineError("max_no_improvement must be positive")
        if self.config.evaluator_timeout <= 0:
            raise EngineError("evaluator_timeout must be positive")
        if self.config.evaluator_backend not in ("trusted-local", "docker-strict"):
            raise EngineError("unsupported evaluator backend")
        if self.config.evaluator_backend == "docker-strict":
            # Strict mode currently supports only the independently pinned
            # reference adapter and policy, not arbitrary custom evaluators.
            if self.config.trusted_evaluator_sha256 not in (
                None, TRUSTED_REFERENCE_EVALUATOR_SHA256
            ):
                raise EngineError("docker-strict requires the reviewed reference evaluator")
            if os.getuid() == 0:
                raise EngineError("docker-strict refuses a root host identity")

    def _ensure_state_dir(self) -> None:
        created = not self.state_dir.exists()
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self._validate_path_components(self.state_dir, self.campaign, "state directory", "directory")
        if created:
            # Persist the newly created directory entry before any promotion.
            self._fsync_directory(self.campaign, required=True)

    def _write_state(self, state: dict[str, Any]) -> None:
        self._ensure_state_dir()
        fd, temp_name = tempfile.mkstemp(prefix=".state.", dir=self.state_dir)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(state, handle, indent=2, sort_keys=True)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_name, self.state_path)
            self._fsync_directory(self.state_dir, required=True)
        finally:
            Path(temp_name).unlink(missing_ok=True)

    def _append_ledger(self, event: dict[str, Any]) -> None:
        self._ensure_state_dir()
        created = not self.ledger.exists()
        with self.ledger.open("a", encoding="utf-8") as handle:
            json.dump(event, handle, sort_keys=True, allow_nan=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        if created:
            # fsync(file) does not persist a newly created directory entry.
            self._fsync_directory(self.state_dir, required=True)

    def _create_evaluation_snapshot(self, candidate: Path) -> tuple[Path, str, int]:
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
        try:
            source_fd = os.open(candidate, flags)
        except OSError as exc:
            raise EvaluationError(f"could not open candidate without following symlinks: {candidate}") from exc

        snapshot_fd: int | None = None
        snapshot_path: Path | None = None
        try:
            if not stat.S_ISREG(os.fstat(source_fd).st_mode):
                raise EvaluationError(f"candidate is not a regular file: {candidate}")

            snapshot_fd, snapshot_name = tempfile.mkstemp(prefix="eudaimon-candidate-")
            snapshot_path = Path(snapshot_name)
            digest = hashlib.sha256()
            byte_count = 0

            with os.fdopen(source_fd, "rb") as source:
                source_fd = -1
                with os.fdopen(snapshot_fd, "wb") as snapshot:
                    snapshot_fd = None
                    for chunk in iter(lambda: source.read(1024 * 1024), b""):
                        snapshot.write(chunk)
                        digest.update(chunk)
                        byte_count += len(chunk)
                    snapshot.flush()
                    os.fsync(snapshot.fileno())
                    os.fchmod(snapshot.fileno(), 0o400)

            return snapshot_path, digest.hexdigest(), byte_count
        except Exception:
            if snapshot_path is not None:
                snapshot_path.unlink(missing_ok=True)
            raise
        finally:
            if source_fd >= 0:
                os.close(source_fd)
            if snapshot_fd is not None:
                os.close(snapshot_fd)

    @staticmethod
    def _terminate_evaluator_group(process: subprocess.Popen[bytes]) -> None:
        """Kill the isolated evaluator group; fail closed if cleanup is uncertain.

        Some macOS runners reject killpg despite allowing signals to the
        individual members of the evaluator's dedicated process group.
        """
        try:
            os.killpg(process.pid, signal.SIGKILL)
            return
        except ProcessLookupError:
            return
        except PermissionError:
            try:
                listing = subprocess.run(
                    ["ps", "-e", "-o", "pid=", "-o", "pgid="],
                    capture_output=True, text=True, check=True, timeout=5,
                )
            except (OSError, subprocess.SubprocessError) as exc:
                raise EvaluationError(
                    "cannot enumerate evaluator group after killpg permission denial"
                ) from exc

            members = []
            for line in listing.stdout.splitlines():
                fields = line.split()
                if len(fields) != 2:
                    raise EvaluationError("malformed evaluator process-group listing")
                try:
                    pid, pgid = map(int, fields)
                except ValueError as exc:
                    raise EvaluationError("malformed evaluator process-group listing") from exc
                if pgid == process.pid:
                    members.append(pid)

            if not members and process.poll() is None:
                raise EvaluationError("cannot locate live evaluator group after killpg permission denial")
            for pid in members:
                try:
                    os.kill(pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                except OSError as exc:
                    raise EvaluationError(f"cannot terminate evaluator group member {pid}") from exc
        except OSError as exc:
            raise EvaluationError("cannot terminate evaluator process group") from exc

    def _evaluate(self, candidate: Path) -> dict[str, Any]:
        # Recheck immediately before each spawn; the campaign is not race-proof.
        self._validate_evaluator_trust()
        self._validate_candidate_path(candidate)
        snapshot, candidate_sha256, candidate_bytes = self._create_evaluation_snapshot(candidate)
        if self.config.evaluator_backend == "docker-strict":
            try:
                return self._evaluate_docker(snapshot, candidate_sha256, candidate_bytes)
            finally:
                snapshot.unlink(missing_ok=True)
        try:
            command = [
                sys.executable,
                "-I", "-B",  # no campaign-local import search path or bytecode writes
                str(self.evaluator),
                "--candidate",
                str(snapshot),
            ]
            started = time.monotonic()
            # Temporary files avoid subprocess.PIPE's unbounded in-memory
            # capture. RLIMIT_FSIZE bounds each stream on supported POSIX
            # systems. A separate process group permits descendant cleanup.
            def limit_output() -> None:
                resource.setrlimit(resource.RLIMIT_FSIZE,
                                   (MAX_EVALUATOR_OUTPUT_BYTES, MAX_EVALUATOR_OUTPUT_BYTES))

            with tempfile.TemporaryFile(mode="w+b") as stdout_file, tempfile.TemporaryFile(mode="w+b") as stderr_file:
                try:
                    process = subprocess.Popen(
                        command, cwd=self.campaign, stdout=stdout_file,
                        stderr=stderr_file, start_new_session=True,
                        preexec_fn=limit_output,
                    )
                except OSError as exc:
                    raise EvaluationError("could not start evaluator with output limits") from exc
                timed_out = False
                try:
                    returncode = process.wait(timeout=self.config.evaluator_timeout)
                except subprocess.TimeoutExpired:
                    timed_out = True
                finally:
                    # An exited evaluator can leave background descendants.
                    # Do not accept its evidence unless group cleanup succeeds.
                    try:
                        self._terminate_evaluator_group(process)
                    finally:
                        if process.poll() is None:
                            try:
                                process.kill()
                            except ProcessLookupError:
                                pass
                            try:
                                process.wait(timeout=5)
                            except subprocess.TimeoutExpired as exc:
                                raise EvaluationError("evaluator did not exit after cleanup") from exc
                if timed_out:
                    raise EvaluationError(
                        f"evaluator timeout after {self.config.evaluator_timeout}s"
                    )
                stdout_file.seek(0, os.SEEK_END)
                stderr_file.seek(0, os.SEEK_END)
                stdout_size, stderr_size = stdout_file.tell(), stderr_file.tell()
                stdout_file.seek(0)
                stderr_file.seek(0)
                stdout_text = stdout_file.read(MAX_EVALUATOR_OUTPUT_BYTES + 1).decode("utf-8", errors="replace")
                stderr_text = stderr_file.read(MAX_EVALUATOR_OUTPUT_BYTES + 1).decode("utf-8", errors="replace")
                if stdout_size >= MAX_EVALUATOR_OUTPUT_BYTES or stderr_size >= MAX_EVALUATOR_OUTPUT_BYTES:
                    raise EvaluationError("evaluator output exceeded the bounded output limit")
            duration = time.monotonic() - started
            if returncode != 0:
                detail = (stderr_text or stdout_text).strip()
                raise EvaluationError(f"evaluator exited {returncode}: {detail[:500]}")
            lines = [line.strip() for line in stdout_text.splitlines() if line.strip()]
            if not lines:
                raise EvaluationError("evaluator produced no stdout")
            try:
                payload = json.loads(lines[-1])
            except json.JSONDecodeError as exc:
                raise EvaluationError("evaluator final stdout line is not JSON") from exc
            result = validate_evaluation(payload)
            result["candidate_sha256"] = candidate_sha256
            result["candidate_bytes"] = candidate_bytes
            result["duration_seconds"] = round(duration, 6)
            return result
        finally:
            snapshot.unlink(missing_ok=True)

    @staticmethod
    def _stage_docker_input(source: Path, destination: Path, expected_digest: str) -> None:
        """Stage only reviewed source bytes, not the campaign directory."""
        digest = hashlib.sha256()
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
        with os.fdopen(os.open(source, flags), "rb") as inp:
            if not stat.S_ISREG(os.fstat(inp.fileno()).st_mode):
                raise EvaluationError("docker input is not a regular file")
            with destination.open("xb") as out:
                for chunk in iter(lambda: inp.read(1024 * 1024), b""):
                    out.write(chunk)
                    digest.update(chunk)
                out.flush()
                os.fsync(out.fileno())
        if digest.hexdigest() != expected_digest:
            raise EvaluationError("reviewed docker input changed while staging")
        destination.chmod(0o400)

    def _evaluate_docker(
        self, snapshot: Path, candidate_sha256: str, candidate_bytes: int
    ) -> dict[str, Any]:
        """Opt-in, fail-closed container execution of the pinned reference policy.

        No implicit pulls, campaign mounts, host secrets, or trusted-local fallback.
        The Docker daemon and OCI image remain trusted dependencies.
        """
        docker = shutil.which("docker")
        if docker is None:
            raise EvaluationError("docker-strict unavailable: docker CLI not found")
        try:
            image = subprocess.run(
                [docker, "image", "inspect", DOCKER_IMAGE],
                capture_output=True, timeout=10, check=False,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            raise EvaluationError("docker-strict cannot verify pinned local image") from exc
        if image.returncode != 0:
            raise EvaluationError("docker-strict pinned image absent; no automatic pull")
        # Never accept a custom evaluator merely because it was self-pinned.
        if self.config.trusted_evaluator_sha256 not in (
            None, TRUSTED_REFERENCE_EVALUATOR_SHA256
        ):
            raise EvaluationError("docker-strict requires reviewed reference evaluator")

        container = "eudaimon-strict-" + uuid.uuid4().hex
        created = False
        started = time.monotonic()
        with tempfile.TemporaryDirectory(prefix="eudaimon-docker-inputs-") as tmp:
            stage = Path(tmp)
            adapter = stage / "eval_runner.py"
            policy = stage / "rr_policy.py"
            self._stage_docker_input(
                self.evaluator, adapter, TRUSTED_REFERENCE_EVALUATOR_SHA256
            )
            self._stage_docker_input(
                self.campaign / "rr_policy.py", policy, TRUSTED_REFERENCE_POLICY_SHA256
            )
            # The candidate is a per-evaluation, fsynced, mode-0400 snapshot.
            # Matching the host UID/GID permits read access to exact bind mounts
            # without making candidate contents world-readable on the host.
            mounts = [
                (adapter, "/eval_runner.py"),
                (policy, "/rr_policy.py"),
                (snapshot, "/candidate.md"),
            ]
            command = [
                docker, "create", "--pull=never", "--name", container,
                "--label", "org.eudaimon.backend=docker-strict",
                "--network", "none", "--read-only",
                "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
                "--pids-limit", "32", "--memory", "256m", "--cpus", "1",
                "--user", f"{os.getuid()}:{os.getgid()}",
                "--workdir", "/", "--tmpfs", "/tmp:rw,nosuid,nodev,size=16m",
                "--entrypoint", "python3",
            ]
            for host_path, container_path in mounts:
                command.extend([
                    "--mount",
                    f"type=bind,src={host_path},dst={container_path},readonly",
                ])
            command.extend([
                DOCKER_IMAGE, "-I", "-B", "/eval_runner.py",
                "--candidate", "/candidate.md",
            ])
            try:
                try:
                    creation = subprocess.run(
                        command, capture_output=True, text=True,
                        check=False, timeout=15,
                    )
                except (OSError, subprocess.SubprocessError) as exc:
                    raise EvaluationError("docker-strict container creation failed") from exc
                if creation.returncode != 0:
                    raise EvaluationError(
                        "docker-strict container creation refused: "
                        + creation.stderr.strip()[:400]
                    )
                created = True
                if not (
                    len(creation.stdout.strip()) == 64
                    and all(c in "0123456789abcdef" for c in creation.stdout.strip())
                ):
                    raise EvaluationError("docker-strict invalid container identity")
                def limit_output() -> None:
                    resource.setrlimit(
                        resource.RLIMIT_FSIZE,
                        (MAX_EVALUATOR_OUTPUT_BYTES, MAX_EVALUATOR_OUTPUT_BYTES),
                    )

                with tempfile.TemporaryFile(mode="w+b") as stdout, tempfile.TemporaryFile(mode="w+b") as stderr:
                    try:
                        process = subprocess.Popen(
                            [docker, "start", "-a", container],
                            stdout=stdout, stderr=stderr,
                            start_new_session=True, preexec_fn=limit_output,
                        )
                    except OSError as exc:
                        raise EvaluationError("docker-strict cannot attach evaluator") from exc
                    timed_out = False
                    try:
                        try:
                            cli_exit = process.wait(timeout=self.config.evaluator_timeout)
                        except subprocess.TimeoutExpired:
                            timed_out = True
                            cli_exit = -1
                    finally:
                        try:
                            self._terminate_evaluator_group(process)
                        finally:
                            if process.poll() is None:
                                process.kill()
                                process.wait(timeout=5)
                    if timed_out:
                        raise EvaluationError("docker-strict evaluator timeout")
                    if cli_exit != 0:
                        raise EvaluationError("docker-strict evaluator attach failed")
                    stdout.seek(0, os.SEEK_END)
                    stderr.seek(0, os.SEEK_END)
                    if (
                        stdout.tell() >= MAX_EVALUATOR_OUTPUT_BYTES
                        or stderr.tell() >= MAX_EVALUATOR_OUTPUT_BYTES
                    ):
                        raise EvaluationError("docker-strict evaluator output exceeded limit")
                    stdout.seek(0)
                    stderr.seek(0)
                    output = stdout.read(MAX_EVALUATOR_OUTPUT_BYTES + 1).decode(
                        "utf-8", errors="replace"
                    )
                try:
                    inspection = subprocess.run(
                        [docker, "inspect", "--format", "{{json .State}}", container],
                        capture_output=True, text=True, timeout=10, check=False,
                    )
                    state = json.loads(inspection.stdout) if inspection.returncode == 0 else {}
                except (OSError, subprocess.SubprocessError, ValueError) as exc:
                    raise EvaluationError("docker-strict cannot inspect evaluator exit") from exc
                if (
                    state.get("Status") != "exited"
                    or state.get("Running") is not False
                    or state.get("ExitCode") != 0
                ):
                    raise EvaluationError("docker-strict evaluator exited unsuccessfully")
                lines = [line.strip() for line in output.splitlines() if line.strip()]
                if not lines:
                    raise EvaluationError("docker-strict evaluator produced no output")
                try:
                    payload = json.loads(lines[-1])
                except json.JSONDecodeError as exc:
                    raise EvaluationError("docker-strict evaluator output is not JSON") from exc
                result = validate_evaluation(payload)
                result["candidate_sha256"] = candidate_sha256
                result["candidate_bytes"] = candidate_bytes
                result["duration_seconds"] = round(time.monotonic() - started, 6)
                result["evaluator_backend"] = "docker-strict"
                result["image_digest"] = DOCKER_IMAGE.split("@", 1)[1]
                return result
            finally:
                # A killed Docker CLI can leave a container alive. Removal and
                # verification are mandatory, even after failed start/timeout.
                try:
                    removal = subprocess.run(
                        [docker, "rm", "-f", container],
                        capture_output=True, text=True, timeout=15, check=False,
                    )
                    probe = subprocess.run(
                        [docker, "inspect", container],
                        capture_output=True, text=True, timeout=10, check=False,
                    )
                except (OSError, subprocess.SubprocessError) as exc:
                    raise EvaluationError(
                        "docker-strict cleanup unverified; container may remain"
                    ) from exc
                absent = (
                    probe.returncode != 0
                    and ("No such object" in probe.stderr or "No such container" in probe.stderr)
                )
                if created and (removal.returncode != 0 or not absent):
                    raise EvaluationError(
                        "docker-strict cleanup failed or unverified; container may remain"
                    )

    def _fsync_directory(self, directory: Path, *, required: bool = False) -> None:
        try:
            fd = os.open(directory, os.O_RDONLY)
            try:
                os.fsync(fd)
            finally:
                os.close(fd)
        except OSError as exc:
            if required:
                raise EngineError(f"cannot durably synchronize directory: {directory}") from exc
            # Post-replace fsync is best effort on filesystems that reject it.

    def _promote(self, candidate: Path, expected_sha256: str, expected_old_sha256: str) -> None:
        source_mode = stat.S_IMODE(self.target.stat().st_mode)
        fd, temp_name = tempfile.mkstemp(prefix=f".{self.target.name}.", dir=self.target.parent)
        temp_path = Path(temp_name)
        digest = hashlib.sha256()
        try:
            with os.fdopen(fd, "wb") as output, candidate.open("rb") as source:
                for chunk in iter(lambda: source.read(1024 * 1024), b""):
                    output.write(chunk)
                    digest.update(chunk)
                output.flush()
                os.fsync(output.fileno())
            if digest.hexdigest() != expected_sha256:
                raise EngineError("candidate bytes changed after evaluation; promotion refused")
            if sha256_file(self.target) != expected_old_sha256:
                raise EngineError("incumbent target changed after promotion intent; promotion refused")
            os.chmod(temp_path, source_mode)
            os.replace(temp_path, self.target)
            self._fsync_directory(self.target.parent)
            if sha256_file(self.target) != expected_sha256:
                raise EngineError("promoted target digest does not match evaluated candidate")
        finally:
            temp_path.unlink(missing_ok=True)

    def _pending_promotion_transactions(self) -> dict[str, dict[str, Any]]:
        pending: dict[str, dict[str, Any]] = {}
        seen_transaction_ids: set[str] = set()
        if not self.ledger.exists():
            return pending
        try:
            raw = self.ledger.read_bytes()
            if raw and not raw.endswith(b"\n"):
                raise EngineError("partial ledger final line; operator review required")
            lines = raw.decode("utf-8").splitlines()
        except (OSError, UnicodeError) as exc:
            raise EngineError(f"cannot read promotion ledger: {exc}") from exc
        for line_number, line in enumerate(lines, 1):
            if not line.strip():
                raise EngineError(f"blank ledger line at {line_number}; recovery requires operator review")
            def unique_members(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
                record: dict[str, Any] = {}
                for key, value in pairs:
                    if key in record:
                        raise ValueError(f"duplicate ledger member: {key}")
                    record[key] = value
                return record

            def forbid_nonfinite(token: str) -> None:
                raise ValueError(f"non-finite ledger token: {token}")

            try:
                event = json.loads(line, object_pairs_hook=unique_members, parse_constant=forbid_nonfinite)
            except (json.JSONDecodeError, ValueError) as exc:
                raise EngineError(f"malformed ledger line {line_number}; recovery requires operator review") from exc
            if not isinstance(event, dict) or not isinstance(event.get("event"), str):
                raise EngineError(f"invalid ledger event at line {line_number}")
            if event["event"] not in ("baseline", "candidate", "evaluation_error", "halt", "promotion_intent", "promotion_commit", "promotion_recovered_commit", "promotion_recovered_abort"):
                raise EngineError(f"unknown ledger event at line {line_number}; operator review required")
            transaction_id = event.get("transaction_id")
            event_type = event.get("event")
            if event_type == "promotion_intent":
                if not isinstance(transaction_id, str) or not transaction_id or transaction_id in seen_transaction_ids:
                    raise EngineError(f"invalid or reused promotion transaction ID at ledger line {line_number}")
                seen_transaction_ids.add(transaction_id)
                for field in ("old_target_sha256", "candidate_sha256"):
                    value = event.get(field)
                    if not isinstance(value, str) or len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
                        raise EngineError(f"invalid {field} in promotion transaction {transaction_id}")
                pending[transaction_id] = event
            elif event_type in ("promotion_commit", "promotion_recovered_commit", "promotion_recovered_abort"):
                if not isinstance(transaction_id, str) or transaction_id not in pending:
                    raise EngineError(f"promotion outcome without intent at ledger line {line_number}")
                intent = pending[transaction_id]
                if event.get("run_id") != intent.get("run_id"):
                    raise EngineError(f"promotion outcome run mismatch at ledger line {line_number}")
                field = "target_sha256" if event_type == "promotion_commit" else "recovered_target_sha256"
                expected = intent["old_target_sha256"] if event_type == "promotion_recovered_abort" else intent["candidate_sha256"]
                if event.get(field) != expected:
                    raise EngineError(f"promotion outcome digest mismatch at ledger line {line_number}")
                del pending[transaction_id]
        return pending

    def _recover_incomplete_promotions(self) -> None:
        for transaction_id, intent in self._pending_promotion_transactions().items():
            old_digest = intent["old_target_sha256"]
            candidate_digest = intent["candidate_sha256"]
            if old_digest == candidate_digest:
                raise EngineError(f"promotion transaction {transaction_id} is ambiguous; operator review required")
            # The intent must identify the exact configured target. Older
            # target-less pending intents cannot safely be recovered automatically.
            if intent.get("target") != self.config.target:
                raise EngineError(
                    f"promotion transaction {transaction_id} target identity missing or mismatched; operator review required"
                )
            current_digest = sha256_file(self.target)
            common = {
                "event": "promotion_recovered_commit" if current_digest == candidate_digest else "promotion_recovered_abort",
                "transaction_id": transaction_id,
                "run_id": intent.get("run_id"),
                "timestamp": utc_now(),
                "recovered_target_sha256": current_digest,
            }
            if current_digest == candidate_digest:
                self._append_ledger(common)
            elif current_digest == old_digest:
                self._append_ledger(common)
            else:
                raise EngineError(
                    f"promotion transaction {transaction_id} target digest matches neither old nor candidate; operator review required"
                )

    def _proposal_files(self) -> list[Path]:
        self._validate_path_components(self.proposals, self.campaign, "proposals directory", "directory")
        return sorted(
            (
                path
                for path in self.proposals.iterdir()
                if path.is_file() and not path.is_symlink() and not path.name.startswith(".")
            ),
            key=lambda path: path.name,
        )

    def _halt(
        self,
        run_id: str,
        state: dict[str, Any],
        reason: str,
        exit_code: int,
    ) -> RunResult:
        state.update({"status": "halted", "halt_reason": reason, "finished_at": utc_now()})
        self._append_ledger(
            {
                "event": "halt",
                "run_id": run_id,
                "timestamp": utc_now(),
                "reason": reason,
                "state": state,
            }
        )
        self._write_state(state)
        return RunResult(
            run_id=run_id,
            status="halted",
            reason=reason,
            iterations=int(state["iterations"]),
            promoted=int(state["promoted"]),
            exit_code=exit_code,
        )

    def run(self) -> RunResult:
        self._validate_campaign()
        self._ensure_state_dir()
        run_id = uuid.uuid4().hex
        lock = RunLock(self.state_dir / "run.lock", run_id)
        lock.acquire()
        try:
            # Recovery precedes every new evaluation and is ledger-driven, not state-driven.
            self._recover_incomplete_promotions()
            state: dict[str, Any] = {
                "engine_version": ENGINE_VERSION,
                "run_id": run_id,
                "campaign": str(self.campaign),
                "target": self.config.target,
                "status": "running",
                "started_at": utc_now(),
                "iterations": 0,
                "promoted": 0,
            }
            self._write_state(state)
            try:
                baseline = self._evaluate(self.target)
            except EngineError as exc:
                state["error"] = str(exc)
                self._append_ledger(
                    {"event": "evaluation_error", "run_id": run_id, "candidate": self.config.target, "error": str(exc), "timestamp": utc_now()}
                )
                return self._halt(run_id, state, "baseline_evaluation_error", 2)
            state["best"] = {"candidate": self.config.target, "evaluation": baseline}
            self._append_ledger(
                {"event": "baseline", "run_id": run_id, "candidate": self.config.target, "evaluation": baseline, "timestamp": utc_now()}
            )
            self._write_state(state)
            if not baseline["protect_pass"]:
                return self._halt(run_id, state, "baseline_protect_failed", 3)

            best = baseline
            no_improvement = 0
            proposals = self._proposal_files()
            if not proposals:
                return self._halt(run_id, state, "no_proposals", 0)

            for candidate in proposals:
                if state["iterations"] >= self.config.max_iterations:
                    return self._halt(run_id, state, "iteration_limit", 0)
                state["iterations"] += 1
                try:
                    evaluation = self._evaluate(candidate)
                except EngineError as exc:
                    state["error"] = str(exc)
                    self._append_ledger(
                        {"event": "evaluation_error", "run_id": run_id, "iteration": state["iterations"], "candidate": candidate.name, "error": str(exc), "timestamp": utc_now()}
                    )
                    return self._halt(run_id, state, "candidate_evaluation_error", 2)

                improved = lexicographically_better(evaluation, best)
                event: dict[str, Any] = {
                    "event": "candidate",
                    "run_id": run_id,
                    "iteration": state["iterations"],
                    "candidate": candidate.name,
                    "evaluation": evaluation,
                    "decision": "rejected",
                    "timestamp": utc_now(),
                }
                if improved:
                    # The score comparison is valid only for the incumbent bytes
                    # that were evaluated, not a target changed in the meantime.
                    if sha256_file(self.target) != best["candidate_sha256"]:
                        return self._halt(run_id, state, "incumbent_changed_since_evaluation", 2)
                    transaction_id = uuid.uuid4().hex
                    old_digest = best["candidate_sha256"]
                    intent = {
                        "event": "promotion_intent",
                        "transaction_id": transaction_id,
                        "run_id": run_id,
                        "candidate": candidate.name,
                        "target": self.config.target,
                        "old_target_sha256": old_digest,
                        "candidate_sha256": evaluation["candidate_sha256"],
                        "phase": "intent_durable",
                        "timestamp": utc_now(),
                    }
                    self._append_ledger(intent)
                    self._promote(candidate, evaluation["candidate_sha256"], old_digest)
                    promoted_digest = sha256_file(self.target)
                    if promoted_digest != evaluation["candidate_sha256"]:
                        raise EngineError(f"promotion transaction {transaction_id} failed post-replace verification")
                    self._append_ledger({
                        "event": "promotion_commit",
                        "transaction_id": transaction_id,
                        "run_id": run_id,
                        "target_sha256": promoted_digest,
                        "timestamp": utc_now(),
                    })
                    best = evaluation
                    no_improvement = 0
                    state["promoted"] += 1
                    state["best"] = {"candidate": candidate.name, "evaluation": evaluation}
                    event["decision"] = "promoted"
                    event["transaction_id"] = transaction_id
                else:
                    no_improvement += 1
                state["no_improvement"] = no_improvement
                self._append_ledger(event)
                self._write_state(state)
                if not evaluation["protect_pass"]:
                    return self._halt(run_id, state, "candidate_protect_failed", 3)
                if no_improvement >= self.config.max_no_improvement:
                    return self._halt(run_id, state, "no_improvement_limit", 0)

            return self._halt(run_id, state, "proposal_exhausted", 0)
        finally:
            lock.release()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("campaign", type=Path)
    parser.add_argument("--target", default=DEFAULT_TARGET)
    parser.add_argument("--max-iterations", type=int, default=DEFAULT_MAX_ITERATIONS)
    parser.add_argument("--max-no-improvement", type=int, default=DEFAULT_MAX_NO_IMPROVEMENT)
    parser.add_argument("--evaluator-timeout", type=float, default=DEFAULT_EVALUATOR_TIMEOUT)
    parser.add_argument(
        "--evaluator-backend", choices=("trusted-local", "docker-strict"),
        default=DEFAULT_EVALUATOR_BACKEND,
        help="trusted-local is not sandboxed; docker-strict requires a preinstalled pinned image",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config = EngineConfig(
        campaign=args.campaign,
        target=args.target,
        max_iterations=args.max_iterations,
        max_no_improvement=args.max_no_improvement,
        evaluator_timeout=args.evaluator_timeout,
        evaluator_backend=args.evaluator_backend,
    )
    try:
        result = CampaignEngine(config).run()
    except EngineError as exc:
        print(json.dumps({"status": "blocked", "error": str(exc)}), file=sys.stderr)
        return 2
    print(json.dumps(result.__dict__, sort_keys=True))
    return result.exit_code


if __name__ == "__main__":
    raise SystemExit(main())