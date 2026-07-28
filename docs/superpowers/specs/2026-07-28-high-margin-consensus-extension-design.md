# High-margin global consensus extension

**Status:** approved on 2026-07-28

## Goal

Reduce classifier `Unknown` results without accepting a model-disagreement
case solely because a majority agrees.

## Decision rule

The successor policy accepts a registered SKU if either condition is true:

1. Fusion Top-1 equals DINOv3 local Top-1; or
2. Fusion Top-1, RepViT Top-1, and DINOv3 global Top-1 are identical, and
   the fusion ranker's first-to-second score margin is at least `0.85`.

All other cases remain `Unknown`.  Ties use the existing deterministic SKU-ID
ordering.  The policy is versioned and hash pinned; a previous policy can be
restored by changing the configured artifact path and SHA-256.

## Selection boundary

The `0.85` floor was selected from Batch1 development evidence.  Relative to
the preceding local-agreement rule, it accepts three additional correct Batch1
results with no additional observed FP.  The observed Batch2 result is two
additional correct automated results with no additional observed FP.

Batch2 has already informed policy selection and is not an untouched release
gate.  A capture-group-disjoint evaluation set is required before broad
production promotion.

## Scope

This changes only registered-SKU classification.  Detector, Box Assurance,
component resolution, non-target rejection, and all upstream safety gates are
unchanged.  It uses scores already computed by the existing fusion path, so it
does not add a model invocation.
