# Eudaimon — Semantic Reconciliation and Canonicalization Gates

**Status: D1 APPROVED; D5 LOCAL REFERENCE ENGINE TRUST RESTRICTION IMPLEMENTED; D2–D4 OPEN; NO PUBLICATION AUTHORIZATION**

**Sources inspected:** The full local contents of `docs/{1-architecture,2-frameworks,3-autoresearch-w,5-eval-runner,6-failure-modes}.md`; the corresponding public documents at immutable `Baiae/Eudaimon` commit `9c464796a68ca19e565c7bdd5f764691a78616a4`, including their section headings and operational requirements; local `engine/engine.py`, `campaigns/rr_engine/eval_runner.py`, and `docs/7-remediation-spec.md`. This is a requirement-level comparison, **not** a claim that all prose has been reconciled line by line. Preserve the originals.

## 1. Core distinction

The **public specification** describes a proposed, richer AutoResearch-W/AGI+W research architecture, including a proposer harness, hidden evaluation splits, 4P metrics, a guard, urgency modes, git-based ratchet, confirmation, audit, and a TSV ledger. It is **not proof those components were implemented**.

The **local documentation** explicitly narrows scope to a deterministic, dependency-free **reference campaign engine** using pre-existing proposal files, one mutable target, a campaign-specific evaluator, JSONL evidence, and a toy policy. It is **not a substitute for the original conceptual design**.

These are different layers of the project, not necessarily conflicting versions of one executable specification.

## 2. Requirement disposition matrix

| Area | Public design requirement or concept | Local reference behavior/documentation | Disposition |
| --- | --- | --- | --- |
| Authority | Separate proposing, judging, and deciding; proposer must not control acceptance or halt | Evaluator returns Protect and score; engine decides; no built-in proposer | **SHARED INVARIANT**; retain in both layers |
| Agent harness | Stateless iterations, model adapters, restricted tools, feedback context | External proposal files in stable lexical order | **FUTURE DESIGN**; no harness implemented |
| Single mutable target | Target-only writes, guard against out-of-scope changes | One target with path/symlink validation and snapshot binding; not a full sandbox | **PARTIAL IMPLEMENTATION**; do not claim comprehensive guard |
| Git ratchet | Baseline HEAD checks, kept commits, rollback/reset on breach | Digest-checked atomic file replacement and transaction recovery; no per-trial Git ratchet | **DIFFERENT MECHANISM**; retain both descriptions |
| Evaluator | Hidden fixture store, multiple families, adversarial probes, 4P metric | Toy document-contract scoring policy, illustrative held-out phrases | **NOT IMPLEMENTED AS PUBLICLY SPECIFIED** |
| Protect Gate | Veto independent of score, including static and behavioral probes | Boolean Protect Gate checked before score; toy sentinel/phrase checks | **SHARED RULE, DIFFERENT COVERAGE** |
| Score | P1–P4 geometric mean and score floors; epoch-scoped comparisons | Contract/safety/traceability/held-out geometric mean | **METRIC INCOMPATIBILITY**; no cross-score comparison |
| Acceptance | Public ratchet includes epsilon/band and simplicity considerations | Strict improvement in score after protection; ties rejected | **POLICY CONFLICT**; human selection required |
| Ledger | `results.tsv`, defined columns, prediction error, mode, audit fields | `.autoresearch/ledger.jsonl`, promotion transactions, state file | **FORMAT CONFLICT**; no silent conversion |
| Evidence security | Prefix hash checks, guard, fixture/evaluator hash, canary suppression | Structural audit and digest-bound candidate snapshot; no ledger hash chain | **PARTIAL IMPLEMENTATION**; not tamper-proof |
| Urgency/modes | NDCF layer urgencies, survive/thrive/excel/protect override, hysteresis | No urgency controller | **FUTURE DESIGN** |
| 4P framework | P1–P4 scored dimensions and agent feedback | Local six broad functional categories; not equivalent to P1–P4 | **CONCEPTUAL LOSS IF OVERWRITTEN**; preserve public detail |
| Other frameworks | Autopoiesis/4E, relevance realization, NDCF, phronesis, active inference/MACI | General intelligence, wisdom, reflection, deliberation, social alignment, self-improvement | **TAXONOMY MISMATCH**; preserve original six-framework mapping |
| Confirmation | Reserved confirmation split, single end-of-campaign use, baseline comparison | No confirmation phase | **FUTURE DESIGN; HUMAN SIGN-OFF** |
| Metric audit | Every 10 KEEPs; calibration skill and divergence reporting | No metric audit | **FUTURE DESIGN; HUMAN SIGN-OFF** |
| Campaign termination | Trial/time budgets, plateau, Protect override, epoch/campaign lifecycle | Iteration/no-improvement budgets, errors, lock, proposal exhaustion | **PARTIAL IMPLEMENTATION** |
| Evaluator isolation | Bounded runtime/memory in sandbox, hidden data inaccessible to proposer | Timeout, output bounds and process-group kill; same-user evaluator not sandboxed | **UNRESOLVED SAFETY BOUNDARY** |
| Human review | Explicit sign-off for changes to protections, halt logic and additional safeguards | Local `docs/6-failure-modes.md` explicitly reserves decisions | **SHARED INVARIANT** |

## 3. Non-negotiable preservation rules

1. **Do not replace** public `2-frameworks.md` with local `docs/2-frameworks.md`: the original six frameworks are substantially more specific than the local functional categories.
2. **Do not replace** public `3-autoresearch-w.md` with the local campaign contract: the former specifies a richer proposed system and a different ledger/ratchet architecture.
3. **Do not replace** public `5-eval-runner.md` with the toy evaluator document: hidden fixtures, leakage controls, probes, confirmation and acceptance criteria would be lost.
4. **Do not replace** public `6-failure-modes.md` with its local summary: specific Goodhart, guard, overfitting, calibration and sign-off provisions would be lost.
5. Keep public `1-architecture.md` as the conceptual architecture and local `docs/1-architecture.md` as the implemented reference boundary.
6. Treat `program.md` as a separate content collision; a byte-level mismatch is confirmed, but no program-level semantic equivalence has been established.
7. Preserve the public historical commit and the local source tree independently. No force push or unreviewed overwrite.

## 4. Canonical conceptual authority and proposed further organization

- `spec/conceptual/`: **APPROVED AND IMPLEMENTED** — unchanged snapshots of the public conceptual design with immutable commit provenance and SHA-256 manifest.
- `docs/reference/`: current local reference engine contracts, marked **IMPLEMENTED REFERENCE** only where verified by tests.
- `docs/7-remediation-spec.md`: safety defects, implemented fixes and unresolved limitations.
- `docs/8-evidence-and-repository-decisions.md`: ledger and publication decisions.
- `docs/9-semantic-reconciliation.md`: this mapping and outstanding decisions.

Only the additive conceptual snapshot and README authority clarification have been performed. Do **not** move existing local reference documents: path changes may break references and require separate review.

## 5. Decisions requiring explicit authorization

**D1 — Product identity: APPROVED.** The richer public AGI+W AutoResearch-W blueprint is the canonical conceptual architecture. The local engine remains a constrained reference implementation. This approval does not authorize implementing the remaining blueprint features.

**D2 — Metric policy:** Keep the toy reference comparator for the example campaign, or change it to the public epsilon/simplicity policy? **Recommended: keep current reference semantics** and design the richer policy separately, with tests and human review.

**D3 — Evidence formats:** Keep legacy JSONL as reference evidence and public TSV as future conceptual specification, or mandate one format? **Recommended: preserve both contracts in their own scopes**, no automatic conversion.

**D4 — Publication:** Approve a new branch based on public main that adds local implementation without replacing original conceptual documents? **Recommended: yes, only after explicit authorization and a final secrets/evidence scan.**

**D5 — Execution trust (reference engine only): IMPLEMENTED 2026-11-17 under instruction to implement remaining safeguards.** The CLI defaults to the reviewed, SHA-256-pinned reference evaluator and its imported local policy. The programmatic config supports explicitly approved, individually pinned evaluator fixtures; arbitrary evaluator scripts fail closed by default. The pin is rechecked before each spawn; a hostile same-user actor can still race pathname checks or control other accessible code/resources. This is **not** a security sandbox, a signature, a comprehensive dependency lock, or authorization to run untrusted evaluators.

## 6. Current verification

Local regression suite: **76 passing tests** after targeted safety hardening on 2026-11-17. These tests verify the constrained reference implementation, not the full public blueprint. Existing campaign ledger: 24 structurally valid records, no pending promotion transactions, no cryptographic authentication. No real campaign was run and no Git commits, remotes, or pushes were made.

**Stop/go gate:** D1 remains approved; the narrow D5 *local reference-engine trust restriction* is implemented. D2–D4 and any broader evaluator/security policy remain open. No publication, ledger migration, untrusted execution, or silent change to architectural contracts is authorized. Future reference-engine hardening does not implement the full conceptual blueprint.
