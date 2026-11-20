# Eudaimon — Evaluator Isolation Boundary: Design and Evidence

**Status: PROPOSED — NOT IMPLEMENTED; NO UNTRUSTED EXECUTION AUTHORIZED.**
**Date:** 2026-11-19. **Scope:** constrained reference engine only.
**Authority:** proposed D6 decision; does not amend the canonical `spec/conceptual/` snapshot.

## 1. Objective and existing guarantees

The current reference engine verifies SHA-256 pins on the reviewed evaluator
(and bundled policy), runs Python with `-I -B`, uses a candidate snapshot,
bounds stdout/stderr and execution time, and attempts process-group cleanup.
These are meaningful integrity and containment measures **but not a security
sandbox**. A malicious evaluator running with the host user's identity could
still read host files, access the network, and interact with host processes.
An integrity pin approves specific code; it does not isolate that code.

**Security objective for an opt-in strict mode:** evaluate only explicitly
approved code and candidate bytes without exposing the user's home directory,
credentials, host processes, network, campaign state, or writable target.
A failure to establish or verify the isolation boundary must prevent execution
and promotion, with an explicit terminal reason. Do not claim that the
resulting system is safe for arbitrary hostile code without independent review.

## 2. Evidence collected on the authorized Mac (synthetic probes only)

- macOS 26.6, arm64, Python 3.12; Docker client/server 29.9.3 available.
- `sandbox-exec` is installed. An `allow default` policy with explicit
  network/write denials blocked a localhost connection and an outside write
  (EPERM), **but allowed reading an outside synthetic secret**. This policy
  fails the confidentiality requirement.
- A more restrictive `deny default` profile with selected filesystem
  allowances did not start the synthetic Python probe (exit 134). A separate
  broad file-read `deny default` test did launch Python; broad read access
  is not an acceptable confidentiality boundary.
- A **Docker create/inspect-only** synthetic probe accepted and reported:
  `network=none`, read-only root filesystem, non-root user `65534:65534`,
  `cap-drop=ALL`, `no-new-privileges`, 32-process limit, 128 MiB memory
  limit, 1 CPU, and a read-only candidate bind mount. The container was
  removed; no image code or real campaign was executed.
- These checks establish *availability and configuration syntax only*.
  They **do not** establish runtime isolation, safe cleanup, or resistance
  to container escapes. No approved/pinned Python runtime image was selected.

## 3. Proposed execution boundary

**Recommended direction: opt-in Docker-backed strict evaluator execution,**
implemented in a separate code PR after D6 approval. Retain the existing
trusted-reference mode for backward compatibility, explicitly labeled
`trusted / not sandboxed`; do not change defaults silently.

Host engine:
1. Validate campaign, target, evaluator and policy paths and source pins.
2. Create a bounded, immutable-for-the-evaluation candidate snapshot.
3. Verify the **exact, reviewed OCI image digest** and runtime availability.
   No implicit image pull, tag-only trust, or image substitution.
4. Launch a short-lived container with only three read-only inputs: reviewed
   evaluator, its reviewed dependencies/policy, and candidate snapshot.
   **Never mount** the campaign root, home, SSH keys, Docker socket, state
   directory, ledger, or other host paths. A container-private scratch tmpfs
   may be writable, bounded, and `nosuid`.
5. Use `--network none`, `--read-only`, `--cap-drop ALL`,
   `--security-opt no-new-privileges`, an unprivileged numeric UID/GID,
   `--pids-limit`, `--memory`, `--cpus`, and a restrictive default
   seccomp profile. Do not grant host PID/network namespaces, privileged
   mode, devices, or additional capabilities.
6. Set a minimal, explicitly enumerated environment. No inherited
   credentials, tokens, proxy settings, or other host secrets.
7. Keep stdout/stderr bounded; validate the final JSON evidence exactly as
   the host engine already does. Record backend, image digest and policy
   version with each evaluation for auditability.
8. Identify the container by a unique engine-owned ID; on success, failure,
   cancellation, and timeout, forcibly remove it and verify cleanup.
   A killed Docker CLI process is **not** proof the container stopped.
9. Never fall back to unsandboxed execution when strict mode is requested.
   Missing Docker, unavailable pinned image, failed mount, denied cleanup,
   or ambiguous output must fail closed and block promotion.

**Caveat:** Docker's daemon and host-side CLI are privileged attack surfaces;
Linux containers share a kernel with their host, whereas Docker Desktop
typically uses a Linux VM on macOS. These mechanisms reduce exposure but
are not a proof of complete hostile-code containment. Pin and review the
runtime image, daemon configuration, and isolation policy before use.

## 4. Non-goals and prohibited shortcuts

- Do not present Python `-I`, resource limits, process groups,
  `sandbox-exec` allow-default, or a hash pin as complete sandboxing.
- Do not switch existing users to Docker without an explicit configuration
  change, or auto-pull an unreviewed image.
- Do not run real or private campaign evidence during isolation tests.
- Do not introduce a second orchestration service, long-running agent, or
  background daemon. Use the already installed Docker runtime if approved.
- Do not modify canonical conceptual source snapshots or the historical
  ledger while developing this boundary.

## 5. Required tests before any strict-mode merge

| Gate | Required observable result |
| --- | --- |
| Approved evaluator | Valid reviewed evaluator/policy and pinned image run on synthetic candidate. |
| No Docker or no image | Strict mode halts before evaluator execution; no fallback. |
| Tag substitution / image mismatch | Reject unless the exact approved digest matches. |
| File confidentiality | Synthetic secret outside explicit mounts is unreadable. |
| File integrity | Target, campaign state and host files remain unmodified by evaluator. |
| Network | TCP/UDP/DNS attempts fail; no host or external network access. |
| Privileges | Non-root UID, no added caps, no-new-privileges, no host PID namespace. |
| Resource limits | CPU, memory, process-count and output limits enforced. |
| Timeout / child processes | Container and descendants removed, even if CLI exits early. |
| Failure injection | Start, wait, inspect and remove failures halt; no promotion. |
| Evidence | JSON validation, Protect Gate, transaction integrity unchanged. |
| Platforms | Ubuntu and macOS CI pass; local macOS synthetic isolation probes pass. |
| Regression | Existing trusted-reference suite still passes with its documented limitation. |

All tests must use temporary synthetic files and containers, with cleanup
verified. CI can test fail-closed wiring without Docker, but a **real**
Docker integration test on each supported host is necessary before claiming
the strict backend works.

## 6. Stop/go decisions

- **D6-A (APPROVED 2026-11-19):** Docker is an optional strict evaluator
  backend. The default trusted-local backend remains unchanged.
- **D6-B (SELECTED FOR EXPERIMENTAL TESTING):** Official Python 3.12.12
  slim-bookworm multi-platform OCI index digest
  sha256:593bd06efe90efa80dc4eee3948be7c0fde4134606dd40d8dbcade98e669c.
  Digest is pinned, no auto-pulls. Independent supply-chain attestation,
  architecture-specific runtime tests and future update process remain
  required before production approval.
- **D6-C (IMPLEMENTATION AUTHORIZED 2026-11-19):** An opt-in, fail-closed
  strict backend may be implemented in a separate PR with the tests above.
  **Production security sign-off remains OPEN** until runtime gates pass.

**Current state:** the separate strict-backend implementation is experimental
and not production-approved. See docs/12-strict-docker-backend.md. The
canonical conceptual source and historical evidence remain unchanged.
