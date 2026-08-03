# Unified Checkout Review Design

## Purpose

Replace the visually and behaviorally different automatic-confirmation and
candidate-selection pages with one customer-facing review workspace. Preserve
the canonical inference pipeline, immutable inference evidence, audit history,
catalog snapshot, payment semantics, and fail-closed `Unknown` behavior.

The customer should always answer the same question in the same place:
"Is every bread and quantity in this order correct?"

## User-visible state model

### 1. All products automatically confirmed

- Show the retained full camera image with numbered detection boxes on the
  left.
- Show the order list, quantity controls, product correction control, total,
  rare actions, and payment action on the right.
- Payment is enabled immediately because every detected object is resolved.
- Selecting an image box selects the corresponding order row, and selecting an
  order row selects the corresponding image box.

### 2. One or more products require candidate selection

- Use the same header, left image pane, right work pane, divider, total area,
  and bottom action rail as the automatically confirmed state.
- Select the first unresolved object initially and highlight its numbered box.
- In the right pane, keep resolved order rows unchanged and render the selected
  unresolved row as `NN번 · 상품 확인 필요`.
- Directly below that row, show the three ranked candidate products in worker
  order, followed by the tertiary `다른 상품 찾기` action.
- Selecting a candidate replaces the unresolved row with the same resolved
  order-row component used for automatic results. It does not navigate to a
  second review page.
- Keep payment disabled while any object remains unresolved. Its label states
  the remaining count. When the last object is resolved, the existing total and
  payment action become available without a page transition.
- A resolved candidate-selected product always exposes the same `변경` control
  as an automatically resolved product.

### 3. Capture must be repeated

- Do not render the current mostly empty retake page.
- Keep the retained capture or camera workspace visible and present one compact
  blocking notice above it.
- The notice contains a concise reason and one primary `다시 촬영` action.
- Activating `다시 촬영` performs the existing audited retake transition and
  returns directly to live camera capture.
- Manual entry remains available only after the existing retry-limit policy
  permits it. It is a tertiary action inside the same notice, not a separate
  content section.

## Shared layout

The review workspace keeps the established BIXOLON POS structure:

```text
+---------------------------------------------------------------+
| BIXOLON  주문 확인                                            |
+------------------------------------+--------------------------+
| 촬영한 트레이                     | 주문 내역                |
|                                    |                          |
| retained image + numbered boxes    | resolved rows            |
|                                    | unresolved row           |
|                                    |   candidate 1             |
|                                    |   candidate 2             |
|                                    |   candidate 3             |
|                                    |                          |
|                                    | total / rare actions      |
+------------------------------------+--------------------------+
|                         payment action                         |
+---------------------------------------------------------------+
```

- Preserve the current approximate 3:2 left/right proportion.
- Keep one thin vertical divider and the continuous full-width bottom rail.
- Use spacing, alignment, typography, and one pale selected surface for
  hierarchy. Do not add cards, gradients, shadows, decorative badges, or
  additional accent colors.
- Orange identifies the active object or primary action. Quantity and edit
  controls remain neutral.
- Keyboard focus uses one consistent visible focus treatment and must not be
  confused with the orange selected-object state.

## Product selection and correction

- `상품 추가`, candidate fallback, and product correction all use the same
  right-side catalog panel.
- Opening the panel preserves the retained image and the selected numbered
  object when an object is being corrected.
- The panel receives keyboard focus when opened, traps focus while open, closes
  with `Esc`, and returns focus to the invoking control.
- A customer may change the same detected object repeatedly.
- Returning an overridden registered object to its original mapped product is
  valid. The current resolution must use `aiAutoCustomerAccepted`; selecting a
  different product must use `customerOverrodeAuto`. Previous resolution rows
  remain immutable history and only one row remains current.
- When one order line represents multiple detected objects, the correction
  menu labels each target using the visible image number, for example
  `02번 빵 변경`. Generic ordinal labels are prohibited.
- Manual products remain removable; detected products remain object-linked and
  cannot be deleted as if they were manual products.

## Copy and localization

- Customer guidance and actions are Korean.
- Registered catalog product names remain the approved English display names.
- Customer category labels are consistently Korean, including `빵` and
  `샌드위치`; raw category IDs must not appear.
- Remove malformed or mojibake literals. Required resolved-state copy is
  `선택한 상품` and `변경`.
- Avoid system-oriented terms such as model confidence, fusion, candidate
  evidence, or `Unknown` in customer copy.

## Architecture

- Keep `CheckoutPhase.customerReview` and `CheckoutPhase.orderReview` as domain
  states so audit and controller responsibilities remain explicit.
- Render both phases through one shared review-workspace component. The phase
  controls only whether unresolved candidate controls or editable order
  controls are active; it must not select a different page skeleton.
- When the final unresolved object is resolved, persist the resulting draft
  order and transition to `orderReview` without visible navigation. The shared
  workspace retains selected object and scroll position across the phase
  transition.
- Continue to derive candidates exclusively from immutable worker Top-3
  evidence and the frozen session catalog. Do not auto-select a rejected result
  in Dart.
- Retake presentation changes only the customer surface. Existing controller
  retake, retry-limit, audit, and session lifecycle contracts remain intact.

## Error handling

- Do not close a catalog panel until a product selection finishes successfully.
- If a selection fails, retain the panel and selected object and show a concise
  inline error; never silently discard the action.
- Disable repeated submit actions while the corresponding async operation is in
  progress.
- A missing retained image uses the existing explicit image-unavailable state;
  it must not invent boxes or crop coordinates.
- Any unresolved or unmapped result continues to block payment.

## Accessibility

- Image boxes, order rows, unresolved rows, candidates, and correction targets
  expose the same visible number in their semantic labels.
- Candidate controls expose product name, price, rank, and selected object
  number.
- The catalog side panel behaves as a modal focus region even though it is
  visually attached to the workspace.
- `Esc` closes the panel, `Enter` activates focused controls, and focus returns
  to the invoking edit/add control.
- Minimum targets remain at least 44 logical pixels.

## Acceptance criteria

1. Automatic and candidate scans render the same review skeleton at 1280x820
   and 1024x720 without page scrolling or overflow.
2. Choosing a Top-3 candidate converts only that numbered unresolved row into
   the normal resolved row and preserves the full retained image.
3. A customer can change `Egg Tart -> Croissant -> Egg Tart`; the current
   product, total, resolution source, and audit history all agree.
4. Aggregated identical products expose target labels using image numbers and
   editing one target changes only that inference object.
5. Product add, correction, and candidate fallback use the same catalog panel;
   `Esc` closes it and keyboard focus does not reach obscured controls.
6. A worker-requested retake shows the compact notice over the capture
   workspace and `다시 촬영` returns directly to live capture.
7. Payment remains unavailable until every detected object is resolved.
8. Rapid scan, candidate, correction, retake, and quantity input does not create
   duplicate sessions, objects, resolutions, or order lines.
9. Customer UI contains no malformed Korean or raw `bread`/`sandwich` category
   IDs.
10. Canonical model, provenance, confidence, decision path, SKU/count/location,
    and fail-closed `Unknown` contracts are unchanged.

## Test strategy

- Controller regression tests cover repeated overrides, restoration to the AI
  mapped product, automatic transition after the last candidate, and payment
  blocking while unresolved.
- Database integration tests verify resolution history and exactly one current
  resolution after repeated correction.
- Widget tests exercise all three states through real components, including
  image/row synchronization, candidate selection, catalog reuse, error
  retention, focus, `Esc`, and numbered duplicate correction.
- Golden tests compare the automatic and candidate states at both kiosk sizes
  and verify the shared skeleton.
- Existing catalog, audit, checkout, scanner, and payment suites remain green.
- Final verification includes `flutter analyze`, focused tests, the full Flutter
  test suite, a Windows Release build, and actual click testing against the
  configured 1.1.0 packaged inference worker.

## Out of scope

- No model, calibration, threshold, fusion-policy, or worker changes.
- No catalog SKU, price, or product-name changes.
- No administrator workflow redesign.
- No new customer features, marketing copy, animation, or decorative visual
  system.
