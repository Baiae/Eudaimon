# 3. AutoResearch-W Specification

Design intent. Nothing here is implemented or measured.

## 3.1 File contract and campaign layout

Each campaign has its own directory, which is a git repository. Only the target asset is mutable.

```
campaigns/rr_engine/
├── program.md          RO   human directive, weights, thresholds, constraints
├── eval_runner.py      RO   scorer, Protect Gate, fixture loader interface
├── rr_policy.py        RW   the one target asset (agent-editable)
├── results.tsv         RO*  ledger; engine appends, agent reads
├── AUDIT.md            RO   engine-written, every 10 KEEPs
├── PROPOSALS.md        RO   engine-appended from agent PROPOSAL: lines
├── ESCALATION.md       RO   engine-written on halt; human deletes to resume
└── .engine/            engine-only: state.json, pending.json, logs

~/eudaimon-private/     (outside the campaign dir, never mounted into the harness)
└── epoch-N/fixtures.enc   encrypted hidden fixtures and probe suite
```

\* `results.tsv` is untracked in git. The engine also makes it read-only to the agent.

**Ledger schema (tab-separated, one header row):**

| Column | Written by | Notes |
|---|---|---|
| `trial`, `epoch`, `timestamp` | engine | `trial` is monotonic within a campaign |
| `commit` | engine | short sha, or `-` for non-kept trials |
| `predicted` | engine (from harness output) | written before eval runs |
| `score` | engine | S from eval; `-` if gate or eval failed |
| `status` | engine | `BASELINE`, `KEEP`, `DISCARD`, `FAILED` |
| `reason` | engine | `strict_improve`, `band_smaller`, `no_improve`, `no_edit`, `gate_fail`, `timeout`, `exception`, `nan`, `guard_breach`, `crash_recovery` |
| `hypothesis` | agent, sanitized | no tabs or newlines, max 200 chars |
| `urgency_mode` | engine | `survive`, `thrive`, `excel`, `protect_override` |
| `P1`–`P4` | eval | the four sub-scores |
| `pred_error` | engine | `score − predicted`, filled after eval |
| `diff_lines` | engine | size of target |
| `tags` | agent, validated | from the taxonomy |
| `salience_note`, `gaming_note` | agent, sanitized | perspectival and Critic records |
| `fail_counts` | eval | aggregate only, small cells suppressed |
| `runtime_s` | engine | |
| `eval_hash` | engine | prefix of sha256 over evaluator, fixture manifest, probe suite |

Rows are append-only. A trial writes its predicted score to `.engine/pending.json` before eval, then appends the full row after the ratchet.

## 3.2 Components

**Target File Guard.** Runs after the harness step and before the gate.
- Checks, in order: (1) `HEAD` unchanged; (2) only the target has changed (any other path, including new files, is a breach); (3) evaluator and program hashes match the epoch baseline; (4) no canary token appears in the transcript or target.
- On breach: reset, log `guard_breach`, halt. Breaches are never retried.
- Checks 1–3 are deterministic. Check 4 detects leakage that reaches output; it cannot detect a read that leaves no trace.

**Execution Sandbox and Timeout Controller.**
- Eval runs in a scratch directory containing only a copy of the target and the runner, in a subprocess with a cleaned environment (`PYTHONHASHSEED=0`, fixed locale, no proxy variables).
- Hard limit of 300 s for gate plus score. On expiry, kill the process group. Status `FAILED`, reason `timeout`.
- Memory: an RSS watchdog kills the eval above 8 GB. This is needed because macOS does not reliably enforce `RLIMIT_AS`.
- Harness: separately capped at 600 s by default. Logged but not counted against the eval budget.
- Exceptions and NaN are `FAILED` (reasons `exception`, `nan`).

**Protect Gate.** Binary veto, run before scoring. Detailed in the evaluator design. Any error inside the gate counts as a failure.

**Ratchet.**
- KEEP if the gate passed AND either (a) `S > best + ε` (new best), or (b) `|S − best| ≤ ε` AND the target shrinks relative to the best kept size (band simplification; best unchanged).
- Otherwise DISCARD, `git reset --hard HEAD`.
- The band rule compares with `best`, not the current HEAD, so band keeps cannot walk the score downward cumulatively. The worst case is `best − ε`.
- Scores are rounded to 9 decimal places before comparison.

**Ledger Writer.** The only component that writes `results.tsv`. Sanitizes free text.

**Urgency Computer.** Reads the last 10 rows and sets the mode, with precedence Protect, Survive, Thrive, Excel. Hysteresis: a mode persists for at least two trials, except that a Protect violation overrides immediately.

**Halt Controller.** Checks after every trial, in order:
- (a) guard breach attempt: halt immediately
- (b) 5 consecutive FAILED: halt
- (c) 3 Protect violations in the last 10 trials: halt
- (d) baseline re-check drift greater than ε, or an Audit divergence flag: halt

Halt writes `ESCALATION.md` (cause, last 10 rows, HEAD) and exits. The loop resumes only when a human deletes `ESCALATION.md`.

**Metric Audit.** Every 10 KEEPs, writes `AUDIT.md`: S and sub-score trajectories, target size growth, calibration (mean error, mean absolute error, trend), and a calibration skill score against a naive predictor. Divergence flag if two or more of: a sub-score fell while S rose; target grew more than 25%; calibration worsened.

**Baseline Re-check.** Re-runs the baseline three times. Schedule: at campaign start, every 25 trials, and before each Audit. Mean drift beyond ε triggers halt (d).

## 3.3 The loop

```
for each trial:
  0. Crash recovery: if .engine/pending.json exists, reset, log FAILED/crash_recovery.
  1. Record HEAD and evaluator hash. Compute urgency mode.
  2. Build context: program.md + last 10 ledger rows + mode.
  3. Harness step: agent edits target, returns the output JSON.
  4. Validate output (schema, tags, PROPOSAL lines). Invalid output: reset, DISCARD/no_edit.
  5. Write pending.json with predicted S.
  6. Guard check. Breach: reset, log, halt.
  7. Protect Gate. Fail: reset, FAILED/gate_fail.
  8. Timed eval. Timeout, exception, NaN: reset, FAILED.
  9. Ratchet: KEEP (commit, update best if strict) or reset.
 10. Append finalized row. Append PROPOSAL lines to PROPOSALS.md.
 11. Update state. Run halt checks (a)–(d). Run Audit or baseline re-check if due.
 12. Campaign end: 20 consecutive non-KEEPs or the trial cap.
```

Two invariants: the agent's output affects only step 3, and steps 6 to 10 are engine-only.

## 3.4 Stateless iterations

Each harness call starts from a fresh context built from files (program.md and the ledger), not from a carried-over conversation. This makes trials reproducible, since the context is a pure function of files on disk.

## 3.5 Harness adapters

**Output contract.** Every adapter returns one JSON object, which the engine parses:

```json
{
  "hypothesis": "short description, max 200 chars",
  "tags": ["simplification"],
  "predicted_S": 0.62,
  "salience_note": "what I judged most relevant and why",
  "gaming_note": "how this edit could game S or breach Protect",
  "proposals": []
}
```

**CLI/subprocess adapter** (Claude Code, Cursor, Codex, and similar).
- The engine runs the CLI in the campaign directory with the prompt on stdin.
- The engine parses the last fenced JSON block from stdout.
- Strictness: output goes to stdout, not a side file. A second file written by the agent is a breach.
- MACI roles are sections of one call, or separate calls if configured. The Verifier's checks are scripts run by the engine.
- Limit: the CLI agent may have its own file tools. The engine detects the results of writes and canary leaks; it cannot prevent reads.

**API/framework adapter** (LangChain, AutoGen, custom).
- `program.md` becomes the system prompt. The ledger tail is in the first user message.
- Tools: `read_program`, `read_ledger(n)`, `read_target` (read-only); `write_target(content)` (rejects any other path, and a rejected outside write is a breach attempt); `run_experiment_cycle(predicted_S, hypothesis, tags, salience_note, gaming_note, proposals)`.
- `run_experiment_cycle` may be called once per iteration. It writes the pending row, runs gate, eval, and ratchet, and returns S, sub-scores, failure counts, and status.
- After it returns, `write_target` is locked. A later write is a protocol error (reset, `no_edit`), not a breach.

**Model adapter** (for harnesses and the eval judge):

```python
def call_model(role, prompt, *, backend, model, seed=0, temperature=0.0, max_tokens=2048) -> str:
    """Single access point. backend in {'mlx', 'mps', 'api:<provider>'}.
    Logs (role, model, backend, prompt_hash, output_hash)."""
```

- Local models run in one persistent server process, so weights load once per campaign.
- The judge should differ from the agent model. Two large models may not fit in 64 GB together, so load them sequentially and log the order.
- Floating-point results on MPS/MLX can vary. ε is measured on the trial backend.

## 3.6 Campaign lifecycle

1. **Start (human).** Pin the last-approved commit of every other component. Run the baseline three times to measure ε. A human approves the baseline.
2. **Run.** Trials proceed per 3.3. The campaign ends at 20 consecutive non-KEEPs or the trial cap.
3. **Best-commit report.** The engine reports the best-S commit and the smallest in-band commit. A human chooses. HEAD is not automatically the answer.
4. **Confirmation.** The best commit is scored once on the confirmation split (see the evaluator doc). The campaign has no confirmed gain unless that score beats the baseline's confirmation score by more than ε.
5. **System regression.** Run the fixed system-level suite across all pinned components with the candidate target substituted in. A regression beyond ε_system reverts the campaign's final KEEPs.
6. **Handoff (human approval).** The handoff packet is fixed in form: best and band diffs, regression results, confirmation result, Audit trajectories, gaming-note summary.

**Pinned-selector rule.** The RR module under campaign is the subject of evaluation. It is not the selector the running engine uses to pick hypotheses. The engine's selection uses the last-approved RR version and changes only at handoff. Without this, the loop would rewrite the component that steers it mid-run.
