# Docker strict backend — internal adversarial review

Date: 2026-11-20. Scope: draft PR #5 and synthetic reference evaluator.
Disposition: HOLD draft; not an independent third-party security assessment.

## Finding D6-R1 — cleanup integrity

A Docker create call can fail or time out after the daemon allocates a
container but before the client receives a successful response. Previously,
the engine attempted removal and inspection but required verified absence
only after an acknowledged successful creation. If creation failed and the
daemon was unavailable during cleanup, it could report only the original
creation error without highlighting the possible leftover container.
No evaluation evidence was accepted in this scenario, but the cleanup
guarantee was overstated.

Fix: require verified container absence even when creation was not
acknowledged. Retain the successful-removal requirement after acknowledged
creation. Added a regression test for failed create plus failed cleanup,
requiring a cleanup error, attempted removal and no accepted baseline.

Local stdlib suite: 106 tests, 105 passed and one intentional skip.
Linux Docker CI must be checked on the new commit before approval.

## Remaining release gates

- Real pinned-image Docker Desktop tests on Apple Silicon, including
  UID/GID bind mounts, confinement, cleanup and promotion.
- Synthetic daemon-interruption and resource-exhaustion testing.
- Review same-user mutation races, local daemon/socket trust and CLI context.
- Independent security review and explicit D6-C production decision.
- Preserve canonical conceptual files and private campaign evidence.

This is an internal review, NOT independent security approval.
