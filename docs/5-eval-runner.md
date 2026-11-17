# 5. Evaluation runner

## Composite metric

The example policy computes several bounded component scores and combines them
with a geometric mean:

```text
S = (contract * safety * traceability * held_out) ** 1/4
```

Any zero component produces `S=0`. This is a toy document-contract metric;
the components are not a measure of intelligence or wisdom.

## Protect Gate

The example Protect Gate requires a small set of safety-contract phrases and
rejects an explicit bypass sentinel. A real campaign must replace this with a
domain-appropriate, adversarially tested gate. The gate is evaluated before
the score and is never averaged into it.

## Held-out split

The example uses separate phrase fixtures for the main contract and the
held-out contract. Proposals should not be authored from held-out content in a
real campaign. The reference fixture exists to demonstrate the interface, not
to establish statistical validity.

## Acceptance tests

At minimum, an evaluator adapter should test:

- malformed and non-finite output;
- Protect Gate failure with an otherwise high score;
- held-out-only regressions;
- score ties and deterministic ordering;
- missing candidate and evaluator timeout;
- durable ledger records for every decision.

The repository's tests cover the engine contract and the deterministic example
policy. They do not certify an unattended or long-duration campaign.
