# RF-DETR-L detector and classifier fusion-consensus design

> **Canonical-final CPU notice.** This is a current RF-DETR CPU design alongside the [nine-image evaluation design](2026-07-29-rfdetr-desktop-nine-image-evaluation-design.md), [offline deployment design](2026-07-29-offline-cpu-rfdetr-fusion-deployment-design.md), and [final CPU documentation design](2026-07-29-cpu-rfdetr-final-documentation-design.md). The canonical final runtime is EXIF-transposed RGB -> CPU/FP32 RF-DETR-L -> RepViT direct gate -> conditional DINOv3 global/local fusion -> SKU or `Unknown`; it replaces the former D-FINE path as the final runtime without deleting that legacy path.

## Objective

Replace the current detector implementation with the frozen RF-DETR-L model
and its validated post-processing from `C:\workspace\bakery_ai_scanner`, while
retaining this repository's RepViT and DINOv3 classifier assets.  The classifier
must use the immutable `fusion_local_or_global_consensus_margin_v1` policy.

## Detector boundary

The imported detector consists of the sidecar RF-DETR-L checkpoint and its
post-processing contract: canonical RGB input, product/background class
validation, finite geometry checks, clipping to the visual frame, deterministic
ordering, and its bound detector-calibration threshold.  The adapter converts
accepted product predictions to this repository's existing `BreadProposal`
contract.  No classifier threshold or geometry heuristic is added at this
boundary.

The detector adapter/factory passes accepted `BreadProposal` regions directly
to the RepViT-M1 direct-decision gate. The canonical CPU path has no Box
Assurance or component-resolver intermediate; those legacy components remain
preserved outside this final runtime.

## Classifier decision contract

For every detector region that reaches classification, run RepViT-M1 first.
A RepViT result accepted by its immutable direct-decision gate is final. Only
a direct-gate rejection runs DINOv3 global evidence, DINOv3 local evidence,
and the immutable fusion ranker. For that conditional recheck path, let `F`
be the fusion-ranked top SKU, `L` DINOv3-local top SKU, `R` RepViT top SKU,
and `G` DINOv3-global top SKU.

The policy returns a SKU only when either condition is true:

1. `F == L`; or
2. `F == R == G` and `fusion_top1_score - fusion_top2_score >= 0.85`.

Every result that fails its applicable direct or fusion acceptance rule returns
`Unknown`; no fallback model may promote it to a SKU. The second condition is
deliberately scoped to the global-consensus route.

## Artifact and schema requirements

- Publish a canonical JSON `FusionPolicyArtifact` with schema version 3,
  decision rule `fusion_local_or_global_consensus_margin_v1`, and
  `consensus_margin_floor: 0.85`.
- Bind the artifact's exact model/preprocess hashes to the configured RepViT,
  DINOv3 weights, DINO support, DINO local-bank, and prototype artifacts.
- Add its relative path and SHA-256 to `configs/classifier_policy.yaml`; loading
  must fail on any hash or provenance mismatch.
- Preserve rollback deserialization for schemas 1 and 2 while strictly
  deserializing schema 3's exact field set.

## Verification

Tests must prove both acceptance routes, rejection for low global-consensus
margin, rejection when the top IDs disagree, schema-v3 canonical round-trip and
invalid-schema rejection, config SHA validation, and `Unknown` reasons.  The
detector adapter must prove source-postprocessing output remains bounded and
maps deterministically to `BreadProposal`. Legacy Box Assurance and resolver
tests must remain unchanged and pass as preservation checks.
