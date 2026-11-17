# 6. Failure modes and sign-off boundaries

## Known failure modes

- **Goodharting:** a proposal can optimize the toy evaluator without being
  useful in the intended world.
- **Drift:** fixtures, labels, or evaluator versions can change and make
  scores incomparable.
- **Guard bypass:** a weak Protect Gate can be gamed or can miss a harmful
  behavior outside its test surface.
- **Overfitting:** proposals can memorize the visible fixtures.
- **Evaluator compromise:** if proposal code can modify the evaluator or its
  inputs, the result is not trustworthy.
- **Operational ambiguity:** a timeout, crashed evaluator, or lost ledger must
  not be interpreted as success.
- **Human over-trust:** a passing score is not a readiness or safety verdict.

The reference engine fails closed on malformed evaluator output, evaluator
errors, an existing run lock, and a baseline Protect Gate failure. It does not
solve sandboxing or malicious evaluator code execution; campaigns must provide
their own isolation boundary.

## 6.6 Additions requiring human sign-off

The following remain design items and are not silently enabled by this
repository:

- a confirmation split;
- a calibration skill score;
- a golden judge set;
- a human relabel sample;
- a ledger prefix hash;
- two-person review for proposals that touch Protect or halt conditions.

Changes to these boundaries should be explicit, reviewed, and recorded outside
the automated proposal loop before implementation.

## What a passing run means

A passing reference run means only that the local evaluator returned a valid
result and the engine applied its comparison rule. It is not a certification,
deployment approval, or claim about AGI+W.
