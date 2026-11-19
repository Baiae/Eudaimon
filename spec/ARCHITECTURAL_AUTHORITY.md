# Eudaimon — Architectural Authority Index

**Updated:** 2026-11-19

## Authority order

1. **Approved, versioned conceptual amendments** under `spec/amendments/`
   have normative precedence **only within their explicitly declared scope**.
   An amendment does not silently replace unrelated blueprint requirements.
2. **Historical canonical conceptual blueprint:** `spec/conceptual/`.
   Its files are preserved byte-for-byte from public commit
   `9c464796a68ca19e565c7bdd5f764691a78616a4` and authenticated
   by `spec/conceptual/SOURCE_MANIFEST.json`. They must not be rewritten.
3. **Reference implementation contracts:** `docs/1-architecture.md`
   through `docs/6-failure-modes.md`; these are narrower examples and
   are not conceptual amendments.
4. **Reference implementation:** `engine/`, `campaigns/`, and `tests/`.
   Actual implemented behavior must be verified separately; neither a
   blueprint nor an amendment is proof of implementation.
5. **Research, decisions and design drafts:** other `docs/` files,
   including evaluator isolation designs. These are non-normative until
   explicitly adopted.

## Amendment register

| ID | Effective date | Status | Normative scope | Source |
| --- | --- | --- | --- | --- |
| [A-001](amendments/A-001-guard-before-reset.md) | 2026-11-19 | Approved conceptually; harness implementation pending | Run guard before output-driven reset/discard in conceptual AutoResearch-W proposer workflow | Owner authorization, issue #4, draft PR #2 |

## Security and implementation status

A-001 is an **approved conceptual ordering rule**, not evidence of a
working proposer harness. The current reference engine is a constrained
reference sketch, not a secure sandbox. An optional Docker isolation
backend is separately proposed under issue #3; image trust, runtime
behavior, threat model and acceptance tests must be independently
verified before the implementation is described as production-ready.

## Provenance rules

- Never overwrite or regenerate historical conceptual source files or
  their manifest to make an amendment appear original.
- Date, version and explicitly scope all future amendments.
- Link new implementation claims to code, tests and reproducible
  evidence, not to a design document alone.
- Keep historical campaign ledgers private and unmodified.
