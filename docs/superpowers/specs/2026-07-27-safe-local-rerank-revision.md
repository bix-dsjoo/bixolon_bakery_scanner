# Safe Local Rerank Revision

This revision supersedes the automatic-global/local confirmation wording in the
earlier local-rerank design.

```text
CanonicalImage + verified foreground box
  -> 5% / 10% / 15% crops
  -> RepViT probability, margin, crop agreement, prototype OOD distance
       -> direct SKU only when every direct gate passes
       -> otherwise DINO global 20-SKU retrieval
            -> candidates = DINO Top-5 union RepViT Top-2 (at most seven)
            -> foreground-aware local patch matching
            -> Top-3 rerank
            -> calibrated safe gate -> SKU
            -> otherwise Unknown + Top-3 + unknown_reason
```

## Safety rules

- Local similarity never independently confirms a SKU. It contributes to a
  calibrated DINO-family evidence vector and requires RepViT/DINO-family
  agreement.
- RepViT direct acceptance requires probability, margin, crop agreement, and
  prototype OOD gates. Softmax confidence alone is insufficient for Unknown.
- A verifier foreground mask is preferred. Until supplied, use an eroded
  verified box; record that background can remain inside it.
- Each SKU local bank is a deterministic, source-balanced coreset of the same
  maximum size (default 512, configurable up to 1024). Evaluation captures and
  their augmentations are never bank sources.
- For each query patch, average the top three reference similarities. Compute a
  trimmed mean over query patches after down-weighting shared crust/background
  patches. Candidate-only softmax is ranking-only, never final confidence.
- The final confidence calibrator consumes RepViT probability/margin,
  crop disagreement, OOD distance, DINO global absolute score/margin, local
  raw score/margin, and matched-patch count/ratio.
- Batch1 develops artifacts and thresholds; Batch2 is locked. A candidate union
  cannot repair a truth SKU absent from both DINO Top-5 and RepViT Top-2; such
  cases require support/training coverage before release.
