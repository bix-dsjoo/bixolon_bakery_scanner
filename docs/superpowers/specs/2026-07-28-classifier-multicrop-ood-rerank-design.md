# Classifier Multi-Crop OOD and Candidate Rerank Design

- Date: 2026-07-28
- Status: approved for implementation planning
- Scope: classification after the final component resolver has produced a `VerifiedBreadBox`

## Goal

Classify only verified single-bread regions with a deterministic, accuracy-first
decision path. RepViT-M1 directly confirms a SKU only when multi-crop
classification and in-distribution evidence are all safe. All other regions
receive a conditional DINOv3 recheck. A recheck that cannot establish a safe
SKU returns `Unknown` together with a ranked Top-3 and explicit reasons.

This design changes classification only. Detector, Box Assurance, final
component resolution, and their original-image boxes remain unchanged.

## Inputs and Invariants

The runtime consumes a `CanonicalImage` and a `VerifiedBreadBox` from the
final component resolver. The box is an in-bounds original-image coordinate
in `[x_min, y_min, x_max, y_max]` form and denotes exactly one bread.

The runtime makes three RGB crops from that box, with 5%, 10%, and 15%
symmetric padding. Padding is clipped to the source image boundary; crop order
is fixed at 5%, 10%, then 15%. Each model applies its versioned 224x224
preprocessing to every crop.

No product mask, segmentation model, attention-derived mask, or mask-restricted
patch matching is part of this scope. DINOv3 uses only the global embedding of
the padded box crops.

## Runtime Flow

```text
CanonicalImage + VerifiedBreadBox
  -> 5% / 10% / 15% RGB crops
  -> RepViT-M1 scores each crop
       -> class probabilities and top-1/top-2 margin
       -> top-1 crop agreement
       -> normalized feature distance to each SKU prototype
  -> all direct gates pass?
       -> SKU, decision_path=repvit_direct
       -> otherwise DINOv3 recheck
            -> global search across all 20 SKU prototypes
            -> candidates = ordered union(DINO Top-5, RepViT Top-2)
            -> deterministic candidate-only rerank
            -> Top-3 from reranked candidates
            -> all recheck gates pass?
                 -> SKU, decision_path=dinov3_confirmed
                 -> otherwise Unknown, decision_path=unknown_top3
```

The DINOv3 runner is lazy: it is not loaded or executed for a RepViT direct
confirmation. The runtime records its invocation rate and per-stage timings.

## RepViT Multi-Crop Evidence

For each crop, RepViT-M1 produces a 20-SKU softmax vector and a penultimate
feature vector. The runtime averages the three probability vectors in crop
order and derives the canonical top-1, top-2, and margin from the averaged
vector. It L2-normalizes every feature, averages them, normalizes the average,
and computes cosine distance to the versioned per-SKU RepViT prototypes.

`crop_agreement` is the fraction of the three crop top-1 predictions matching
the canonical averaged top-1. It is 1.0 only for three-way agreement. The
top-1 prototype distance is the OOD evidence; it does not independently
assign a product SKU.

RepViT confirms directly only when every calibrated direct gate passes:

1. top-1 calibrated probability is at least `repvit_min_probability`;
2. calibrated top-1/top-2 margin is at least `repvit_min_margin`;
3. `crop_agreement` is at least `repvit_min_crop_agreement`;
4. the top-1 prototype distance is at most `repvit_max_prototype_distance`;
5. the artifact, class map, prototype support, scores, and features validate.

All thresholds, temperatures, and prototype-distance calibration details are
stored in a versioned development-only calibration artifact. They are never
hardcoded in the runtime and are never selected using the locked acceptance
set.

## DINOv3 Candidate Rerank

When a direct gate fails, DINOv3 produces one normalized global embedding by
averaging the three crop embeddings after per-crop L2 normalization and then
normalizing again. It scores all 20 SKU prototypes by cosine similarity.

The rerank candidate set is the deterministic union of the DINO global Top-5
SKU IDs and the RepViT averaged-probability Top-2 SKU IDs. A SKU appearing in
both sets occurs once. Candidate ordering before reranking is descending DINO
score, then descending RepViT probability, then ascending SKU ID; it exists
solely to make ties reproducible.

For each candidate, the calibration artifact transforms the RepViT probability
and DINO similarity onto calibrated comparable score scales and produces a
candidate rerank score:

```text
rerank_score(sku) =
  repvit_weight * calibrated_repvit_score(sku)
  + dinov3_weight * calibrated_dinov3_score(sku)
  + agreement_bonus(sku)
```

`agreement_bonus` may be nonzero only when the SKU is both model top-1 and is
defined entirely by the calibration artifact. Candidates are sorted by rerank
score descending, then DINO similarity descending, then RepViT probability
descending, then SKU ID ascending. The first three distinct candidates are the
Top-3 returned for an `Unknown` result.

DINOv3 confirms the reranked top SKU only when every calibrated recheck gate
passes:

1. DINO global top score meets `dinov3_min_score`;
2. the reranked top-1/top-2 margin meets `rerank_min_margin`;
3. the reranked top SKU has adequate support evidence;
4. the required model-agreement gate passes, when enabled by calibration;
5. artifact, support, feature, and score validation succeeds.

There is no fallback that promotes the RepViT or DINO top-1 when a recheck
gate fails.

## Decision Contract

Every final object retains its verified original-image box and returns exactly
one of these decision paths:

```json
{
  "decision": "sku",
  "sku_id": 6,
  "confidence": 0.98,
  "decision_path": "repvit_direct",
  "top3": [],
  "unknown_reason": []
}
```

`dinov3_confirmed` uses the reranked calibrated top-1 confidence. `Unknown`
uses the best reranked candidate score when DINO completed, or the best
RepViT-calibrated candidate score when DINO failed before producing valid
scores. That score ranks candidates; it is not an asserted probability that
the object is unknown.

```json
{
  "decision": "unknown",
  "sku_id": null,
  "confidence": 0.41,
  "decision_path": "unknown_top3",
  "top3": [
    {"rank": 1, "sku_id": 6, "score": 0.72},
    {"rank": 2, "sku_id": 5, "score": 0.68},
    {"rank": 3, "sku_id": 19, "score": 0.44}
  ],
  "unknown_reason": ["repvit_low_margin", "model_disagreement"]
}
```

`unknown_reason` is a sorted, duplicate-free list from this controlled
vocabulary:

- `repvit_low_confidence`
- `repvit_low_margin`
- `crop_disagreement`
- `repvit_ood`
- `dinov3_low_score`
- `rerank_low_margin`
- `insufficient_support_evidence`
- `model_disagreement`
- `artifact_failure`
- `invalid_model_output`

An `Unknown` result always carries exactly three distinct registered SKU
candidates when valid candidates are available. A malformed or unavailable
artifact fails closed with `artifact_failure`; no SKU is emitted.

## Calibration and Evaluation

Calibration data is grouped by capture scene so correlated crops, rotations,
and views cannot cross train and validation partitions. It selects direct and
recheck gates in this priority order:

1. zero automatic SKU errors;
2. zero fallback Top-3 omissions for registered SKUs;
3. zero assisted failures;
4. maximum automatic coverage;
5. minimum DINOv3 invocation rate.

The locked 299-image acceptance set is evaluation-only. Any parameter change,
including crop agreement, prototype distance, rerank weights, support gates,
or thresholds, requires calibration on development evidence and evaluation on
a newly locked set.

Reports include each SKU, the existing/new SKU split, declared confusable
pairs, lighting/rotation/scale/padding slices, model agreement slices, and
registered versus non-target inputs. They report automatic precision, coverage,
fallback Top-3 recall, assisted success, `Unknown` reasons, DINO invocation
rate, end-to-end p50/p95, and RepViT/DINO/rerank stage timings.

## Required Tests

Unit tests cover crop clipping and order, three-crop aggregation, agreement
calculation, feature-prototype OOD distance, deterministic Top-5/Top-2 union,
tie-breaking, all direct and recheck gates, each `unknown_reason`, invalid
artifacts, non-finite outputs, and output serialization.

Integration tests assert that only `VerifiedBreadBox` values enter the
classifier, direct-safe inputs never invoke DINOv3, unsafe inputs invoke it
once, and final item aggregation preserves box count and original coordinates.

Regression and performance tests must report the accuracy and timing gates in
the repository instructions. No release claim is valid until the applicable
locked-set zero-error conditions and RTX 5080 warm end-to-end p95 of at most
0.5 seconds are measured.
