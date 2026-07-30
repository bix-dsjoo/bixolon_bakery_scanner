# Customer Capture Review Redesign

## Responsibility and acceptance

**Responsibility:** let a bakery self-checkout customer verify what the camera
recognised from the retained capture, understand which detected bread each
checkout line represents, and correct only uncertain results without relying
on an isolated crop.

**Acceptance:** after analysis, the customer can see the complete retained
capture with one numbered, labelled detection box for every final inference
object; tapping a box and tapping its corresponding checkout line select the
same object; a selected object is visually prominent in both places; confirmed
items retain their existing automatic checkout flow; unresolved items expose
their existing candidate choices and catalog fallback in context; and a
customer can retake when the image or detection region is visibly unsuitable.
No inference result, candidate ranking, `Unknown` decision, audit capture,
order provenance, or model policy is changed by this presentation work.

## Decision

Use a **capture-first, linked review ledger** rather than the current
side-by-side original and enlarged crop.

This is preferable to a one-item wizard because a customer who has placed
several breads on the tray needs to check count, location, and identity as a
whole before choosing individual alternatives. It is preferable to a static
full-image overlay because selection must connect the image evidence to the
line that will be charged. It follows the common self-checkout pattern of an
itemised review while keeping camera evidence available at the point of
correction. Comparable vision-assisted checkout products emphasise a real-time
itemised receipt and final confirmation rather than exposing confidence scores
or model internals.

## Customer experience

### 1. Review the captured scene

The review page begins with the exact retained camera still, rendered in its
canonical orientation and aspect ratio. It is never replaced by, nor framed as,
an inferred crop.

Every final inference object has a bounding box on the image. The box carries a
stable reading-order number (`01`, `02`, ...) and a short state label:

- confirmed object: its recognised product name;
- candidate object: `확인이 필요해요` (confirmation needed); and
- `Unknown` object: `상품을 확인해 주세요` (please identify this item).

Boxes use an outline and translucent tint only; the underlying bread remains
visible. A selected box is BIXOLON orange and uses a thicker outline. Other
confirmed boxes are quiet graphite; objects requiring attention use the
existing uncertainty semantic colour. The number, outline pattern, and text
state communicate status together, so colour is never the sole cue.

If labels would collide, the number remains on the box and the product name is
shown only in the linked list. The rendering must preserve the canonical
image-to-box coordinate mapping including the current Windows preview-orientation
correction rules.

### 2. Link image evidence to the checkout list

Below the image, each object is a flat, numbered checkout row. It displays the
recognised name or confirmation state, quantity (one object per row initially),
and the existing product price when a product is selected. Grouped totals stay
on the subsequent order-review page; this screen answers “what did the camera
see?” before “what will I pay?”.

Selecting either a detection box or its row selects the same object. The page
scrolls or pans only as needed to keep the selected image region visible; it
does not crop away the surrounding scene. The matching row receives a subtle
selection background and an explicit `사진에서 02번` (No. 02 in the photo)
reference. Keyboard focus and screen-reader labels express the same mapping.

On a compact window, the capture appears above the ledger. On a wide kiosk
window, capture and ledger may sit side-by-side while retaining this reading
order and a visible focus path.

### 3. Correct only objects that need help

Confirmed objects are read-only on this page; their ordinary path remains
automatic. The customer can select an attention row/box to open an inline
detail region immediately below its row. It contains, in this order:

1. plain-language reason: `사진에서 02번 빵을 확인해 주세요`;
2. the existing candidate products as large, named choices with price;
3. `전체 상품에서 찾기`; and
4. `다시 촬영` when the displayed image/box does not represent the placed
   bread clearly.

Candidate order and contents exactly reflect the immutable inference result;
the UI must not invent a best match or conceal an `Unknown` outcome. Choosing a
candidate or catalog product continues to use the existing selection/audit
path. Retake uses the existing reset-and-rescan behaviour and clearly explains
that the current photo will be replaced for this checkout attempt according to
the established retention flow.

The previous isolated crop is removed from the default customer screen. A
future optional magnifier may zoom the complete capture around the selected box,
but it must retain the selected outline and a route back to the full scene.

### 4. Proceed

The fixed bottom action remains the existing primary action. It becomes enabled
only when every object is already confirmed or the customer has made the
required selection under current checkout rules. Its label stays action-based
(`주문 확인` / confirm order). An above-action summary names how many items
still need attention instead of asking every customer to second-guess automatic
matches.

## Technical boundaries

- Add a customer presentation model that derives a stable display number,
  canonical `Rect`, product presentation state, and attention state from the
  immutable checkout/inference objects. It contains no model confidence or
  model-facing explanation.
- Add an interactive capture overlay that renders in the retained image's
  canonical coordinate frame, supports hit testing, and exposes semantic labels
  for every object.
- Replace `CapturedReviewImage` with the linked capture overlay; do not change
  the retained file, its hash, or `SelectedObjectCropGeometry` outside the
  customer review surface without an explicit migration.
- Keep the existing controller calls for top-3 choice, catalog choice,
  continuation, and retry/rescan. If a retake callback is not currently
  available in `CustomerReviewView`, expose only that narrow callback through
  the existing checkout screen/controller boundary.
- Preserve all fail-closed behaviour: no UI selection changes an immutable
  inference object; customer resolutions remain separate audit evidence.

## Tests

Write the failing widget/contract tests before behaviour changes. Cover:

- every final object renders exactly one numbered overlay with its canonical
  bounding box mapping;
- selecting a row selects and highlights the matching overlay, and selecting
  an overlay selects the matching row;
- confirmed, candidate, and `Unknown` states have distinct text labels and
  accessible semantics without revealing confidence scores;
- candidate choices appear only for objects that need a customer decision and
  retain their supplied ordering;
- catalog and retake calls use their current controller paths;
- the image remains full-scene at all supported layouts, without the default
  isolated selected-object crop;
- the primary action's enabled state still obeys checkout resolution rules; and
- canonical coordinate/orientation tests cover Windows and non-Windows image
  presentation.

Run focused customer-review tests, then all Flutter widget, accessibility, and
checkout/audit contract tests. Any unavailable camera or platform suite is
reported as unverified.

## Self-review

- The design directly addresses cropped evidence, opaque recognition, and
  uncertain-candidate selection.
- Camera evidence is visible without presenting model scores or allowing the
  customer to alter immutable inference.
- The existing canonical-frame, `Unknown`, audit, and resolution boundaries are
  retained.
- The scope is one customer review surface and its narrow presentation helpers;
  it does not redesign checkout, model inference, or administration.
