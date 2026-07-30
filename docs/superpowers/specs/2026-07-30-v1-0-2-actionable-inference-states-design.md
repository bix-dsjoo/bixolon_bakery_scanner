# 1.0.2 Actionable Inference States Design

## Purpose

Version 1.0.2 makes the bakery evaluator understandable to first-time users
while retaining the evidence needed to assess inference behavior. It does not
change the canonical RF-DETR-L, RepViT, conditional DINOv3, or immutable fusion
policy. Instead, it translates existing result and quality signals into clear
next actions.

## Product decisions

The primary UI presents exactly three states for every analysis:

| State | User-facing copy | When it applies | Result handling |
| --- | --- | --- | --- |
| Normal | `정상 인식` | An object is automatically accepted as a registered SKU. | Show product name, box, and final count. |
| Unknown | `알 수 없음` | A box is usable but the model cannot safely auto-confirm it, and ranked candidates are useful evidence. | Show the three most likely products; do not silently count it as a SKU. |
| Needs retake | `이 사진만으로 판단하기 어려워요` | Image, box-separation, detector, or candidate evidence is too weak to use safely. | Do not publish the scan's SKU or count as a usable result; direct the user to retake. |

The UI must not claim that an item is an unregistered/new product. A closed-set
classifier cannot distinguish an unseen product from weak visual evidence with
enough certainty to make that claim.

## Needs-retake guidance

`Needs retake` is an action outcome rather than an alternate SKU outcome. The
display chooses one short, concrete instruction from the underlying signal:

| Underlying signal | Guidance |
| --- | --- |
| Overlap, merge, split, or poor box separation | `빵 사이 간격을 두고 다시 촬영해 주세요` |
| Blur, clipping, low exposure, or otherwise unusable frame | `빵이 모두 보이도록 다시 촬영해 주세요` |
| Candidate evidence is not useful enough to present as a recommendation | `빵이 잘 보이도록 다시 촬영해 주세요` |

It can apply at either scope:

- **Whole scan:** frame-wide quality or detection problems make the entire
  photograph unusable. Present one whole-photo retake state and suppress
  usable SKU/count output.
- **Individual object:** an isolated object is the problem. Highlight its box
  and instruction; the scan is still marked as requiring a retake, so users do
  not treat a partial total as final.

If any object needs a retake, the primary screen must make it clear that the
photo is not a finalized count. Confirmed objects may remain visible as
diagnostic evidence but are not shown as a final transaction total.

## Screen behavior

1. Run the existing inference pipeline and retain its canonical coordinates,
   result path, Unknown reason, confidence/ranking evidence, and timing.
2. Derive an immutable presentation state without altering the underlying
   decision. The most severe visible action wins: whole-scan retake, object
   retake, Unknown, then Normal.
3. Show all detection boxes with product or state labels. Confidence stays out
   of the image overlay.
4. For Unknown, show `가능성이 높은 제품 3개` only when the candidates are
   useful. Never fabricate candidates merely to fill the panel.
5. For Needs retake, replace the final summary with the instruction and a
   `다시 촬영` action. Keep a collapsible `분석 참고` area for model evaluators.

## Evidence and developer view

The collapsible `분석 참고` area is secondary to the simple user instruction.
It may include the detector status, box quality flags, Unknown reason, ranked
candidate evidence, decision path, per-stage latency, backend, and model/policy
provenance. It must label low similarity as evidence only, not as an assertion
that the product is new or unregistered.

## Data boundary

A presentation-state adapter owns this feature. It consumes existing
canonical inference output and optional quality flags, and emits:

- `normal`, `unknown`, `needsRetakeObject`, or `needsRetakeScan`;
- a localized primary instruction;
- an optional object identifier for object-level highlighting;
- whether final total/count is usable;
- whether ranked candidates are displayable; and
- a diagnostic reason code retained for the developer view.

Detector thresholds, Box Assurance, component resolution, classifier weights,
direct gate, fusion artifact, SHA validation, and the fail-closed `Unknown`
classification contract remain unchanged.

## Validation

Tests must cover:

- accepted SKU -> Normal and count included;
- Unknown with useful ranked evidence -> Unknown plus exactly three candidates;
- weak ranked evidence -> Needs retake without candidate recommendations;
- object-level quality issue -> highlighted object and non-final scan result;
- scan-level quality issue -> whole-photo retake and no final total;
- unknown/retake states never aggregate into a registered SKU count;
- overlay labels remain visible without confidence values; and
- existing canonical pipeline regression and policy integrity checks remain
  unchanged.

