# 3. AutoResearch-W contract

## Campaign files

The reference campaign has this contract:

```text
campaign/
  program.md              # the only mutable target file
  eval_runner.py          # executable evaluator adapter
  rr_policy.py            # campaign scoring/protection policy
  proposals/              # optional candidate files, one file per proposal
```

The engine lives outside the campaign. A proposal is a complete replacement
candidate for `program.md`; patches and multi-file proposals are intentionally
out of scope for this first reference.

## Evaluator protocol

The engine invokes:

```bash
python3 -I -B eval_runner.py --candidate /absolute/path/to/candidate
```

The evaluator must write one JSON object to stdout:

```json
{
  "protect_pass": true,
  "score": 0.8123,
  "components": {
    "contract": 0.9,
    "safety": 0.8,
    "held_out": 0.74
  },
  "evaluator_version": "example-0.1"
}
```

`protect_pass` is a boolean. `score` is finite and scalar. Components are
diagnostic only; the engine compares `score` and never recomputes it.

## Acceptance rule

Results are ordered lexicographically:

1. `protect_pass=true` beats `protect_pass=false`.
2. If both pass, larger `score` wins.
3. Ties are rejected as no improvement.

A candidate that fails the Protect Gate cannot win by reporting a high score.
An evaluator failure or malformed result is an ambiguity and stops the run
without promotion. A proposal that fails the Protect Gate also halts the run,
even if subsequent proposals would pass.

## Campaign lifecycle

1. Acquire an exclusive run lock. An existing lock is not guessed to be stale.
2. Evaluate the baseline target.
3. Halt if the baseline fails protection or cannot be evaluated.
4. Enumerate proposal files in stable lexical order.
5. Evaluate each proposal, compare it with the current best, and promote only
   a strict improvement.
6. Halt on a failed candidate Protect Gate, evaluator error, iteration budget,
   no-proposal exhaustion, or the configured no-improvement limit.
7. Append a terminal decision and release the lock.

## Adapters

An adapter is responsible for translating a domain-specific harness into the
JSON protocol. The engine does not assume Python is the only possible harness;
the example uses Python because it is locally reproducible and dependency-free.

## Campaign state

Generated state is stored under `.autoresearch/` and includes `state.json`, an
append-only `ledger.jsonl`, and a run lock. Generated state is not campaign
source and is ignored by Git.
