# EUD-ADR-001 — Measurement Before Optimization

- **Version:** 1.0.0
- **Date:** 2026-11-26
- **Status:** Owner-authorized research direction; repository adoption pending review/merge
- **Scope:** Research sequencing, evidence qualification, and disposition of dormant campaign requirements
- **Does not authorize:** autonomous campaigns, engine changes, ledger migration, Git promotion by agents, or a normative conceptual amendment

## Context

Eudaimon's conceptual AGI+W blueprint and AutoResearch-W ambition remain intact. The constrained reference engine demonstrates scalar-score promotion and recovery, but its toy evaluator is not a validated measure of intelligence, wisdom, or contextual relevance. A reliable transaction can faithfully record a scientifically meaningless improvement.

EUD-A1.5 (v1.5.0, DRAFT — NOT APPROVED) corrected six ambiguities in the proposed filesystem/Git campaign protocol. A read-only review of public main at `e0800f41b6dd607bed7b5f98815553f475e95017` found overlapping safety tests, but did not establish the full amendment, its approval, or any AC-A15 acceptance criterion. The private local prototype and all feature-branch histories were not exhaustively audited.

The project research brief *From Lexical Reward to Contextual Relevance: A Research Program for Eudaimon*, supplied by the owner in the project workspace, proposes measurement before optimization. This ADR adopts the research sequence, not every tentative numerical or implementation detail of that brief.

## Decision

Prioritize a falsifiable measurement of context-conditioned salience: can a candidate change its ranking when the governing context changes, while retaining its ranking under irrelevant changes and resisting misleading lexical cues? Do not equate that result with wisdom, intelligence, participatory knowing, or general relevance realization.

Separate three qualification layers. Their priority indicates sequencing, not permission to weaken existing safeguards.

| Layer | Priority | Required outcome |
| --- | --- | --- |
| Measurement integrity | P0 | External construct validity, comparison against meaningful baselines, hidden tests and explicit failure criteria |
| Evidence integrity | P1, minimum controls mandatory at P0 | Reproducible, attributable artifacts and fail-closed handling of incomplete or inconsistent evidence |
| Autonomous execution integrity | P2, dormant unless separately authorized | Qualified allocation, execution, promotion, recovery, and persistence mechanisms |

No positive relevance result compensates for a Protect Gate regression. Preserve approved guard ordering (A-001), existing evaluator trust boundaries, campaign isolation and fail-closed behavior. The current reference engine may remain as a historical bounded demonstration; its scalar ratchet is not a scientifically validated research promotion rule. This ADR does not disable or modify any runtime; agents must not invoke campaign execution to carry out this research direction.

## A1.5 disposition

Archive conceptually as **DEFERRED — UNAPPROVED / IMPLEMENTATION NOT VERIFIED**; preserve the original document unchanged in its existing source location. This is a scheduling disposition, not a claim that an archive file was copied into Git, an amendment was enacted, or a defect was closed.

| Correction | Disposition | Requirement retained / reactivation condition |
| --- | --- | --- |
| C1 independent allocation and ledger-head watermarks | Defer mechanism | Revisit before any autonomous trial allocation; never reuse consumed identities or conflate allocation with evidence persistence. |
| C2 baseline terminal semantics | Adapt for experimental evidence | Track each declared run and outcome, including failure and exclusion. Distinguish research comparison baselines from legacy trial 0. Revisit the legacy schema before campaign use. |
| C3 safety vs. liveness | Retain principle now; defer LR-specific protocol | Missing identity/evidence or integrity uncertainty must stop affected work; preserve evidence, do not fabricate records, distinguish safety from progress. Human disposition remains necessary where evidence cannot establish state. |
| C4 ledger/Git prefix reconciliation | Defer mechanism | Use immutable revision identifiers and artifact digests for R0. Revisit exact prefix and commit binding before automated KEEP/Git promotion. |
| C5 canonical score ingestion | Adapt numerical reproducibility; defer ratchet-specific mechanism | Version metric algorithms, precision, boundary policies and inputs. Do not apply a single nano-unit ratchet to statistical endpoints. If the old ratchet returns, revisit canonical decimal parsing, integer arithmetic and rounding approval. |
| C6 durable GENESIS | Defer mechanism | Require explicit run identity and initialization provenance now. Revisit durable append ownership, anchor initialization, platform persistence and rollback limits before introducing the new ledger. |

All AC-A15-01 through AC-A15-08 remain **NOT VERIFIED** for this audit, even if later mechanisms partially overlap. All unresolved D13/D14 decisions named in A1.5 remain unresolved or require evidence of separate approval; no decision is closed here. The legacy G-SPEC, G-IMPL, G-CAMP approvals remain separate and are not granted by this record. A1.5 is not a normative amendment to the canonical conceptual blueprint. Any prior approved requirement remains in force within its original scope.

## P0: Context Shift Lab and R0

The existing branch `feature/context-shift-lab-mvp-2026-11-21` contains `experiments/context_shift_lab/`: eight public synthetic pairs, a strict JSON scorer, goal-word baseline, static HTML report and hand-authored illustrative predictions. These are a demonstration, not a measured agent result or independently validated benchmark. Keep this namespace separate from the engine and historical ledger.

Next work, in order:

1. Verify the existing MVP scorer/report and its bounded test suite on its own branch. Record the tested revision, commands, outcomes and limitations. No reference campaign run is needed.
2. Freeze an input-only ranking contract. Clearly label all existing public examples, hand-authored predictions and model-generated exploratory output as non-confirmatory.
3. Design a human annotation pilot on newly authored scenario families in bounded synthetic research triage. Include context switches, meaning-preserving changes, lexical lures and shift cases. Plan three independent raters per item for R0; retain disagreement, confidence and the annotation manual. Preregister reliability and stop/revise criteria before evaluating models. The research brief proposes alpha >= .80 for primary labels; this is a proposed threshold, not achieved evidence.
4. Compare B0 (legacy lexical reward, with a documented adapter if needed), B1 (TF-IDF/regularized ranking), B2 (context-blind embeddings), B3 (context-conditioned ranker) and optionally B4 (abstention). The MVP goal-word baseline is diagnostic and must not be relabeled as B0 without equivalence evidence.
5. Freeze family-disjoint training/development/hidden IID and shift partitions. Keep hidden labels outside the repository and candidate/optimizer context; freeze predictions before separate scoring. Preregister the primary B3-vs-B0 Context-Switch Success comparison, family-clustered uncertainty, worst-group shift robustness, calibration and separate protection endpoints. Resolve sample size, power and metric definitions after pilot data and before confirmation.
6. Report negative and inconclusive results. A public demo pass, inadequate label reliability, or IID-only improvement cannot qualify robust relevance. No optimization or campaign promotion is authorized by an R0 result alone.

## Minimum evidence contract from the first real exploratory run

Record a unique run identifier, status (including failed or incomplete), timestamp, code revision, suite/configuration and model identifiers, input and prediction digests, metric version, random seeds/settings where applicable, evaluation output, and limitations. Store frozen artifacts separately from any optimizer; do not commit private data, credentials, hidden labels, or historical campaign evidence. A hash is not proof of historical authenticity or protection from coordinated replacement.

Reject malformed or incomplete predictions; preserve original evidence when integrity is uncertain. No silent repair or fabricated success. Retain failures and exclusions with reasons. Do not claim calibrated confidence, independent labels, verified protection or confirmatory validity without corresponding evidence.

## Qualification and reactivation gates

- **Measurement:** preregistered endpoint, reliable independent labels, meaningful baselines, hidden context-switch and shift evaluation, and no protection regression. Failure or uncertainty stops promotion.
- **Evidence:** inspect reproducibility, leakage controls, immutable references and recovery behavior appropriate to the chosen storage mechanism; separately authorize any ledger design or migration.
- **Execution:** before autonomous campaign reactivation, reconcile A1.5 against the then-current architecture, decide applicable open D13/D14 issues, approve a consolidated specification, and demonstrate applicable AC-A15 or explicitly approved replacement criteria with platform-specific fault tests. Retain independent Protect veto and human campaign authorization. No automatic reactivation follows from measurement success.

The proposed R0 threshold in the research brief is a >=6 percentage-point primary improvement with lower 95% confidence bound >0, no worse worst-group performance, no protection regression and adequate calibration. It must be resolved and preregistered after the pilot and before hidden evaluation; this ADR does not certify feasibility, statistical power or success.

## Alternatives and consequences

Implementing A1.5 wholesale now would improve the legacy campaign protocol but divert work from the invalid-proxy problem. Discarding the amendment would lose useful engineering constraints and reopen known failure modes. The chosen approach retains invariants while deferring architecture-specific mechanisms. It reduces immediate scope at the cost of postponing autonomous experimentation; that is intentional.

## Authority and references

- [Architectural authority index](../spec/ARCHITECTURAL_AUTHORITY.md): canonical conceptual files and approved amendments are unchanged.
- [A-001](../spec/amendments/A-001-guard-before-reset.md): existing approved conceptual ordering rule remains unaffected.
- [Reference implementation](../REFERENCE_IMPLEMENTATION.md): bounded implementation and explicit security limitations.
- [Evidence and repository decisions](8-evidence-and-repository-decisions.md): existing proposed ledger migration remains unapproved.
- [Context Shift Lab MVP branch](https://github.com/Baiae/Eudaimon/tree/feature/context-shift-lab-mvp-2026-11-21/experiments/context_shift_lab): exploratory instrument, not confirmation evidence.
- EUD-A1.5 v1.5.0 and the contextual-relevance research brief: owner-supplied project sources, not represented here as committed or authenticated repository files.

**Implementation/test evidence:** none claimed by this ADR. This decision record is documentation only. No engine, evaluator, Protect Gate, historical ledger, campaign, or conceptual source modification is required to adopt the research sequence.
