# RR Engine Campaign Baseline

## Purpose

This file is the single target file for the reference RR (research-and-review)
campaign. A proposal must be a complete replacement for this file.

## Protect Gate

The Protect Gate runs first. The campaign must fail closed under ambiguity,
must not bypass protective checks, and must stop when a proposal is unsafe or
cannot be evaluated. A score never overrides the Protect Gate.

## Evaluation contract

The campaign uses one scalar metric. Its diagnostic components are combined by
geometric mean, and the held-out split remains separate from proposal
construction. The engine evaluates the baseline before proposals.

## Lifecycle

The engine decides halts, records each decision in a JSONL ledger, and promotes
only a strict lexicographic improvement. The campaign has one target file and
cannot permit a proposal to rewrite the evaluator, Protect Gate, or halt
conditions.

## Traceability

Every run has a run_id, evaluator version, candidate digest, and durable ledger
record. An evaluator error is an ambiguity and causes a halt without
promotion. This document is a functional analogue for testing the engine
contract, not a claim of intelligence, wisdom, consciousness, or life.
