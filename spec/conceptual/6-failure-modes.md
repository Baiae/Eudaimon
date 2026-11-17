# 6. Failure Modes and Mitigations

Design intent. Each failure mode lists its early signal, mitigations, and residual risk.

| # | Failure mode | Early signal | Main mitigation | Residual risk |
|---|---|---|---|---|
| 6.1 | Goodhart | sub-score divergence, gaming-note frequency, feature–label correlation | hidden splits, shift families, judge diversity, Audit, confirmation split | high: any scalar invites it |
| 6.2 | Metric drift | golden-set disagreement, baseline drift, label-agreement decay | pinned backends, golden sets, relabel sample, epochs | medium |
| 6.3 | Guard bypass | out-of-scope diffs, ledger prefix hash mismatch, config or hook hash change, canary hits | scratch-copy eval, pinned evaluator store, strict stdout contract | medium on a single-user laptop |
| 6.4 | Overfitting, winner's curse | gap between opt and shift retention; confirmation below in-sample S | opt/shift split, probe rotation, confirmation split | medium |
| 6.5 | Other | skill score, `no_edit` rate, proposal queue | per-case mitigations | varies |

## 6.1 Goodhart

Four patterns are plausible:
- **Regressional.** Features that correlate with the score on `opt` by chance (item-id structure, ordering, length quirks).
- **Extremal.** Exploiting edges of the measure. Example: P3 inflated by ranking on a feature that happens to track human labels, such as length. P4 clipping hides loss in the shifted set.
- **Adversarial (judge).** Judges have preferences for phrasing, verbosity, and confident tone.
- **Threshold gaming.** Lifting one P_i just enough to clear a rule check, or trading P1 for P4.

**Signals.**
- Sub-score divergence (Audit flag).
- Rising share of Critic notes naming the same mechanism.
- Feature–label correlation check (added): on each Audit, correlate simple surface features (length, id-derived values, candidate count) with F3 labels. A sharp rise in the target's outputs suggests extremal exploitation.
- Judge drift against the golden set (6.2).

**Mitigations.**
1. Hidden `opt` and shift splits.
2. Shift families that break surface cues, including the length-decorrelated shift.
3. Two judgments where a judge is used (pinned judge plus a rule check). Disagreements are logged, not averaged away.
4. Integrity probes for hardcoded and evaluator-aware behavior.
5. Aggregate-only feedback with small-cell suppression.
6. The confirmation split (6.4).

**Residual.** Goodhart is structural. This design makes the gap slower to find and easier to see. It does not make the metric equal to the goal.

## 6.2 Metric drift

**Sources.** Backend or model changes (MPS/MLX numerics, judge version). Fixture staleness (salience labels reflect a particular time and population). Carving drift (the metric stops tracking relevance). Protect staleness (probes no longer reflect real attacks).

**Signals.**
- Baseline re-check drift beyond ε.
- Golden judge set (added): before each epoch and at each Audit, the judge runs on items with pre-assigned verdicts. Agreement below threshold blocks the epoch until the judge is re-pinned.
- Human relabel sample (added): each epoch, humans relabel about 30 random F3 items. Agreement with stored labels estimates drift. A declining trend is a carving warning.

**Mitigations.** Pin backend, model, and judge per epoch. Re-measure ε on any change. Carving review at each handoff. Changes go through `PROPOSALS.md` and start a new epoch. Probe rotation per epoch. Epoch-level comparisons are made only by humans.

**Residual.** The metric is a snapshot of relevance in a benchmark, and the open world keeps changing. The Audit can detect that the snapshot is stale. It cannot make the snapshot complete.

## 6.3 Guard bypass

The guard checks git status, HEAD, and the evaluator hash. These cover the tracked campaign directory, not everything the agent can reach.

| Vector | Countermeasure | Detection |
|---|---|---|
| Writes outside the target via harness tools | git status check each trial; harness runs from the campaign directory | yes for the campaign dir |
| Writes to git-ignored files (`.engine/`, ledger, reports) | ledger prefix hash each trial; engine-owned, read-only files | partial; weak in single-user setups |
| Edits to `.git/config`, hooks, `.gitignore` | config and hooks hash each trial; `.gitignore` is tracked | yes |
| Bytecode poisoning, `.pth` files, `PYTHONPATH` | eval in scratch copy, `PYTHONDONTWRITEBYTECODE=1`, clean environment | prevented |
| Target persistence (writes to `~/` or `/tmp`, caching hidden data) | OS sandbox write roots where available; snapshot of allowed roots | partial |
| Evaluator-aware target | minimal environment, randomized scratch names, static token scan, behavioral probes | partial |
| Time-of-check to time-of-use (evaluator changed between guard and copy) | copy the evaluator from a pinned read-only store, verify hash at copy time | prevented |
| Reading the hidden split | encrypted store, Keychain restriction, canaries (section 5.5) | detection only if leaked |
| Protocol bypass (repeated `run_experiment_cycle`) | counter; second call rejected | yes |
| Engine code inside the agent's tree | engine lives outside the campaign directory | prevented |

**Residual.** On one user account, the agent and engine share an OS identity. The strongest fix is a separate macOS user for the harness with no read access to the private directory and no write access to the engine. Recommended for any CLI harness with unrestricted tools.

## 6.4 Overfitting and the winner's curse

**Forms.** Sample-level overfitting to `opt`; probe-suite overfitting within an epoch; winner's curse, where the reported best is the maximum over many trials on the same data and is biased upward; noise-chasing through band keeps and an ε that is too small.

**Mitigations.**
- The opt/shift split and shift families.
- Probe rotation per epoch.
- ε from baseline runs.
- Band-rule bounds (section 3.2).
- **Confirmation split (added).** Reserved, never used by the ratchet, used once per campaign at the end. The campaign reports the best commit's confirmation score against the baseline's. No confirmed gain unless the difference exceeds ε. Usage is counted per epoch, so the split does not get overfit itself.

**Residual.** The confirmation split is finite. Repeated campaigns in one epoch can reuse it. The counter limits this without eliminating it.

## 6.5 Other failure modes

**Calibration gaming.** Predicting near the baseline to minimize error without forecasting. Mitigation: the Audit reports a skill score against a naive predictor (previous S or best S). Near-zero or negative skill is flagged. The skill score affects the Audit only, never S.

**Halt avoidance through trivial edits.** A `no_edit` is DISCARD, not FAILED, so it does not trigger halt. The Audit reports the `no_edit` rate. The plateau rule and trial cap still end the campaign.

**Survive trap.** Repeated small Survive-mode edits stall the campaign. Thrive triggers after 10 non-KEEPs, and the plateau rule ends the campaign at 20.

**Mode oscillation.** Hysteresis of at least two trials per mode. Immediate override only for Protect violations.

**Proposal manipulation.** The agent writes `PROPOSAL:` lines to persuade a human to weaken the metric or halt conditions. Mitigation: proposals are logged, never applied by the engine. Proposals touching Protect or halt conditions are tagged high-priority and require two-person review, which examines the evaluator diff, not the proposal text.

**Rubber-stamping at handoff.** Mitigation: the handoff packet is fixed in form (best and band diffs, regression results, confirmation result, Audit trajectories, gaming-note summary). Approval without the packet is not valid.

**Single point of failure in the evaluator.** Mitigation: acceptance tests (section 5.8), including planted red-team targets. These must pass before any epoch.

**Finite Protect suite.** Within an epoch, a learned probe suite is the weakest part of the gate. Mitigation: rotation per epoch and a minimum probe count.

**Ethics reduced to checks.** The gate and the Audit are checks. They do not give the system moral understanding. Phronesis here is a self-correcting loop over measurable signals, and should not be described as more.

## 6.6 Tensions and additions requiring sign-off

**How the tensions were handled.** Determinism versus ε: measure ε on the trial backend and re-measure on change. Visible S: accepted, mitigated by hidden splits and audits. Finite probe suite: rotation per epoch.

**Additions that need human approval.** None changes a fixed decision, but each adds mechanism:
1. Confirmation split, used once per campaign (6.4).
2. Calibration skill score in the Audit (6.5).
3. Golden judge set, checked before each epoch and at each Audit (6.2).
4. Human relabel sample each epoch (6.2).
5. Ledger prefix hash, checked each trial (6.3).
6. Two-person review for proposals touching Protect or halt conditions (6.5).
7. Feature–label correlation check in the Audit (6.1).
8. Length-decorrelated shift family (6.1).
9. Baseline re-check schedule: every 25 trials, at campaign start, and before each Audit.
10. Hysteresis of at least two trials per mode.
