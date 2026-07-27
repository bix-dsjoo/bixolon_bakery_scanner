# Detector-Only Postprocess Design

**Status:** Approved design, pending implementation-plan review  
**Scope:** Existing 299-image locked OOF evaluation set only

## Goal

Test whether D-FINE-N 640 alone can reach zero errors at IoU 0.50 and IoU 0.75 on the 299-image grouped OOF evaluation, without a learned verifier. Measure warm RTX 5080 end-to-end p95 latency and require it to be at most 0.5 seconds.

The outcome may be that the detector-only approach fails the zero-error gate. That is a useful result and must not be hidden or converted into an operational 100% claim.

## Minimal Pipeline

~~~text
Input image
  → D-FINE-N 640 native decoder output
  → score threshold selected by four-fold cross-fit
  → overlap-aware score decay (Soft-NMS), not destructive hard NMS
  → deterministic final score threshold
  → source-coordinate boxes and count
~~~

The evaluation will compare D-FINE native output, existing recall-first raw candidates, and Soft-NMS variants. It will select one policy for each target fold using only the other four folds.

## Why This Scope

D-FINE is already a localization-focused real-time DETR. DETR set prediction is designed to produce a final set without a hand-built multi-stage proposal classifier. The current large raw-candidate count is an artifact of the recall-first top-30 export, not proof that a two-model verifier is required.

Soft-NMS is permitted as a score-decay policy because it retains overlapping candidates rather than deleting them solely due to overlap.

## Cross-Fit Policy

For each target fold:

1. Read only the other four folds' completed immutable D-FINE receipts and predictions.
2. Enumerate a finite grid of score thresholds and Soft-NMS parameters.
3. Rank policies by IoU .75 misses, false positives, duplicates, split errors, and merge errors; use IoU .50 errors next.
4. Apply the selected policy exactly once to the target fold.
5. Emit per-image source-coordinate boxes, a policy receipt, and a deterministic error report.

The target fold is never used to choose its own score or overlap parameter.

## Error Analysis

The report must include all errors at IoU .50 and .75, by fold and image:

- misses
- false positives
- duplicates
- split errors
- merge errors
- candidate score and selected policy
- before/after overlay for every non-exact image

The analysis will decide whether the remaining errors are output-policy errors or unavailable-separation evidence. It will not invent a learned verifier or claim that unobserved overlap conditions are solved.

## Performance Gate

Measure after warm-up on RTX 5080:

- decode and postprocess latency
- total detector-plus-postprocess latency
- mean, p50, and p95 over the defined evaluation images

The target is total warm p95 <= 0.5 seconds. If an accuracy-preserving policy cannot meet that target, report the measured tradeoff; do not discard boxes for speed.

## Acceptance

A detector-only release is accepted only if all 299 OOF images have:

1. zero misses, false positives, duplicates, split errors, and merge errors at both IoU .50 and .75;
2. valid source-coordinate boxes;
3. exact image-level counts;
4. immutable detector, policy, evaluation, overlay, and timing evidence;
5. development-only scope text naming absent real empty-tray, overlap, and obstruction data.

If any gate fails, the next work is targeted data/error analysis, not automatic expansion to the previous cascade.
