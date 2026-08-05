# RF-DETR-L bread GPU FP16 OOF reference

This directory intentionally contains no model weights, predictions, staged
images, or run receipts. Those artifacts are external and must be bound by ID,
size, and SHA-256 in an artifact manifest after a successful run.

`tools/train/train_rfdetr_bread_oof.py` trains only the `train` role of each
immutable 15+5 split, with class map `{1: bread}`, device `cuda:0`, and seed
`20260803 + fold_index`. Calibration rows may select a detector threshold;
evaluation rows are never used for training or selection. Evaluation uses
deterministic one-to-one IoU 0.50 matching and reports misses, duplicates,
non-target detections, splits, and merges. Since this corpus has no negative
scenes, non-target rejection remains unverified.

When the RF-DETR training runtime is unavailable, the trainer writes only an
`unverified_missing_rfdetr_train_runtime` receipt. It does not create a
checkpoint, predictions, calibration evidence, or claimed fold result.
