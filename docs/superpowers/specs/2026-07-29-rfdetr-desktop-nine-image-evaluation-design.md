# RF-DETR-L desktop pipeline: nine-image evaluation design

## Goal

Evaluate the nine fixed Batch2 images with the already frozen RF-DETR-L,
post-processing, RepViT-20, and conditional DINOv3 ViT-S/16 pipeline from
`C:\workspace\bakery_ai_scanner`.  This is a quality comparison run, not a
retraining, recalibration, release, or CPU-latency optimization claim.

## Scope

- Inputs are the existing fixed Batch2 profile: E/M/H, three images each.
- The detector is the immutable RF-DETR-L final-development checkpoint named by
  `bakery_ai_scanner/configs/desktop_pos_20.yaml`.
- Detector output is normalized only by the source repository's RF-DETR adapter
  and its bound M calibration threshold: background removal, finite-geometry
  validation, frame clipping, and thresholding.  No new NMS, score threshold,
  crop rule, or geometry heuristic is introduced.
- Every accepted product crop uses the frozen RepViT-20 checkpoint.  Its existing
  gate invokes DINOv3 ViT-S/16 global/local support evidence only for ambiguous
  RepViT evidence, and returns `UNKNOWN` when its published gate cannot justify
  a SKU.
- The evaluation writes per-image machine-readable results and rendered overlays
  to a new timestamped output directory, preserving input images and source
  artifacts.

## Explicit exclusions

- Do not use D-FINE, the legacy four-state MobileNet assurance adapter,
  ConvNeXt assurance, the component-union resolver, or their thresholds.
- Do not train, fine-tune, recalibrate, alter the immutable RF-DETR checkpoint,
  modify the DINO/RepViT support bank, or use the locked evaluation set.
- Do not claim a CPU speed improvement from this run.  RF-DETR-L latency must be
  measured separately after quality is established.

## Data flow

```text
fixed Batch2 image
  -> EXIF-corrected RGB frame
  -> frozen RF-DETR-L
  -> source RF-DETR adapter plus M-bound detector threshold
  -> padded crop
  -> RepViT-20
  -> conditional DINOv3 ViT-S/16 global/local evidence
  -> SKU or UNKNOWN, object result, overlay
```

The RF-DETR adapter preserves the canonical visual frame.  It discards
background predictions, rejects malformed geometry, clips valid edge-crossing
boxes to the image frame, and emits product candidates in deterministic order.
The classifier does not promote an uncertain candidate to an SKU.

## Verification and deliverables

Before processing images, the run must preflight the config and prove the
checkpoint, detector calibration, RepViT manifest, DINO weight, DINO support
manifest, and gate bindings are internally consistent.  The nine input names
must exactly match the fixed Batch2 profile and produce exactly nine result
records.  Each record must contain canonical-frame boxes, detector score, SKU
or `UNKNOWN`, decision reason, and timing.

Deliver the generated overlay paths and a concise summary of accepted/UNKNOWN
objects.  If a source artifact cannot be verified or the pipeline raises a
stage error, publish no partial final report and report the failure boundary.
