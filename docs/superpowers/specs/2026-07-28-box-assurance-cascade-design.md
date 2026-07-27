# Box Assurance Cascade Design

**Status:** Proposed and approved for specification review  
**Scope:** Existing 299-image locked evaluation set only

## Goal

On the locked 299-image evaluation set, produce exactly one final bread box per real bread with zero misses, duplicates, non-target boxes, and merged boxes at both IoU 0.50 and IoU 0.75. Measure warm GPU end-to-end p95 latency at or below 0.5 seconds on the current RTX 5080.

This is not an operational 100% claim. The dataset has no real empty-tray, overlap, or obstruction examples, so those conditions remain outside the verified scope.

## Pipeline

```text
Input image
  → D-FINE-N 640, score >= 0.001, per-image/source top 30
  → proposal relation graph
  → MobileNetV4 Box Assurance batch pass
  → conditional ConvNeXt-Tiny Box Assurance pass
  → duplicate/partial/multiple resolution
  → final source-coordinate boxes or Unknown
```

The detector is recall-first. It must not discard low-score candidates before the assurance stages.

## Proposal Relation Graph

Nodes are D-FINE candidates in original image coordinates. Edges connect boxes that have high IoU, containment, or close centers. An edge is evidence of a possible duplicate, partial crop, or merge; it is never by itself permission to suppress a candidate.

Hard NMS is not the final decision mechanism because it can remove two genuinely overlapping breads. It may only provide a deterministic, non-destructive grouping hint.

## Box Assurance Outputs

Every evaluated candidate has:

- state: `INVALID`, `EXACTLY_ONE`, `PARTIAL`, or `MULTIPLE`
- `exactly_one_probability`
- `box_quality`: calibrated probability that the final box meets IoU 0.75
- `box_delta`: source-coordinate offset applied to the candidate box
- model provenance and inference path

MobileNetV4 is the first pass. ConvNeXt-Tiny is executed only when MobileNetV4 confidence or box quality is insufficient, when its state is `PARTIAL` or `MULTIPLE`, or when graph evidence conflicts with its state.

## Graph Resolution

- `INVALID`: remove from final boxes.
- `EXACTLY_ONE`: apply its box delta; within a duplicate graph component, retain only the highest-quality compatible candidate.
- `PARTIAL`: apply the delta, rebuild its local graph relationships, and evaluate again.
- `MULTIPLE`: recover compatible separated candidates already present in the detector proposal graph. If no independent candidate exists for each bread, return `Unknown` for the unresolved component rather than counting a merged box.
- MobileNetV4/ConvNeXt-Tiny conflict: use ConvNeXt-Tiny only if its confidence and quality thresholds pass; otherwise retain `Unknown`.

An `Unknown` is never silently counted as a bread. It is an error for the locked-set zero-error gate.

## Training and Cross-Validation

Use the existing grouped five-fold split without mixing `(capture_batch, scene_number)` across train and validation.

For target fold `k`:

1. Train both assurance backbones only with the other four folds.
2. Generate detector candidates only from held-out fold `k`.
3. Infer candidate states, quality, and deltas on fold `k`.
4. Select detector, first-pass, fallback, graph, and quality thresholds only with the other four folds.
5. Evaluate fold `k` once with its independently selected policy.

The combined OOF result covers each staged image exactly once. Model, preprocessing, crop-generation, threshold, and receipt hashes are immutable report inputs.

## Performance Contract

Measure after GPU warm-up on RTX 5080:

- image preprocessing
- D-FINE-N 640
- proposal graph
- MobileNetV4 batch inference
- ConvNeXt-Tiny fallback inference
- graph resolution
- total E2E latency

Record mean, p50, p95, and conditional ConvNeXt execution rate. The gate is E2E p95 <= 0.5 seconds. Accuracy is never reduced merely to satisfy latency; unresolved cases become `Unknown`.

## Locked-Set Acceptance Gate

All of the following must hold:

1. At IoU 0.50 and 0.75: misses, duplicates, false positives, split errors, and merge errors are all zero.
2. Every image's final box count equals its ground-truth bread count.
3. No final box is `Unknown`.
4. Every final box preserves valid original-image coordinates.
5. RTX 5080 warm E2E p95 is at most 0.5 seconds.
6. The immutable report declares `operational_guarantee: false` and lists absent real empty-tray, overlap, and obstruction data.

