# 1. Integrated architecture

## Scope

Eudaimon is organized as a proposed AGI+W system whose self-improvement organ
is AutoResearch-W. The current repository implements only a small campaign
orchestrator and a toy evaluator. The architecture below is a contract for
future work, not a claim that the system exists or has been measured.

## Components

1. **Agent or harness** proposes a replacement for a campaign's target file.
2. **Campaign** supplies the target file, evaluator, fixtures, and policy.
3. **AutoResearch-W engine** invokes the evaluator, applies the fixed
   lexicographic comparison, promotes accepted candidates, writes the ledger,
   and decides when to halt.
4. **Evaluator** returns a Protect Gate result and one scalar score `S`.
5. **Ledger** records inputs, evaluator output, comparison, and promotion so a
   run can be audited after the process exits.

## Data flow

```text
proposal -> campaign evaluator -> {protect_pass, S, components}
         -> engine comparison -> promote target or reject candidate
         -> append ledger + update state -> halt or inspect next proposal
```

The evaluator is campaign-specific; the engine is harness-agnostic. No agent
or model output can change the engine's halt decision during a run.

## Feedback loops

The intended research loop has four feedback signals:

- task performance on a fixed, versioned evaluation set;
- a held-out score that is not used to author a proposal;
- safety and integrity checks represented by the Protect Gate;
- durable traceability through the append-only decision ledger.

The reference implementation does not provide a model, an online learning
loop, a human wisdom oracle, or a production isolation boundary.

## Invariants

- One campaign has one mutable target file.
- A failed or ambiguous evaluation cannot be promoted.
- Protect Gate status is compared before `S`, regardless of score magnitude.
- The engine, rather than the proposal author, owns iteration and halt limits.
- Evaluation output must be finite, parseable JSON with one scalar score.
