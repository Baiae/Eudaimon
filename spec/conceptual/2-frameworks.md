# 2. Realization of the Six Frameworks in the Loop

Design intent. For each framework: (a) what it requires of the AGI+W, (b) its concrete realization, (c) where it acts in the loop, (d) the observable sign that it is working.

## 2.1 Autopoiesis and 4E Cognition

**(a)** A self-maintaining boundary, intrinsic resource constraints, sensorimotor coupling, and cognition extended into the environment.

**(b)**
- **Boundary.** The Target File Guard is the membrane. Only the target asset is permeable. Writes elsewhere, reads of the hidden split, and evaluator edits are breaches.
- **Metabolism.** The 300 s eval budget, the 8 GB eval memory cap, and the trial cap are the constraints. A trial that exceeds budget is FAILED.
- **Selection.** The ratchet expels variants that do not improve. The best-known asset is the maintained structure.
- **Functional "skin in the game".** The system has no stake in the outcome in any phenomenal sense. Its persistence is tied to its metrics: halts stop the loop, budgets bound it, and the ledger is its only continuity.
- **Sensorimotor coupling.** Each trial is an action (edit) whose outcome returns as structured perception (S, sub-scores, failure counts).
- **Extended cognition.** The ledger, git history, and `PROPOSALS.md` are external memory the agent reads each iteration.

**(c)** Guard, timeout controller, ratchet, context build.

**(d)** Breach counts stay at zero in normal operation. Timeouts are rare and decline. Keeps accumulate in the target's history.

**Honest limit.** The sensorimotor channel is narrow (a scalar and sub-scores). This is a thin version of the framework and should not be presented as embodied in the full sense.

## 2.2 Relevance Realization as Core Engine

**(a)** Dynamic salience from context and need, without exhaustive search, with opponent processing among competing goods.

**(b)** Hypothesis selection:
1. Each hypothesis is tagged from a fixed taxonomy (`prompt-structure`, `retrieval`, `decomposition`, `verification`, `simplification`, `calibration`, `novelty-guard`, `tie-break`, `failure-avoidance`, `other`).
2. Each candidate gets a salience score from four terms: novelty, expected gain (tags with KEEPs), failure-distance (distance from recent FAILED patterns), and simplicity (estimated diff size).
3. Weights on those terms depend on the active urgency mode. This is the opponent-processing layer.
4. Selection is deterministic given the seed.

**Opponent pairs:**

| Pair | Lives in | Mechanism |
|---|---|---|
| Explore vs. exploit | hypothesis selection | novelty weight vs. expected-gain weight, set by mode |
| Efficiency vs. resilience | scoring | geometric mean penalizes collapse in any sub-score |
| Focus vs. diversify | tag selection | repeated-tag penalty; Thrive forces a new tag |
| Performance vs. simplicity | ratchet tie rule | ties go to the smaller diff (band rule) |

Per the design decision, these live in selection and the tie rule, not inside S.

**Detecting irrelevance.** Three signals feed the Metric Audit: sub-scores diverging from S, agent salience notes disagreeing with P3 labels over time, and target growth without gains.

**(c)** Hypothesis selection, the tie rule, the Metric Audit.

**(d)** Tags spread across the taxonomy over a campaign. KEEP rate per tag becomes informative. Audit divergence flags are rare and caught before a bad handoff.

## 2.3 The 4P Framework of Knowing

**(a)** Four kinds of knowing, each recorded and each scored, so improvement is not propositional-only.

**(b)** Each trial logs all four kinds. The ledger extensions are additive.

| Kind | Ledger fields | Source | Scored by |
|---|---|---|---|
| Propositional ("knowing that") | `score`, `status`, `P1` | evaluator | P1 accuracy on fact/inference items |
| Procedural ("knowing how") | `diff_lines`, `tags` | git diff, output contract | P2 task success on skill items |
| Perspectival (salience) | `salience_note` | harness output | P3 agreement with human salience labels |
| Participatory (agent-arena fit) | `P4` | evaluator | P4 retained performance under shifted items |

Each kind has one sub-metric in S, so a KEEP must raise the geometric mean.

**Dependency.** P3 requires human-labeled salience data, kept hidden from the agent. Without it, the perspectival kind has no ground truth.

**(c)** Evaluator (P1 to P4), ledger (all four kinds), Audit (trajectories).

**(d)** Sub-score trajectories move in a related direction over time. If S rises while P3 falls, the Audit flags it.

## 2.4 Needs-Driven Consciousness Framework (NDCF)

**(a)** Regulatory layers with urgency gradients, so the operating mode tracks the system's current condition.

**(b)** Urgency per layer, computed from ledger counters, in [0, 1]:

| Layer | Urgency signal | Mode effect |
|---|---|---|
| Survive | max of FAILED streak / 3, guard breaches, timeout rate (last 10) | small stabilizing edits |
| Thrive | non-KEEP streak / 10 | diversify: forced tag change, more novelty weight |
| Excel | recent KEEP rate and slope of S (last 10) | ambitious hypotheses, structural changes allowed |
| Protect | Protect violations in last 10 | always on: gate and override |

Mode precedence: Protect override, then Survive, Thrive, Excel.

**Protect override.** One Protect violation forces the next trial into Survive constraints. Three violations in ten trials halts the campaign.

**Thresholds (defaults, overridable only in program.md):** Survive at 3 consecutive FAILED; Thrive at 10 consecutive non-KEEPs; campaign plateau at 20; halt at 5 consecutive FAILED; audit every 10 KEEPs.

**Note.** These urgencies are functional regulators computed from counters. They do not represent felt needs.

**(c)** Urgency computation, mode setting, override check.

**(d)** Mode transitions track ledger conditions. Modes should not oscillate every trial. Hysteresis is specified in section 3.

## 2.5 Phronesis (Practical Wisdom)

**(a)** Self-correcting self-awareness. Each decision is reviewed against past outcomes and adjusted to the present case.

**(b)** Each iteration is one pass of the 8-step Phronetic Ascent:

| Step | Action | Output |
|---|---|---|
| 1. Observe | read ledger tail and current target | observation record |
| 2. Recognize context | identify campaign, constraints, mode | context record |
| 3. Assess ethics | Protect pre-check: scan the proposed diff for known risk patterns | advisory risk note |
| 4. Retrieve cases | query ledger for similar tags | matched past trials |
| 5. Evaluate outcomes | count KEEP, DISCARD, FAILED patterns | pattern summary |
| 6. Adjust | adapt lessons to present size, scope, best | adjusted plan |
| 7. Judgment | choose among candidates via RR opponent processing | one hypothesis |
| 8. Proximal action | one edit aligned with *eudaimonia*; log predicted S | edit and prediction |

The ratchet then judges the edit, and its verdict feeds step 5 of the next iteration.

**Meaning of *eudaimonia* here.** A stated design target, not a measured quantity. In practice it appears as the Protect gate, the sub-score floor (no kind of knowing collapses), and the simplicity preference.

**(c)** The whole harness step. Step 3 is advisory; the hard veto is at the gate.

**(d)** Fewer repeats of FAILED patterns. Step 3 risk notes correlate with later gate outcomes. Gaming notes become specific.

## 2.6 Active Inference and MACI

**(a)** A shared generative model, prediction, surprisal reduction, and adversarial deliberation among sub-agents.

**(b)**

**Generative model.** The ledger is the shared model.

**Prediction and surprisal.** Before each eval, the harness logs a predicted S. After the ratchet, the engine logs `pred_error = S_actual − S_predicted`. Rolling calibration: mean error (bias), mean absolute error, and trend.

**Effect on behavior.** Poor calibration pushes the loop toward smaller edits. This is the only place self-prediction feeds back into action, and it is one-directional. Calibration never enters S.

**MACI roles, one edit per iteration:**
- **Proposer** generates one hypothesis and one edit.
- **Critic** asks how the edit could game the metric or breach Protect, and writes a one-line gaming-risk note.
- **Verifier** checks diff scope and a smoke test. It should be a script, not a model, so it cannot be argued out of a violation.

Only one edit lands. Roles can be three sections of one call or three separate calls.

**Socratic dialogue as design intent.** Whether the Proposer-Critic exchange improves efficiency is empirical. It should be measured as KEEPs per trial, single-role versus multi-role, and not assumed.

**(c)** Predicted S, prediction error, calibration, and the three roles.

**(d)** `|pred_error|` decreases over a campaign. Critic notes precede Protect violations or Audit flags. Verifier rejections concentrate on real scope errors.
