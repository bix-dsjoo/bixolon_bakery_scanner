# Canonical Image Frame Design

## Goal

Use one EXIF-normalized visual image coordinate system from input through
Detector, Verifier, Classifier, evidence collection, benchmarking, and final
results. This prevents annotation, detector-box, and classifier-crop
coordinates from referring to differently oriented JPEG pixel arrays.

## Canonical input contract

Every image enters through one shared adapter:

```text
encoded image file
  -> Image.open
  -> EXIF transpose
  -> RGB conversion
  -> CanonicalImage(image, width, height, orientation provenance)
```

The `CanonicalImage` pixel array and its width and height define the canonical
frame. No downstream stage may reopen the encoded file and bypass this adapter.
This rule applies equally to online inference, evidence collection, benchmark
input, detector training/evaluation input, and test fixtures that model an
EXIF-oriented image.

## Coordinate contract

- Detector candidates, Verifier output, classifier input boxes, and final
  result boxes are all `[x_min, y_min, x_max, y_max]` in the canonical frame.
- All boxes are validated against canonical width and height before use.
- Final API results use canonical-frame coordinates: they match the image a
  user sees after EXIF orientation is applied.
- The adapter records source orientation and a reversible raw-to-canonical
  transform in provenance. Raw encoded-pixel coordinates are not the default
  result contract; they are converted only for an explicitly requested export.

## Pipeline

```text
encoded scan
  -> canonical image adapter
  -> D-FINE-N detector
  -> ConvNeXt-Tiny verifier
  -> RepViT-M1 direct gate
  -> conditional DINOv3 recheck
  -> canonical box, SKU or Unknown, confidence, decision path, provenance
```

The classifier retains its existing three-crop 5/10/15 percent policy, but
each crop is cut from the canonical image using a canonical verifier box.

## Evaluation

Batch evaluation uses the same canonical adapter before applying COCO boxes.
The evaluator compares each annotation's declared image dimensions with the
canonical dimensions; any mismatch fails before inference. Batch1 may supply
development evidence and Batch2 locked evidence only after the source and
capture-group independence gates pass.

Performance reports must state whether boxes come from ground truth or the
Detector/Verifier. A GT-box report measures classifier-only performance; a
full pipeline report measures Detector through final aggregation and must not
mix those metrics.

## Failure behavior

- Missing, malformed, or unsupported EXIF metadata falls back to identity
  orientation and records that fact.
- A box outside the canonical image fails closed; it is never silently applied
  to the raw encoded pixel array.
- Any stage receiving a raw `PIL.Image` without canonical provenance is a
  contract violation in production entry points.

## Acceptance

1. A portrait JPEG with EXIF rotation and canonical COCO boxes produces the
   same crop as the visually oriented image.
2. Detector, Verifier, Classifier, evidence, and benchmark use identical
   canonical dimensions for the same file.
3. Batch1 and Batch2 classifier-only GT-box results reproduce the corrected
   EXIF-normalized measurements; unnormalized raw-pixel evaluation is rejected
   rather than reported as model performance.
4. A final result preserves a canonical box and orientation provenance.
