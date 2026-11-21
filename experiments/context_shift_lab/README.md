# Context Shift Lab — public MVP

A tiny evaluation instrument for one question: when the **same evidence** appears under two different goals, does a submitted ranking change its first choice appropriately? The first deliverable is a self-contained HTML results page, a strict JSON scorer, eight synthetic pairs, and a diagnostic goal-word baseline. The sample submission is deliberately hand-authored to demonstrate the interface; it is **not** a measured AI result.

## Run

From the repository root, with Python 3.12 (standard library only):

```bash
python3 experiments/context_shift_lab/runner.py \
  --predictions experiments/context_shift_lab/illustrative_predictions.json \
  --html /tmp/context-shift-report.html \
  --json /tmp/context-shift-results.json
```

Open `/tmp/context-shift-report.html` in a browser. It has no server, network calls, JavaScript dependencies, or backend process. A committed `demo_report.html` shows the illustrative result immediately. The report filters passed/missed pairs and prints to PDF.

To test an agent, export the input-only set and give it each `goal` and `items` from `demo_prompts.json` (or from your exported copy). Collect a complete ranking of item IDs per case. Save a JSON file using the shape below, then pass it to `--predictions`.

```bash
python3 experiments/context_shift_lab/runner.py \
  --export-prompts /tmp/context-shift-prompts.json
```

The export excludes `gold_id` and `reason`. Because the demo labels are public in the repository, this procedure is exploratory and unsuitable as a confirmatory test.

```json
{
  "model_name": "Your frozen agent/version",
  "predictions": [
    {"case_id": "replication", "ranked_ids": ["b", "a", "c"]}
  ]
}
```

Include **every** case, exactly once; the snippet above only illustrates one entry. Each `ranked_ids` must be a permutation of that pair's item IDs. An optional numeric `confidence` from 0 to 1 is retained for inspection but is not calibrated or scored. Missing or malformed entries stop scoring; they do not quietly count as successes. The CLI exits nonzero and reports the first validation error.

The pass rule is deliberately narrow: a pair passes only if **both** first choices match its provisional labels. The report also includes the score of a deterministic goal-word overlap baseline for reference. It does not infer wisdom, contextual awareness, safety, or statistical significance. Public cases are not a hidden split. There are no independent human labels or real agent runs in the committed demonstration.

## Architecture and blast radius

`demo_suite.json` → frozen agent rankings → `runner.py` validation and scoring → portable HTML/JSON reports. The runner reads submitted **data only**; it does not execute submitted model code. It lives in `experiments/` and does not change `engine/`, campaign policy pins, Protect Gate, historical ledgers, or the separate draft Docker backend. Keep results from this public demonstration outside the promotion logic.

| Choice | Gain | Cost | Primary failure mode / blast radius |
|---|---|---|---|
| Public synthetic pairs | Demo and team trial without credentials | No independent validity | Label assumptions could be mistaken for ground truth; affects this demo report only |
| Exact permutation contract | Reproducible pair scoring | Agents need an adapter | Partial output is rejected; no misleading partial score |
| Static HTML with embedded JSON | Shareable offline report | No hosted multiuser workflow | Report can be copied out of context; status and suite hash stay visible |

## Next evidence gate

Have at least two independent reviewers label newly authored, family-disjoint pairs; retain disagreements, freeze a hidden confirmation split outside the repository and candidate context, and preregister a context-switch comparison with a shift family. Only then discuss validated claims or using the measure in an optimization loop. The Protect veto stays independent of this relevance score.

## Verification

```bash
python3 -m unittest discover -s experiments/context_shift_lab -p 'test_*.py' -v
```
