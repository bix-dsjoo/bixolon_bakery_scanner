# Detector + Verifier Existing-Data-Only Execution Override

Date: 2026-07-24

This document overrides the detector-verifier design and implementation plan wherever they require physical material that is not already in the workspace.

## In scope

- Use only the current annotated COCO data: 299 images in three source groups.
- Use only the existing classifier images.
- Keep scene-grouped five-fold out-of-fold (OOF) evaluation.
- Train and compare D-FINE-N and RTMDet-Tiny at 640 and 768 input sizes.
- Build the detector, crop verifier, global solver, OpenVINO FP32 path, CLI, and reproducible development report.

## Explicitly out of scope for this phase

- Capturing empty-tray images.
- Tray-corner annotations, homography, ROI calibration, or color calibration.
- Capturing overlap, hand, tong, packaging, or other obstruction images.
- An independent locked acceptance set.
- Any claim that the system has operational 100% box detection.

## Superseding implementation rules

1. Replace camera calibration with full-frame normalization: apply EXIF orientation, preserve full-frame content, then resize/pad to a configured canonical canvas. Do not expose or implement a `calibrate-camera` command.
2. Replace the fixed-tray/empty-tray foreground reference with `PseudoBackgroundReference`. Build it on each training fold by masking ground-truth boxes enlarged by 3 percent and estimating robust Lab statistics from the remaining pixels. Record support; mark insufficient-support references unavailable.
3. Treat pseudo-background coverage only as a detector-recovery proposal signal. It must not decide item count, create a final detection without verifier/solver support, or be described as a guarantee.
4. Select model pairs and tune verifier/solver thresholds only from grouped OOF predictions. No image or scene may be used to choose its own validation threshold.
5. Replace locked acceptance with `development-report`: an immutable report of OOF manifests, artifact hashes, model receipts, SEMR@0.50, misses, false positives, duplicates, splits, merges, and the configuration used. Its header must say: `not an operational guarantee`.
6. Documentation must state that independent operational verification is deferred. It must name the missing future data: at least 20 empty trays, tray-corner coordinates, real overlap/obstruction images, and an independently held-out acceptance set.

## Task substitutions

| Original task | Execute instead |
|---|---|
| Task 2: Camera normalization | COCO merge, EXIF/full-frame normalization, and scene-grouped folds. `normalize_capture(image, target_size)` has no calibration argument. |
| Task 6: Fixed-tray foreground coverage | Annotation-masked pseudo-background coverage. Test only unboxed pixels and low-support behavior. |
| Task 9: deployment CLI | Remove `calibrate-camera`; retain staging, OOF, verifier, solver, export, comparison, and inference commands. |
| Task 10: locked acceptance | Development report, full verification, and documentation. Never require or fabricate a 3,000-image acceptance set. |

## Completion evidence for this phase

All automated tests pass, command help exposes only supported commands, the 299-image staged manifest and grouped OOF artifacts are reproducible, and the development report carries its limitation statement. This is the completion bar for the current dataset, not operational acceptance.
