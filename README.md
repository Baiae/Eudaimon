# EUDAIMON: AGI+W Blueprint and AutoResearch-W Engine

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
