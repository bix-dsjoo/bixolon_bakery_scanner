# Few-shot SKU training-data optimization design

## Responsibility and acceptance

**Responsibility:** determine the smallest number of labeled development images
per newly registered SKU that preserves the accuracy and fail-closed behavior of
the classification subsystem.

**Acceptance:** on the frozen RPC protocol described here, the selected shot
count is the smallest count whose locked result is non-inferior to the balanced
150-shot reference, passes the wrong-SKU and old-SKU regression guardrails, and
has complete model, data, calibration, policy, seed, code, and artifact
provenance. A result on RPC is an RPC result; it does not establish the image
requirement for bakery products or another retail capture domain.

## Goal

Answer the practical onboarding question:

> For an existing product-recognition system, how many labeled source images
> are needed to add a new SKU?

The experiment optimizes labeled development/support images first. It does not
try every combination of model, support selection, shot count, calibration
count, detector, and augmentation. Instead, it uses a staged funnel:

```text
cheap low-shot screen
  -> retain at most two methods
  -> ascending learning curve
  -> refine the first passing interval
  -> rebuild and calibrate the full classification subsystem
  -> one locked comparison
```

The primary comparison uses ground-truth product boxes so detector errors cannot
masquerade as classification errors. Detector generalization is a separate
responsibility and is checked end to end only after a classifier candidate is
frozen.

All variants are research-only pipeline compositions. They do not modify
`configs/pipelines/canonical_cpu.yaml`, replace the bakery RF-DETR artifact, or
change the released 20-SKU class map. A winning variant requires a separate
promotion decision and immutable production manifests.

## Terminology and counting

- A **shot** is one labeled, original `train2019` image assigned to a novel SKU.
  Augmented pixels, padded crops, feature perturbations, and repeated epochs do
  not create additional shots.
- A **support set** is the nested set of `k` selected shots for every novel SKU
  in a class fold.
- A **base SKU** is trained before the simulated onboarding event.
- A **novel SKU** is hidden from base training and added with `k` shots.
- A **capture stratum** is the tuple `(category_id, product identity, side,
  camera)` parsed from RPC train filenames. Frames in one stratum are correlated
  views from one capture setup.
- A **scene burst** is an atomic group of adjacent checkout images. No burst may
  cross calibration, selection, or locked roles.
- The **balanced reference** uses 150 shots per novel SKU. RPC provides at least
  158 training images per category, so all 200 categories can participate.
- The **all-available reference** uses every available train image and is a
  secondary upper-bound diagnostic because its classes are imbalanced.

Every result reports both the image count and the number of covered capture
strata. “Five images” must not be described as five independent capture
sessions when several images came from one stratum.

## Dataset and provenance

The external source is the RPC 2019 dataset under `C:\workspace\archive`:

| Role source | Images | Objects | Annotation SHA-256 |
| --- | ---: | ---: | --- |
| `train2019` | 53,739 | 53,739 | `2fe6891a1f33d54104116940bd2b6167d2e20b846c66808ad33e98cc3775125a` |
| `val2019` | 6,000 | 73,602 | `25afdfed91bc09bff595399e0876a5707708a7061be3fa4121d13385abd1bde7` |
| `test2019` | 24,000 | 294,333 | `2a1cb518b202c7e13a74b4ca742aad76f6246cba788288bac6423c7d4a97ba58` |

There are 200 SKU categories. Train images contain one annotated object and
span four cameras; category counts range from 158 to 640. Validation contains
2,000 easy, 2,000 medium, and 2,000 hard checkout scenes. Test contains 8,000
scenes at each difficulty.

`C:\workspace\archive\retail_product_checkout` is a duplicate extracted copy.
The experiment uses only the root copy and must fail if a materializer attempts
to combine both. Images, crops, embeddings, raw predictions, and full run
outputs remain external and are never committed.

The source annotation declares the RPC Attribution-NonCommercial-ShareAlike
license. Any later redistribution or commercial use requires a separate
license review.

### Immutable control-plane records

Implementation must create Git-tracked manifests that record:

- dataset identity and the three annotation hashes above;
- every selected image identity, byte size, and SHA-256;
- category map and simulated base/novel class-fold assignment;
- capture-stratum and scene-burst identities;
- development, calibration, selection, and locked role;
- support-selection method, shot count, fold, and seed;
- canonical preprocessing and augmentation identities;
- initialization, model, prototype/support, calibration, and policy hashes;
- code commit, environment lock, and output URI.

Changing any source, split, selection rule, preprocessing rule, or seed creates
a new manifest version. Published evidence is never mutated.

## Leakage-safe roles

### Development/support

Only `train2019` supplies model-training images and prototype/cache support.
The train annotation contains one object per image, and that ground-truth box is
the canonical crop source.

The 200 categories are partitioned into five immutable novel-class folds of 40
SKUs. In each fold:

- 160 categories are base SKUs;
- 40 categories are novel SKUs;
- each SKU is novel exactly once across the five folds;
- assignment is balanced by RPC supercategory, with SHA-256 tie-breaking;
- one frozen base artifact is trained per fold and reused by all shot
  conditions in that fold.

The base model uses a fixed, balanced maximum of 150 images per base SKU. The
experiment varies only the novel-SKU support count.

### Calibration and development selection

`val2019` is divided 50/50, with scene bursts kept atomic:

1. Parse a filename as `YYYYMMDD-HH-MM-SS-SUFFIX.jpg`.
2. Within `(date, suffix, difficulty)`, sort by timestamp.
3. Start a new burst when the gap from the preceding image exceeds 120 seconds.
4. Apply deterministic iterative stratification using difficulty and the
   burst's category-incidence vector.
5. Resolve all ties with SHA-256 of
   `(split-version, burst-identity)`.

The two roles must be as close to 3,000 images each as burst atomicity permits,
must have approximately equal easy/medium/hard counts, and must contain every
SKU. A split that violates SKU coverage or assigns one burst to two roles is
invalid.

- **Calibration** may fit gates, temperatures, risk calibration, and fusion.
- **Development selection** compares methods and shot counts.

No development-selection result may alter the calibration membership.

### Locked acceptance

All `test2019` scene bursts are locked acceptance. They are not used for method
choice, shot-count choice, support selection, augmentation choice,
hyperparameter choice, calibration, or debugging.

The locked set is evaluated only after the candidate and the balanced reference
are frozen. If the locked result influences a subsequent choice, the lock is
retired and no acceptance claim is made until a newly locked set is available.

## Fixed image contract

All source and checkout images are EXIF-transposed and converted to RGB before
crop extraction. Ground-truth COCO boxes are converted to finite, clipped,
in-bounds `[x_min, y_min, x_max, y_max]` coordinates in that canonical frame.
Malformed or empty boxes fail closed.

The model comparison uses one common, versioned crop and normalization contract.
The current 5%, 10%, and 15% padded views may be retained as deterministic
model inputs, but they count as transformations of one shot, not three shots.
Augmentation is fixed before the first run and is not a factor in the main
funnel.

## Compared low-shot methods

The first screen compares only three method families:

Each method family must produce the same full-system evidence interface:
RepViT global scores, DINOv3 global scores, and DINOv3 local scores in the
registered-SKU class order. This keeps the fail-closed gate/fusion boundary
comparable even when the onboarding recipe changes.

### M0: current-style learned head plus mean support

- Initialize from the immutable fold-specific base checkpoint.
- Keep the RepViT backbone frozen.
- Expand the classifier to the novel SKUs.
- Preserve old classifier rows exactly.
- Train only the declared new-head parameters with a fixed, class-balanced
  recipe.
- Build DINOv3 global and local mean support from the same selected shots.

M0 is the control because it is closest to the current 15+5 onboarding method.

### M1: dual frozen mean prototypes

- Keep both RepViT and DINOv3 feature extractors frozen.
- L2-normalize each model's support embeddings independently.
- Average support embeddings by SKU in each feature space and normalize the
  means again.
- Use RepViT-space cosine scores as RepViT global evidence and DINOv3-space
  cosine scores as DINOv3 global evidence.
- Build DINOv3 local patch prototypes from the same selected shots.

M1 is the simplest metric-learning baseline.

### M2: dual frozen exemplar caches/kernels

- Keep every normalized RepViT and DINOv3 support embedding rather than
  reducing a SKU to one mean.
- Produce a class-normalized cache/kernel score so base classes with more
  support cannot win solely from support count.
- Use a fixed closed-form or training-free scorer whose hyperparameters are
  declared before development-selection evaluation.
- Retain DINOv3 local patch exemplars under the same class-normalized rule.

M2 tests the recent cache/kernel few-shot direction represented by Tip-Adapter
and ProKeR without requiring a large end-to-end update.

CLIP text priors are not part of the primary experiment. RPC labels such as
`1_puffed_food` are not sufficiently specific product descriptions. A later
CLIP challenger requires immutable brand, variant, size, and package text and
must be a separate experiment.

## Support-selection methods

### RND: deterministic random

For each seed and SKU, rank eligible source identities by
`SHA256(seed, source-identity)` and take the first `k`. Sampling is without
replacement.

### DIV: diversity-aware

Use frozen DINOv3 embeddings from eligible train images:

- for one shot, choose the medoid nearest the class centroid;
- for more shots, use deterministic k-medoids or equivalent farthest-first
  coverage with SHA-256 tie-breaking;
- while `k` does not exceed the number of capture strata, select at most one
  image per stratum;
- above that point, add images round-robin across strata before adding another
  image from an already overrepresented stratum.

For every seed, support sets are nested:

```text
K1 ⊂ K3 ⊂ K5 ⊂ K10 ⊂ K20 ⊂ K40 ⊂ K80 ⊂ K150
```

The selector must materialize the entire ordered support list once. A larger
shot condition is a prefix extension, never an independently resampled set.

## Funnel design

### Stage 1: cheap low-shot screen

Use oracle crops without gates, fusion, or `Unknown`. Record forced Top-1 from
the RepViT and DINOv3 global branches separately, plus their Top-1 agreement.
Run:

```text
M0 × DIV × {1, 3, 5}
M1 × DIV × {1, 3, 5}
M2 × DIV × {1, 3, 5}
M2 × RND × {1, 3, 5}
```

This is 12 cells, not the full method-by-selector Cartesian product. Each cell
starts with five support seeds across all five novel-class folds. A method is
dominated and removed only when both of its paired branch-level novel-SKU macro
Top-1 results are more than two percentage points below another method and it
offers no branch-level wrong-SKU improvement. Any contender within one
percentage point of the best method on either branch, or on a non-dominated
accuracy/error trade-off, expands to ten seeds. At most two methods continue.

### Stage 2: ascending learning curve

For the surviving methods, evaluate:

```text
1 -> 3 -> 5 -> 10 -> 20
```

Continue to `40 -> 80 -> 150` only if no smaller count passes. Always train the
balanced 150-shot reference and all-available diagnostic once.

Each point starts with five support seeds. Clearly failing points do not receive
more seeds. A point within three percentage points of the provisional
non-inferiority boundary expands to ten seeds.

After a first passing point appears, evaluate the next larger anchor to check
that the result is not a non-monotonic accident. If the larger anchor fails, do
not select a minimum; expand seeds and diagnose the support or training
instability.

### Stage 3: boundary refinement

Evaluate only the interval between the last failing anchor and first passing
anchor:

- `3` fail and `5` pass: add `4`;
- `5` fail and `10` pass: add `6` and `8`;
- `10` fail and `20` pass: add `12`, `15`, and `18`;
- for a later interval, add no more than three preregistered interior points.

All refinement points use ten support seeds. The smallest passing count becomes
the provisional candidate.

### Stage 4: full classification-subsystem confirmation

Only these frozen conditions enter the expensive confirmation:

1. the last failing count;
2. the provisional minimum;
3. the next larger passing anchor;
4. the balanced 150-shot reference.

For every condition, rebuild and hash:

```text
oracle product crop
  -> RepViT direct evidence/gate
  -> conditional DINOv3 global and local evidence
  -> immutable fusion consensus
  -> registered SKU or Unknown
```

Every condition receives its own calibration artifacts fitted only on the fixed
calibration role. The configured canonical acceptance rule remains fail-closed:
the ranked SKU is accepted only when it equals local Top-1, or when both model
global Top-1 values equal that SKU and the fusion margin is at least `0.85`.
Every other result is `Unknown`.

Calibration sample count is fixed throughout this design. Optimizing calibration
count is a later one-dimensional experiment performed only after the
development/support count is selected.

### Stage 5: locked and end-to-end confirmation

Evaluate exactly two frozen conditions on `test2019`:

- the provisional minimum;
- the balanced 150-shot reference.

The Stage-5 scheduler accepts no free method, selector, or shot-count input.
For each fold and support seed it consumes a canonical Stage-4 selection
certificate containing exactly four distinct confirmation-score receipt
SHA-256 values: last failure, provisional minimum, next passing anchor, and
the balanced 150-shot reference. The certificate requires one common
method/selector/fold/seed, a failing last-lower point, a passing provisional
minimum and next anchor, and a passing 150-shot reference. Both locked
conditions must reproduce that certificate exactly; their candidate/reference
method and selector must match, and their reference is exactly `k=150`.

The certificate is not authorized by digest strings alone. Before scheduling,
scoring, or aggregating a locked condition, resolve all four declared external
receipt paths, require canonical bytes whose SHA-256 values equal the claims,
and verify each is a completed provisional Stage-4 confirmation receipt for
the declared condition, cohort, scoring plan, method, selector, fold, and
support seed.

If the provisional minimum passes, it is the RPC minimum for this model and
capture contract. If it fails, no larger count is selected from the same locked
evidence.

After locked classification acceptance, perform one end-to-end confirmation
with a separately frozen, artifact-verified retail product detector if such a
detector exists. If no retail detector is available, report the end-to-end
boundary as unverified and limit the conclusion to oracle-box classification.
Never use the bakery-only detector's failure on packaged goods to tune the
classification experiment.

## Metrics and statistical comparison

### Cheap-screen metrics

- novel-SKU macro forced Top-1 accuracy;
- base-SKU macro forced Top-1 accuracy;
- novel/base confusion matrix;
- per-SKU accuracy and fifth-percentile SKU accuracy.

### Full-subsystem primary and guardrail metrics

- **Primary:** novel-SKU macro final correct recall, with `Unknown` counted as
  not correct;
- wrong registered-SKU rate over all ground-truth novel objects;
- `Unknown` rate and registered coverage;
- base-SKU macro final correct recall and wrong-SKU rate;
- per-SKU final correct recall, worst-SKU list, and fraction of novel SKUs with
  a loss greater than ten percentage points;
- conditional-DINO execution rate;
- E/M/H results separately and combined.

Use deterministic one-to-one ground-truth object accounting. During oracle-box
classification there is exactly one prediction opportunity per ground-truth
box. The later detector evaluation uses canonical-frame IoU `0.50` and reports
misses, duplicates, non-target detections, splits, and merges separately.

Confidence intervals use a preregistered hierarchical paired bootstrap:

1. resample novel SKUs within their class fold;
2. resample checkout scene bursts within difficulty;
3. retain paired predictions for all compared conditions;
4. aggregate across the declared support seeds.

The bootstrap seed and replicate count are fixed in the experiment manifest.

## Passing rule

The provisional and locked minimum must satisfy all of the following relative
to the balanced 150-shot reference:

1. the lower 95% confidence bound for novel-SKU macro final correct recall is
   no more than `2.0` percentage points worse;
2. the upper 95% confidence bound for novel-SKU wrong registered-SKU rate is no
   more than `0.5` percentage points worse;
3. no more than 5% of novel SKUs lose more than `10.0` percentage points of
   final correct recall;
4. base-SKU macro final correct recall is no more than `1.0` percentage point
   worse than the frozen fold-specific base checkpoint;
5. no artifact, role, class-map, preprocessing, support, calibration, or policy
   verification fails.

A lower wrong-SKU rate obtained by rejecting nearly everything does not pass
because the primary final-correct-recall criterion includes `Unknown` as not
correct. CPU latency and DINO execution rate are reported but cannot justify
an accuracy trade-off.

## Failure handling

- Missing or hash-mismatched images, annotations, checkpoints, support banks,
  policies, or preprocessing artifacts abort the run before evaluation.
- A SKU without enough valid shots for a declared condition invalidates that
  condition; it is never oversampled with duplicates.
- A malformed ground-truth crop is reported and the dataset manifest is
  rejected, not silently skipped.
- A support selector with nondeterministic ties is invalid.
- A calibration or selection burst appearing in another role invalidates all
  dependent receipts.
- Skipped GPU, artifact, integration, package, or end-to-end suites are
  unverified, not passed.
- An unexpected non-monotonic learning curve triggers more seeds and diagnosis;
  it never triggers silent smoothing or deletion of an unfavorable point.

## Deliverables

Git contains only compact control-plane and reviewed evidence:

- immutable RPC dataset and split manifests;
- class-fold and ordered support-selection manifests;
- one experiment specification per stage;
- compact result receipts and reviewed learning-curve summaries;
- a final comparison of the selected minimum and balanced reference;
- explicit limitations and the status of end-to-end verification.

External storage contains images, crops, cached embeddings, checkpoints,
prototype/support banks, raw evidence, raw predictions, and full run outputs.

The final conclusion must have this form:

> Under RPC 2019, the declared class-incremental model recipe, the frozen
> preprocessing contract, and the locked checkout-scene protocol, the smallest
> passing development/support count is `k` images per newly added SKU.

It must not be shortened to “all bakery or retail SKUs need `k` images.”

## Research basis

The method screen is intentionally small and grounded in these relevant
directions:

- Snell et al.,
  [*Prototypical Networks for Few-shot Learning*](https://arxiv.org/abs/1703.05175):
  distance-to-prototype classification for novel classes.
- Zhang et al.,
  [*Tip-Adapter*](https://arxiv.org/abs/2207.09519): a training-free support
  cache for few-shot CLIP adaptation.
- Bendou et al.,
  [*ProKeR*](https://openaccess.thecvf.com/content/CVPR2025/html/Bendou_ProKeR_A_Kernel_Perspective_on_Few-Shot_Adaptation_of_Large_Vision-Language_CVPR_2025_paper.html)
  (CVPR 2025): a kernel interpretation and globally regularized closed-form
  few-shot adapter.
- Bär et al.,
  [*Frozen Feature Augmentation*](https://openaccess.thecvf.com/content/CVPR2024/html/Bar_Frozen_Feature_Augmentation_for_Few-Shot_Image_Classification_CVPR_2024_paper.html)
  (CVPR 2024): few-shot improvement from augmenting frozen features.
- [DINOv3](https://ai.meta.com/research/publications/dinov3/) (Meta AI, 2025):
  strong frozen self-supervised visual representations and lightweight
  downstream adaptation.
- Tur et al.,
  [*Exploring Fine-grained Retail Product Discrimination*](https://arxiv.org/abs/2409.14963)
  (2024): retail zero-shot limitations and the usefulness of visual
  prototypes.

These works motivate the hypotheses; none substitutes for the locked RPC
experiment or for later target-domain bakery/retail evidence.
