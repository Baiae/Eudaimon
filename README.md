# EUDAIMON: AGI+W Blueprint and AutoResearch-W Engine

## Reference implementation update (2026-11-17)

This branch preserves the original public AGI+W conceptual blueprint and its
historical root-level sketches. A **separate, bounded and tested** local
reference engine has been added under [engine/](engine/) and
[campaigns/rr_engine/](campaigns/rr_engine/). See
[REFERENCE_IMPLEMENTATION.md](REFERENCE_IMPLEMENTATION.md) for the current
implementation contract, limitations, and tests. The older text below
describes the historical design-only baseline, **not** the status of the
new reference engine; no full AGI+W implementation is claimed.


Design documents and an untested reference sketch for an AGI+W (Artificial General Intelligence + Wisdom) system whose self-improvement organ is a harness-agnostic AutoResearch engine (AutoResearch-W).

**Status: design intent only.** Nothing here has been implemented, run, or measured. Code is an untested sketch. Mechanisms are functional analogues. The system is not claimed to be conscious or alive.

## Layout

```
docs/
  1-architecture.md        Integrated architecture, data flows, feedback loops
  2-frameworks.md          How the six frameworks are realized in the loop
  3-autoresearch-w.md      File contract, components, loop, adapters, campaign lifecycle
  5-eval-runner.md         Composite metric, Protect Gate, held-out split, acceptance tests
  6-failure-modes.md       Goodhart, drift, guard bypass, overfitting, other failures
campaigns/
  rr_engine/
    program.md             Starter program.md for Campaign 1 (RR engine)
engine/
  engine.py                Minimal reference-implementation sketch (untested)
```

## Read order

1. `docs/1-architecture.md`
2. `docs/2-frameworks.md`
3. `docs/3-autoresearch-w.md`
4. `campaigns/rr_engine/program.md`
5. `docs/5-eval-runner.md`
6. `docs/6-failure-modes.md`
7. `engine/engine.py`

## Design decisions (fixed)

Decisions C1 to C5 from the original brief are treated as fixed. In particular: lexicographic evaluation (Protect Gate first, then a geometric-mean score S), one target file per campaign, a single scalar metric, and the engine (not the agent) decides halts.

## Additions requiring human sign-off

See `docs/6-failure-modes.md`, section 6.6. The list includes a confirmation split, a calibration skill score, a golden judge set, a human relabel sample, a ledger prefix hash, and two-person review for proposals that touch Protect or halt conditions.

## Setting up a campaign (once the engine is implemented)

```
cd campaigns/rr_engine
git init && git add program.md && git commit -m "baseline program.md"
# add eval_runner.py, rr_policy.py, .gitignore; then:
chmod 444 eval_runner.py program.md
python ../../engine/engine.py .
```

Keep the engine outside the campaign directory (see section 3 of the docs).
