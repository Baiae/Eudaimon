# 1. Integrated Architecture

Design intent. Nothing here is implemented or measured. Mechanisms are functional analogues.

## 1.1 Design philosophy

1. **Separate proposing, judging, and deciding.** The agent proposes, the evaluator judges, and the engine decides. No component grades its own output or controls its own halt conditions. This is the structural answer to Goodhart and self-deception.
2. **Wisdom as process, not a constraint list.** Protect is a fixed gate. Everything else is a self-correcting loop: predict, act, observe, compare, adjust.
3. **Carve, then revise slowly.** The scalar metric is the agent's well-defined sub-problem. Only humans can re-carve it, through epochs and `PROPOSALS.md`.
4. **Small steps by default.** Each trial changes one asset by one edit. Large changes need a justified urgency mode and still pass the same gate.

## 1.2 Layered structure

```
Layer 0  PINNED SUBSTRATE (read-only to agent, pinned per campaign)
         eval_runner.py: fixtures, probes, scorer, hidden split
         engine: guard, sandbox, gate, ratchet, git, adapter
         program.md: human directive, weights, thresholds

Layer 1  CAMPAIGN DIRECTOR (human-gated)
         campaign order (RR -> MACI prompts -> phronesis policy)
         campaign end (20 consecutive non-KEEPs or trial cap)
         system regression suite, handoff approval, epoch changes

Layer 2  ITERATION LOOP (engine-owned, automated)
         context build -> harness step -> guard -> gate -> timed eval
         -> ratchet -> ledger -> urgency -> halt check

Layer 3  MUTABLE TARGET (agent-owned, one file per campaign)
         rr_policy.py | maci_prompts.md | phronesis_policy.yaml
```

## 1.3 Components and functions

| Component | Functional role | Analogue | Writes to |
|---|---|---|---|
| Fixture set (visible and hidden) | environment the edits act on | sensory-motor world | none (read-only) |
| Evaluator (`eval_runner.py`) | produces perception: S, sub-scores, failure counts | sensory channel | returns to engine |
| Protect Gate | binary veto before scoring | immune / boundary check | ledger (violations) |
| Guard | membrane: admits change only to target | cell membrane | ledger (breaches) |
| Timeout controller | metabolic budget per trial | energy budget | ledger (timeouts) |
| Ratchet | selection: keep or expel the variant | natural selection | git, ledger |
| Ledger (`results.tsv`) | extended memory and shared generative model | memory, world model | itself (append-only) |
| Urgency computer | converts ledger into layer urgencies and mode | homeostatic regulator | mode field |
| Harness (agent) | proposes one edit with a predicted score | actor and predictor | target file, output JSON |
| Model adapter | single access point for all model calls | sensorimotor interface | none |
| `PROPOSALS.md`, `AUDIT.md`, `ESCALATION.md` | outward channels to humans | reporting | engine (agent proposes only) |

## 1.4 Data flows

Primary, per trial:

```
ledger tail + program.md
  -> context prompt
  -> harness: Proposer / Critic / Verifier (Phronetic Ascent)
  -> one edit to target + predicted S + hypothesis note
  -> Guard (scope, evaluator hash, history unchanged)
  -> Protect Gate (probe suite)
  -> timed eval (opt and shift fixtures, deterministic)
  -> S, sub-scores, failure counts
  -> Ratchet: KEEP (commit) or reset
  -> ledger row (4P fields + prediction error)
  -> urgency per layer -> mode -> halt check -> next trial
```

The agent receives S, the four sub-scores, failure-category counts, the ledger tail, and `program.md`. It never receives the hidden split, per-item hidden results, or probe contents.

The agent emits one edit, a hypothesis note, a predicted S, a salience note, a gaming-risk note, and optional `PROPOSAL:` lines.

## 1.5 Feedback loops

| Loop | Timescale | Signal | Effect |
|---|---|---|---|
| L1 Ratchet | per trial | S vs. best ± ε | keep or expel the variant |
| L2 Mode control | per trial | urgency per layer | edit size, diversity, ambition |
| L3 Calibration | rolling window | prediction error | smaller edits when predictions are poor |
| L4 Audit | every 10 KEEPs | S, sub-score, size, calibration trends | divergence flag, then halt |
| L5 Halt | event | FAILED streak, Protect count, drift | stop loop, write `ESCALATION.md` |
| L6 Campaign handoff | campaign end | system regression suite | revert final KEEPs or approve |
| L7 Epoch | human-initiated | applied `PROPOSALS.md` entry | re-carve metric, reset best and baseline |

The fast loops (L1, L2) do most of the work. The slow loops (L4 to L7) keep them honest. Only humans close L6 and L7.

## 1.6 Known tensions

- **Determinism versus ε.** S is deterministic, yet ε comes from baseline spread. This is consistent only if ε absorbs backend nondeterminism (MPS/MLX). Measure ε on the trial backend.
- **Visible S as a Goodhart channel.** The agent sees S on every trial. Mitigation is the hidden split plus audits, not withholding S.
- **Finite probe suite.** A fixed Protect suite can be learned over a long epoch. Mitigation is rotation per epoch.
