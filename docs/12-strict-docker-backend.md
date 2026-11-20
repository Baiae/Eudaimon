# Optional strict Docker evaluator — implementation contract

**Status:** experimental, opt-in. Requires the pinned image installed locally.
**Approved direction:** D6-A, 2026-11-19. No automatic fallback or image pull.
**Threat model:** reviewed evaluator and policy, synthetic candidate snapshots; not
a general-purpose sandbox for arbitrary malicious code.

## Use

The default remains the existing trusted-local reference evaluator, which is
**not sandboxed**:

    python3 engine/engine.py campaigns/rr_engine

Opt into Docker isolation with:

    python3 engine/engine.py campaigns/rr_engine --evaluator-backend docker-strict

Strict mode refuses execution if Docker is missing, the pinned image is absent,
or the evaluator/policy source pins fail. The CLI never auto-pulls images.
The reviewed Python image is:

    docker.io/library/python@sha256:593bd06efe90efa80dc4eee3948be7c0fde4134606dd40d8dd8dbcade98e669c

This is the official Python 3.12.12 slim-bookworm multi-platform index digest
observed via Docker buildx imagetools inspect on 2026-11-19. An OCI digest
pins image contents but is **not** an independent supply-chain attestation.
Only an operator should pull this exact digest after reviewing the image
provenance and local Docker daemon configuration. Example:

    docker pull docker.io/library/python@sha256:593bd06efe90efa80dc4eee3948be7c0fde4134606dd40d8dd8dbcade98e669c

The engine itself never issues docker pull.

## Isolation and trust

The engine first rejects DOCKER_HOST overrides and Docker contexts whose
endpoint is not a local Unix socket. This prevents accidentally interpreting
local candidate bind paths on a remote Docker daemon. It then checks the exact
image digest locally and starts a fresh container with pull=never, network=none,
a read-only root filesystem,
all Linux capabilities dropped, no-new-privileges, a non-root numeric UID/GID,
a 32-process limit, 256 MiB memory limit, one CPU, and a bounded scratch
tmpfs. It bind-mounts **only three exact read-only files**:

- the copied, independently SHA-256-pinned evaluator adapter;
- the copied, independently SHA-256-pinned policy module;
- the candidate's temporary, fsynced, read-only snapshot.

No campaign directory, ledger, home directory, Docker socket, network
namespace or host secrets are mounted. The container uses a dedicated
identity and is forcibly removed after evaluation; cleanup is verified
before its output is accepted. The host validates JSON, the Protect Gate,
candidate digests and transaction invariants as before.

Only the bundled reviewed evaluator/policy are supported in strict mode.
Custom evaluator pins are rejected even when programmatically approved.
The legacy trusted-local backend remains available explicitly, unchanged.

## Tests

Standard library unit tests (no Docker required):

    python3 -B -m unittest discover -s tests -v

Explicit opt-in Docker integration tests (require the pinned image):

    python3 -B -m unittest discover -s tests_docker -v

Integration tests use synthetic campaign files and temporary containers only.
They must not read or modify historical campaign evidence.

## Limitations

This is a **defense-in-depth container boundary**, not a proof of safety
against hostile code, kernel/daemon exploits, container escapes, or
malicious same-user races. Docker Desktop on macOS runs a Linux VM; the
Linux backend uses the host kernel. The daemon, image and host filesystem
are trusted dependencies. A failed Docker daemon may leave a container
running even if the host engine refuses its evidence; an operator must
investigate cleanup errors. Rootless Docker, remote Docker hosts, and
unreviewed custom images/evaluators are not validated. Resource limits
and filesystem restrictions depend on the runtime platform.

Do not deploy as a production hostile-code execution service without
independent security review, cross-platform runtime tests, and an explicit
D6-C production acceptance decision.
