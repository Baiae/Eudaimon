# Eudaimon — Proposed Conceptual Guard-Order Amendment

**Status: PROPOSED AMENDMENT — NOT ADOPTED OR IMPLEMENTED.**
**Date:** 2026-11-19.
**Applies to:** canonical conceptual AutoResearch-W blueprint, specifically
`spec/conceptual/3-autoresearch-w.md` (historical snapshot).
**Does not apply to:** a currently running autonomous proposer harness; the
reference engine consumes existing proposal files and has no such harness.

## 1. Problem

The preserved conceptual algorithm orders these steps:

1. Execute the proposing harness.
2. Validate its output; if invalid, reset/discard.
3. Write pending evidence.
4. Perform the guard check and halt on breach.

This can erase or alter evidence of an out-of-scope file modification before
the guard checks it. An adversarial harness could simultaneously modify a
protected file and return malformed output, triggering an early reset.

**Invariant:** no operation that repairs, resets, or discards harness effects
may run before the guard has checked the post-harness workspace against the
pre-harness protected baseline.

## 2. Proposed revised sequence

1. Before harness execution, capture the authorized baseline and the set of
   protected paths, including unexpected new files and symlink changes.
2. Run the harness under its approved execution boundary and collect its
   raw output and exit status without resetting or accepting any changes.
3. **Immediately run the guard** over the unmodified post-harness workspace.
   If the guard cannot complete, treat the result as a breach.
4. On breach, preserve bounded forensic metadata, record a terminal guard
   failure, and halt. No score, candidate promotion, or automatic reset is
   permitted before the evidence is preserved and the guard outcome recorded.
5. Only after a clean guard result, validate the harness output schema,
   proposal tags and required fields.
6. On malformed output, record the invalid-output outcome; then perform only
   the explicitly authorized discard/reset of the mutable target. Never
   reset or overwrite protected files as part of normal recovery.
7. On valid output, write the pending evaluation record and continue through
   trusted evaluation, Protect Gate, decision, promotion and durable ledger
   operations. Preserve existing independent evaluator/engine authority.
8. Before promotion, recheck the relevant target identity/digest and guard
   invariants. Any ambiguity halts the campaign.

The specific names, persistence format and rollback mechanism must be
reconciled with the *conceptual* Git-ratchet/TSV design. The current reference
engine's JSONL/single-target mechanism is **not** silently substituted.

## 3. Acceptance tests for a future harness implementation

- **Malformed output + protected-file edit:** guard breach is recorded and
  the run halts before any reset; protected-file evidence is preserved.
- **Malformed output only:** guard passes; invalid output is recorded and
  only the authorized mutable target may be reset.
- **Valid output + protected-file edit:** guard breach takes precedence over
  valid output, score and promotion.
- **Guard unavailable / unreadable path / symlink swap:** fail closed; no
  automatic reset or promotion.
- **Valid output + clean guard:** normal evaluation and Protect Gate continue.
- **Out-of-scope new file / deletion:** guard detects the unauthorized change.
- **Post-evaluation target race:** digest and target identity are rechecked.
- **Audit:** terminal events are durable and distinguish breach, invalid
  output, evaluation failure and accepted promotion.

Tests must use synthetic workspaces and must not modify historical evidence.

## 4. Provenance and approval protocol

The historical files under `spec/conceptual/` are byte-for-byte preserved
from public commit `9c464796a68ca19e565c7bdd5f764691a78616a4`,
with hashes in `SOURCE_MANIFEST.json`. They remain the original canonical
snapshot. **Do not edit these files in place or regenerate the manifest to
conceal a historical change.**

If the owner approves this amendment:

1. Add a separately versioned, dated amendment under
   `spec/amendments/`, explicitly referencing the original source file
   and commit; retain the original snapshot and manifest unchanged.
2. Record the approval and effective version in the architectural authority
   index, distinguishing the new normative amendment from the historical
   source.
3. Review the proposed guard ordering against the conceptual Git-ratchet
   workflow and security requirements before implementation.
4. Implement the proposer harness and its guard only in a **separate** PR,
   with the adversarial tests above and explicit sign-off.

**Decision D7 (open):** Approve this guard-first conceptual amendment and
the additive versioning protocol. Until then, this document is a proposal,
not a change to the authoritative blueprint.
