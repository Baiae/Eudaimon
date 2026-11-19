# Eudaimon — Evidence and Repository Reconciliation Proposal

**Status: PROPOSED — NOT AUTHORIZED FOR MIGRATION, GIT OPERATIONS, OR CAMPAIGN EXECUTION**
**Inspection date:** 2026-11-16
**Scope:** Local directory `/Users/projectphaedra/Documents/ChatGPT/Eudaimon` and public `Baiae/Eudaimon` main.

## Decision A — Ledger integrity (proposed)

**Recommendation:** Keep the existing legacy JSONL ledger byte-for-byte unchanged. Do not retrofit a chain into old records or claim they are authenticated. Adopt a separate versioned v2 ledger for future runs only after explicit approval, with monotonic sequence numbers, canonical JSON serialization, a previous-record SHA-256 digest, and a schema identifier. Define an initial genesis record binding the v2 chain to a **hash of the complete legacy ledger bytes** at migration time, with a prominent `LEGACY_UNVERIFIED` designation. The genesis hash records the legacy bytes as seen at migration, **not** their historical authenticity. SHA-256 chaining detects accidental or unsanctioned edits relative to an externally retained trusted anchor; without external anchoring or signatures, an attacker who can rewrite the ledger can recompute the entire chain.

**Fail-closed policy proposed:** A partial final JSONL line, missing sequence, broken chain, duplicated transaction ID, or unknown schema must halt new evaluation and require operator review. Never silently truncate, repair, or overwrite existing evidence. Retain the original ledger and migration manifest with their digests. The existing `tools/audit_ledger.py` is structural-only and must not be marketed as tamper-proof.

**Approval needed before implementation:** schema v2 format; external anchoring/signature strategy; whether to use a new ledger file or a sidecar; operator recovery procedure; retention of evidence exports.

## Decision B — Repository canonical layout (proposed)

**Recommendation:** Treat the local structured tree as the **candidate** canonical source layout, but do not make it canonical until reviewed. Preserve GitHub's current commit history separately; do not force-push, graft, or merge histories automatically.

| Component | Public main at 9c464796 | Local working tree |
| --- | --- | --- |
| Design documents | `1-architecture.md`, `2-frameworks.md`, `3-autoresearch-w.md`, `5-eval-runner.md`, `6-failure-modes.md` at root | Corresponding documents under `docs/`, plus remediation and this proposal |
| Engine | `engine.py` at root | `engine/engine.py` plus package init |
| Example campaign | `program.md` at root | `campaigns/rr_engine/program.md`, `eval_runner.py`, `rr_policy.py`, `proposals/` |
| Tests | None in public tree | `tests/test_engine.py`, `tests/test_ledger_audit.py` |
| Tools | None in public tree | `tools/audit_ledger.py` |
| Runtime evidence | Not present in public tree | `campaigns/rr_engine/.autoresearch/` ignored |
| Git | `main` at `9c464796a68ca19e565c7bdd5f764691a78616a4` | Unborn `master`, no commits, no remote |

The table is a **path-level inventory**, not a semantic diff or proof that similarly named documents are equivalent. Before any publication, compare bytes and behavior of every corresponding file, verify that no credentials or private campaign evidence enter the proposed commit, and decide whether to stage the structured tree on a new branch based on public `main`.

## Decision C — Artifact retention (proposed)

- Keep `.autoresearch/` ignored locally until a separate evidence-export policy is approved. Preserve the existing ledger and state files.
- Proposal files are currently ignored; decide explicitly whether proposals are reproducible source inputs or disposable local fixtures. Do not change ignore rules before deciding.
- Do not commit generated `__pycache__` or `.DS_Store` files.
- The local repository's unborn `master` and the public repository's `main` are distinct histories. Do not configure a remote, create a commit, or push without separate authorization.

## Execution gates

1. Approve or amend Decisions A–C.
2. Complete remaining R5 containment design and R6 fault-injection coverage.
3. Produce a full content-level comparison against public main in a read-only operation.
4. Only then propose a non-destructive branch-based publication plan for explicit authorization.

**No production campaign, migration, Git write, or publication is authorized by this proposal.**


## Verified content-level comparison (read-only)

**Reference:** public `main` commit `9c464796a68ca19e565c7bdd5f764691a78616a4`. Fetched the nine corresponding files directly from that immutable commit and compared their SHA-256 digests with local files. **All nine differ byte-for-byte**; therefore, the public documents cannot be treated as redundant copies of the local documents.

| Public path | Local path | Public bytes | Local bytes | Result |
| --- | --- | ---: | ---: | --- |
| README.md | README.md | 2244 | 1886 | DIFFERENT |
| .gitignore | .gitignore | 142 | 104 | DIFFERENT |
| 1-architecture.md | docs/1-architecture.md | 5087 | 2063 | DIFFERENT |
| 2-frameworks.md | docs/2-frameworks.md | 8848 | 1803 | DIFFERENT |
| 3-autoresearch-w.md | docs/3-autoresearch-w.md | 10260 | 2401 | DIFFERENT |
| 5-eval-runner.md | docs/5-eval-runner.md | 9205 | 1391 | DIFFERENT |
| 6-failure-modes.md | docs/6-failure-modes.md | 9202 | 1704 | DIFFERENT |
| engine.py | engine/engine.py | 9789 | 28582 | DIFFERENT |
| program.md | campaigns/rr_engine/program.md | 4814 | 1233 | DIFFERENT |

**Publication blocker:** Public design documents are substantially longer than the local documents. Do not replace or move them without an explicit, section-by-section semantic reconciliation. Keep the public documents available as a separate historical design reference. This inventory proves difference, not which text is authoritative.

**Recommendation revised:** A publication branch should preserve public documentation initially and add the local implementation under its structured directories, resolving README and ignore-rule collisions explicitly. No publication branch has been created.

## Semantic reconciliation follow-up

See `docs/9-semantic-reconciliation.md` for the requirement-level mapping and D1–D5 decisions. The public AGI+W blueprint and local reference engine are different scopes. No canonical document moves or substitutions are authorized.
