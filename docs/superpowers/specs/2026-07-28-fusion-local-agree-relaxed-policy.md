# Fusion-local agreement relaxed classification policy

**Status:** approved on 2026-07-28

## Decision

For registered SKU classification, automatically emit the fusion ranker's Top-1
only when it equals the DINOv3 local-evidence Top-1.  Otherwise emit
`Unknown` with the ranked Top-3 candidates.

The rule is named `fusion_local_agree_v1` and is carried in an immutable,
hash-pinned fusion-policy artifact (schema version 2).  The previous
`risk_threshold_v1` artifacts remain readable so an explicit rollback only
requires restoring the policy path and SHA-256 in configuration.

## Scope and safety boundary

This changes only the registered-SKU classifier acceptance rule.  Detector,
Box Assurance, final component resolution, non-target rejection, and their
zero-error gates are unchanged.  A disagreement remains abstained rather than
being resolved by a plurality vote.

## Observed operating point

On the evaluated evidence, the rule yielded 474/508 correct automated results
with 1 wrong automatic label on Batch1 and 502/522 correct automated results
with 2 wrong automatic labels on Batch2.  The observed Batch2 automatic error
rate is 2/504 (0.397%) and correct automatic coverage is 96.169%.

Batch2 was inspected while selecting this policy; it must therefore be treated
as policy-selection evidence, not as an untouched release gate.  Promotion
requires an independently collected, capture-group-disjoint evaluation set.

## Runtime behavior

The rule uses evidence already calculated for the strict path and adds no model
invocation.  It preserves the existing `FUSION_RANKED` decision path for an
accepted SKU.  Risk remains computed and recorded by the policy contract for
diagnostics, but it does not decide acceptance under this rule.
