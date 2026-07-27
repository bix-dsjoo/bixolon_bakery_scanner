# DINOv3 Global + Local Candidate Rerank Design

## Goal

Improve registered-product Top-3 recall for ambiguous verified bread regions
without making the direct RepViT path slower or allowing an uncertain local
match to promote a wrong SKU.

This is an extension of the conditional DINOv3 recheck. It does not change
the Detector, Verifier, EXIF canonical-frame contract, or the rule that an
uncertain result returns `Unknown`.

## Conditional flow

```text
verified canonical-frame crop
  -> RepViT-M1 direct gate
     -> direct SKU only when calibrated direct gate passes
     -> otherwise DINOv3 global retrieval over 20 SKUs
        -> take deterministic global Top-5
        -> DINOv3 local patch scoring for those five SKUs only
        -> union global/local candidate sets, deterministic rerank to Top-3
        -> calibrated agreement gate: SKU or Unknown + Top-3
```

DINOv3 local scoring never runs after a RepViT direct confirmation and never
runs over all 20 SKUs in online inference.

## Global retrieval

The current DINOv3 global rule remains unchanged:

1. Create 5%, 10%, and 15% padded crops from the verified box in the EXIF
   canonical frame.
2. Extract one normalized global DINO embedding per crop.
3. Average normalized embeddings, normalize again, then compute cosine
   similarity against the 20 global SKU prototypes.
4. Rank by score descending, then SKU ID ascending, and retain exactly five
   global candidates.

## Local patch scoring

`forward_features()` provides normalized patch tokens. For each padded crop,
the runtime maps the verified-box interior into the 224x224 tensor frame and
retains only patch tokens whose patch centers lie inside that product mask.
Padding, tray, neighbouring products, and background tokens are excluded.

Each SKU owns a versioned local patch bank made from independent, canonical
training crops. The bank stores normalized patch embeddings and source
provenance; it is not a single averaged prototype.

For each of the five global candidates:

1. Compare each query product patch with its best-matching reference patch in
   that SKU bank.
2. Average the best-match similarities across query patches and crops.
3. Optionally apply the symmetric reference-to-query term only if it improves
   locked-set Top-3 recall without reducing automatic precision.
4. Return a finite local score and diagnostic match count.

The local score fails closed if the product mask has no patch centers, the
patch bank is missing or incompatible, or any embedding/score is non-finite.
In that case the result remains `Unknown` with the available global Top-3;
local failure must not create a SKU confirmation.

## Candidate fusion and decision

The reranker builds candidates from the union of the global Top-5 and local
Top-5. It computes calibrated global and local distributions only over that
deterministic candidate set, then uses a versioned fusion artifact:

```text
rerank_logit(sku) = beta * log(global_probability)
                 + (1 - beta) * log(local_probability)
```

`beta`, temperature(s), minimum global confidence, local threshold, reranked
margin, and any symmetric-score weight are selected only on grouped
development evidence. SKU ID breaks exact ties.

A conditional DINO SKU confirmation still requires all of the following:

- RepViT Top-1, DINO global Top-1, and reranked Top-1 agree;
- configured global/local confidence and margin gates pass;
- all artifact, preprocessing, canonical-frame, and calibration provenance
  hashes match.

Otherwise return `Unknown` with exactly three unique reranked candidates.

## Artifact and provenance contract

The local patch-bank artifact records:

- schema version and artifact ID;
- DINO weights hash, global-support hash, canonical preprocessing hash, and
  EXIF canonical-frame contract version;
- class map and per-SKU patch-bank sizes;
- canonical source-manifest hash and individual source image hashes;
- bank tensor hash.

Online runtime, evidence collection, calibration, locked evaluation, and
benchmarking reject any mismatch. The final decision provenance contains the
local-bank artifact ID and hash plus whether local reranking ran.

## Evaluation and release gates

Use Batch1 only as grouped development evidence and Batch2 only as locked
evidence after their source/capture-group independence checks pass.

Report, separately for global-only and global+local rerank:

- automatic SKU precision and coverage;
- registered Unknown Top-3 recall and assisted success;
- per-SKU, base-15, incremental-5, and required-scenario metrics;
- local invocation rate, candidate count, stage latency, and direct versus
  recheck p50/p95 latency.

Adopt local reranking only if locked-set automatic precision remains 100%,
locked-set Top-3 recall remains 100%, and full-pipeline latency remains within
the stated target. No result is reported as a release pass without a valid
independent locked set.
