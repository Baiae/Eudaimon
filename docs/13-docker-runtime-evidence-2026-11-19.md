# Docker strict evaluator — reproducible runtime evidence

**Evidence date:** 2026-11-19 (US Pacific; CI timestamps may be UTC 2026-11-20)  
**Branch:** `feature/eudaimon-docker-strict-2026-11-19`  
**Validated commit:** `db11d2c6c3d5473f35f793c22f8e11d92358430a`  
**Scope:** synthetic public reference campaign only; no historical/private campaign data.

## Verified on Linux

- **Docker integration CI:** https://github.com/Baiae/Eudaimon/actions/runs/44658402462
- **Reference stdlib CI (Ubuntu + macOS):** https://github.com/Baiae/Eudaimon/actions/runs/44658402403
- Linux Docker Engine 29.4.2, x86_64; Python 3.12.12 slim-bookworm image fetched by exact multi-platform index digest `sha256:593bd06efe90efa80dc4eee3948be7c0fde4134606dd40d8dd8dbcade98e669c`.
- **4/4 real Docker integration tests PASS:** pinned evaluator baseline, Protect Gate failure without promotion, safe promotion with transaction evidence, and synthetic host-file/network/root-write confinement.
- Synthetic confinement test inspects actual Docker HostConfig and mount state: read-only root and exact file mounts, no network, dropped capabilities, no-new-privileges, non-root UID, 256 MiB memory, 1 CPU, 32-process limit. It attempts and fails synthetic host-secret access, host-root write, candidate overwrite, and outbound network connection.
- Container cleanup check confirms no synthetic Eudaimon containers remain.
- **103 stdlib tests:** 102 pass, one intentional skip for unavailable private historical evidence; both Ubuntu and macOS CI jobs PASS.

## Defect discovered and corrected by actual runtime tests

The first real Linux integration run (https://github.com/Baiae/Eudaimon/actions/runs/44658204743) revealed a cleanup-verification incompatibility: Docker 29 emits lowercase `error: no such object`, whereas the implementation initially recognized only `No such object`. This caused a **fail-closed baseline evaluation error**, not an unsafe promotion. The code now casefolds the Docker error while still requiring a specific not-found response; the synthetic test also checks the normalized wording. The correction passed subsequent Docker CI.

## Mac validation status

**Not yet verified.** Docker Desktop 29.9.3 is present on Apple Silicon, and the registry confirms the exact multi-platform index digest. The normal Docker image pull stalled. A direct, digest-verifying image retrieval was attempted to diagnose the network issue, but successful image installation and macOS Docker execution were **not** established by the Linux CI results. Do not claim macOS Docker containment based solely on macOS stdlib tests.

## Remaining release gates

1. Complete Apple Silicon Docker Desktop runtime tests with the exact pinned image, including file mounts, host-file/network confinement, cleanup and promotion.
2. Run adversarial runtime probes for timeouts, descendants, Docker daemon interruption and resource exhaustion.
3. Obtain independent security review of Docker daemon/image trust, host UID mapping and TOCTOU assumptions.
4. Explicitly approve production security posture and merge PR #5. Until then, the PR remains **draft**.

**Interpretation:** Linux synthetic integration evidence is positive; it is not a proof of sandbox security, protection against kernel/daemon compromise, or production approval.
