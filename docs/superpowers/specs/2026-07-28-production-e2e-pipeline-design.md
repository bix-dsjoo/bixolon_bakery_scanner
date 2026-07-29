# Production E2E Pipeline Design

> **Historical/superseded notice.** The canonical final CPU path is documented in the [CPU RF-DETR final documentation design](2026-07-29-cpu-rfdetr-final-documentation-design.md). The D-FINE design below is preserved for history and is not deleted.

- Date: 2026-07-28
- Status: approved for implementation
- Scope: Build and measure the complete GPU inference path over the existing
  299 scan images without changing the meaning of their detector artifacts.

## Goal

Provide a deterministic end-to-end runner that turns one source image into
final SKU-labelled object results and a report. The report measures matched
object Top-1 accuracy, registered-SKU Top-3 recall, false-positive final
objects, final `Unknown` objects, and warm GPU latency. It also reports p50,
p95, and conditional-model invocation rates so the mean cannot hide a slow
tail.

The implementation must preserve the required production order:

```text
source image
  -> D-FINE-N candidates
  -> MobileNetV4 box assurance
  -> conditional ConvNeXt-Tiny assurance
  -> component resolver
  -> RepViT-M1 classification
  -> conditional DINOv3 recheck
  -> final objects and SKU counts
```

## Data and evaluation contract

The detector staging annotations intentionally collapse labels to one `bread`
class. Evaluation reads the three original COCO annotation files instead and
creates immutable `SkuGroundTruth` entries containing source image identity,
original-image `xyxy` box, and SKU ID. Their categories are already the
canonical 20-SKU map: group_15class supplies its 15 registered IDs and the two
20-class batches supply all 20 IDs. The staging artifact remains unchanged.

Each predicted final object has an in-bounds original-image `xyxy` box, either
a SKU ID or `Unknown`, a finite confidence, a decision path, and exactly three
distinct ranked SKU candidates whenever it is `Unknown`. SKU quantities are
derived solely from these final objects.

At each reported IoU threshold (0.50 and 0.75), one-to-one deterministic box
matching happens before classification accounting:

- `top1_correct`: matched, non-Unknown final objects with the matching SKU;
- `top1_accuracy`: `top1_correct / registered_gt_count`;
- `top3_correct`: matched objects whose final SKU is correct or whose Unknown
  Top-3 contains the matching SKU;
- `top3_recall`: `top3_correct / registered_gt_count`;
- `false_positives`: unmatched final objects;
- `unknown`: matched final objects with an Unknown decision.

Misses, duplicates, splits, and merges are retained in the report too: they
are essential diagnostics and cannot be obscured by the requested summary
metrics.

The existing 299 images are grouped OOF development evidence, not an
independent locked acceptance set. Fold-specific detector and box-assurance
artifacts may only predict their held-out fold. Classifier calibration must not
be selected from the same evaluated fold. The report must state this scope and
must not call any result a release approval.

## Runtime boundaries

`bakery_scanner.runtime` owns only orchestration. It receives model runners
through narrow protocols, produces immutable contracts, and never silently
converts missing models, invalid tensors, or resolver ambiguity into a SKU.

`bakery_scanner.verifier.assurance` owns MobileNetV4/ConvNeXt four-state
assurance, quality and box-delta validation. It exposes batch scoring and a
conditional-cascade decision, not product classification.

`bakery_scanner.detectors.proposal_graph` owns graph construction and final
component resolution. It keeps all candidates; it uses overlap and containment
as evidence but never hard-NMS suppression. A component without adequate
separation evidence becomes `Unknown`.

`bakery_scanner.classification` owns three padded crops (5%, 10%, 15%),
RepViT scoring, lazy DINOv3 scoring, calibrated gates, Top-3, and fail-closed
classification decisions. RepViT runs only for resolved single-bread boxes;
DINOv3 loads and runs only when RepViT cannot directly confirm a SKU.

`bakery_scanner.e2e` owns source-label loading, matching, report aggregation,
and benchmark aggregation. It does not tune thresholds or alter model output.

## Model and artifact requirements

All model artifacts are validated before use: readable pinned paths, SHA-256
receipts, model/class-map compatibility, expected tensor shapes, finite
outputs, and CUDA:0 availability. GPU inference is FP32 and deterministic.
The already configured RTX 5080 is the only supported production benchmark
device. Missing or invalid artifacts fail the command rather than generating
invented results.

Box Assurance is trained and evaluated in grouped five-fold OOF mode using
only the other four folds for each target fold. The final online bundle is
only created when all required artifact receipts are valid. Classification
uses an independent calibration artifact; if that evidence is unavailable,
the runner still emits fail-closed Unknown decisions and labels the report as
uncalibrated rather than claiming SKU quality.

## Benchmarking

The benchmark command accepts the complete 299-image manifest, warms at least
10 images, then records one whole-image sample per remaining image. CUDA is
synchronized around every measured GPU stage and the whole E2E sample. It
writes canonical JSON containing image count, warmup count, device, precision,
artifact hashes, mean/p50/p95 of every stage and total latency, and ConvNeXt/
DINO invocation rates. Any image failure is recorded and causes a non-zero
exit; no partial report is presented as a full 299-image result.

## Tests and completion evidence

Unit tests cover source SKU-label loading, geometry preservation, deterministic
matching, all requested metrics, Unknown accounting, Top-3 rules, conditional
execution, malformed artifacts, and latency aggregation. Integration tests
exercise the exact stage order with fakes. GPU smoke tests load every real
artifact and run a source image. The final command suite must validate all
unit/integration tests, then run the 299-image grouped-OOF evaluator and warm
benchmark. The measured report is the only evidence used for performance or
accuracy claims.
