# Amendment A-001 — Guard Before Reset (AutoResearch-W)

**Version:** A-001 v1.0  
**Approved:** 2026-11-19, by project owner in the active project conversation  
**Status:** APPROVED CONCEPTUAL AMENDMENT — NOT YET IMPLEMENTED IN A PROPOSER HARNESS  
**Scope:** AutoResearch-W conceptual proposer/guard workflow  
**Supersedes only:** the *ordering* of output validation/reset and protected-file guard checks in the algorithm under `spec/conceptual/3-autoresearch-w.md`  
**Original source:** public repository commit `9c464796a68ca19e565c7bdd5f764691a78616a4` (immutable historical snapshot).

## Normative requirement

The protected-file guard **MUST run immediately after the proposer harness
returns and before any validation-driven reset, discard, rollback, or
candidate promotion** that could modify the workspace or erase evidence.

1. Capture the authorized protected-file baseline and scope **before** the
   proposer harness runs.
2. Run the harness and preserve its raw output and post-harness workspace
   long enough to perform the guard.
3. Run the guard on that unmodified post-harness state **before** interpreting
   invalid output as a reason to reset/discard.
4. On a guard breach, inability to check, or ambiguous state: record the
   terminal guard failure and bounded forensic evidence, **halt without
   reset or promotion**.
5. Only on a clean guard result: validate the harness output.
6. On malformed output after a clean guard: record invalid output and
   perform only the authorized target reset/discard, without modifying
   protected files.
7. On valid output after a clean guard: continue with pending evidence,
   independent trusted evaluation, Protect Gate, engine decision and durable
   promotion transaction. Recheck guard/target invariants before promotion.

A malformed harness response **MUST NOT** suppress the guard check.
A valid response **MUST NOT** override a guard breach.

## Required adversarial tests before implementation

- Malformed output **plus** protected-file modification: halt before reset;
  preserve evidence.
- Valid output **plus** protected-file modification: halt before evaluation.
- Guard unavailable, unreadable, or symlink-swapped protected path: fail closed.
- Unauthorized new/deleted file: guard detects scope change.
- Malformed output with a clean guard: authorized target reset only.
- Valid output with a clean guard: normal evaluation and Protect Gate.
- Post-evaluation target change: refuse promotion and preserve evidence.

## Scope and provenance

This amendment is an **additive normative overlay**, not an edit to the
historical blueprint. The original files under `spec/conceptual/` and
their `SOURCE_MANIFEST.json` SHA-256 digests **MUST remain unchanged**.
For the conflicting step ordering, this amendment takes precedence over the
historical snapshot; all other conceptual requirements remain intact.

The current `engine/` reference implementation **does not run a proposer
harness**. It consumes existing proposal files. Therefore this amendment
does **not** certify an existing harness or authorize autonomous code
modification. Future proposer-harness implementation requires a separate
reviewed PR and synthetic adversarial tests.

**Design discussion:** `docs/11-guard-order-amendment-proposal.md` and
GitHub issue #4.
