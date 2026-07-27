# Final Inference Pipeline Design

- Date: 2026-07-27
- Status: approved architecture

## Decision

The online bakery-scanner inference pipeline is fixed as follows:

```text
Scan image
  -> Detector: D-FINE
  -> Verifier: confirm each candidate represents exactly one bread
  -> Classifier: RepViT
  -> DINOv3 recheck only for low-confidence or confusable classifications
  -> item, quantity, position, confidence, and decision path
```

RTMDet is not part of the final online inference path. It may only be used in
offline experiments if a later, independently evaluated change is proposed.

## Stage contracts

### Detector: D-FINE

D-FINE proposes every plausible bread location. Its output is candidate
evidence, not a final item count or product classification. Every encoded
input is first EXIF-transposed and converted to RGB; that visually oriented
image is the original-image coordinate frame. Candidate boxes return to this
canonical frame after model resize, letterbox, or perspective normalization is
reversed. EXIF orientation is never reversed during ordinary inference.

### Verifier

The verifier assesses each candidate as `invalid`, `exactly_one`, `partial`,
or `multiple`. Only `exactly_one` candidates become final object regions.
It owns removal of non-bread detections and resolution of duplicate, split,
and merged boxes; it does not classify product type.

### Classifier: RepViT

RepViT receives only verified regions. It returns ranked product candidates,
calibrated confidence, and the separation between the leading candidates.
Direct classification is permitted only when the versioned calibration
criteria are met.

### Conditional DINOv3

DINOv3 is invoked only when RepViT confidence or candidate separation does
not meet the calibrated direct-decision criteria, including declared
confusable product pairs. It confirms a registered product only with
sufficient reference-match evidence; otherwise the result is `Unknown`.

## Final result contract

Each final object contains a registered product ID or `Unknown`, an in-bounds
canonical visual-original-image box in `[x_min, y_min, x_max, y_max]` form, decision
confidence, and one decision path: `classifier_direct`, `dinov3_recheck`, or
`unknown`. Product-level quantities must sum to the number of final object
regions.

## Release requirements

The final runtime must measure end-to-end and per-stage GPU latency after
warm-up, including p50/p95 and DINOv3 invocation rate. The 0.5 second target
does not justify accuracy regression. Before production approval, the locked
evaluation set must have zero misclassifications, misses, duplicates, and
non-target detections within its validated operating range.
