# BIXOLON Bakery Kiosk Visual Redesign

**Date:** 2026-07-31
**Status:** Approved design direction; implementation awaits written-spec review
**Scope:** Customer kiosk visual system and layout
**Version constraint:** Keep application version `1.1.0`

## 1. Objective

Redesign the customer-facing kiosk so it looks like a mature, continuously
operated product rather than a generated collection of cards. Preserve every
checkout capability and the existing customer flow while rebuilding the
visual system, shared shell, density, alignment, and screen composition.

The redesign must make three relationships immediately understandable:

1. what the camera captured;
2. which detected object maps to which store product; and
3. what the customer can confirm, correct, or pay for next.

The product should feel calm, operational, and trustworthy. Decoration is
subordinate to comprehension.

## 2. Non-goals

This redesign does not:

- add or remove customer capabilities;
- change detector, classifier, fusion, or fail-closed acceptance behavior;
- change SKU, count, confidence, provenance, or audit contracts;
- add a new checkout step;
- remove catalog selection, quantity editing, count mismatch, retake,
  payment, completion, or administrator entry;
- expose model scores, hashes, policy names, or technical evidence to
  customers;
- introduce gradients, glow, blur, glassmorphism, decorative badges, or
  marketing copy.

`Unknown` remains a correct fail-closed result and is never converted into an
arbitrary registered SKU.

## 3. Existing flow to preserve

```text
Ready
  -> Analyzing
  -> Retake required, when the result is unsafe
  -> Customer review, when an object needs a choice
  -> Order review
  -> Paying
  -> Payment complete
  -> Ready for the next customer
```

The redesign changes how these states are composed, not when or why they
occur.

## 4. Diagnosed visual problems

### 4.1 Shared shell

- Brand, kiosk name, and page title repeat vertically and consume too much
  height.
- Customer screens use inconsistent maximum widths (`920` and `1240`).
- The action footer is painted only inside the centered content constraint,
  creating a white slab that stops abruptly on both sides.
- Screens without an action still reserve an empty footer.
- The floating administrator control does not belong to the header grid.

### 4.2 Information hierarchy

- Routine guidance is presented as a colored rounded card, giving it the same
  visual weight as actionable states.
- Orange is used for primary actions, tertiary actions, status, labels, and
  selection, so the primary action loses hierarchy.
- Large empty regions separate related content instead of clarifying it.
- Product names and their quantity/edit controls are too far apart.

### 4.3 Component language

- Rounded cards are used for structural panes, guidance, candidates, and
  catalog choices.
- Nested cards obscure containment and make the UI look assembled from
  generic components.
- Icons are attached to actions that are already clear from their labels.
- Large radii and repeated pale fills create an artificial bento-grid feel.

### 4.4 Trust and continuity

- In the all-accepted path, the order screen removes the capture and boxes.
- A customer cannot visually connect a product row to its detected bread.
- Screen width and density change between stages, making one kiosk feel like
  several unrelated pages.

## 5. Design direction

### 5.1 Product character

The visual reference is a mature operational product: the density and
alignment discipline of GitHub, Stripe Dashboard, Google Admin, Shopify
Admin, Linear, Carbon, and Microsoft 365, without copying their brand colors,
icons, or signature decoration.

The bakery-specific signature is the bidirectional relationship between the
real tray image and the commercial order. This relationship, rather than a
decorative motif, is the memorable element.

### 5.2 Principles

- Express hierarchy with position, alignment, spacing, and type before color.
- Use one brand accent: the existing BIXOLON orange.
- Allow one filled primary action per screen.
- Use cards only when an object is genuinely independent or floating.
- Prefer spacing and one-pixel dividers for grouping.
- Keep routine information neutral; reserve tinted surfaces for states that
  require attention.
- Keep customer copy short, factual, and action-oriented.
- Use icons only when they materially improve recognition.
- Maintain at least 48 px touch targets and visible keyboard focus.

## 6. Visual system

### 6.1 Color

```text
canvas          #F7F7F5
surface         #FFFFFF
surface-subtle  #F1F1EE
ink             #1B1B1B
muted-ink       #666560
divider         #DDDDD8
accent          existing BIXOLON orange
success         existing confirmed semantic color
warning         existing uncertainty semantic color
error           existing error semantic color
focus           existing accessible focus color
```

Orange is limited to:

- the current primary action;
- the actively selected detected object;
- a state that explicitly requires customer attention; and
- a small brand wordmark.

Routine tertiary actions use neutral ink.

### 6.2 Typography

Keep Pretendard with the existing Korean fallback stack.

```text
page title       20 / 28, weight 700
panel title      16 / 24, weight 600
row title        14 / 20, weight 600
body             14 / 20, weight 400
supporting text  12 / 18, weight 400 or 500
total amount     20 / 28, weight 700, tabular figures
button label     14 / 20, weight 600
```

No customer heading exceeds 20 px inside the app shell.

### 6.3 Spacing and shape

```text
spacing scale          4, 8, 12, 16, 24, 32
control radius         6
image/panel radius     8
structural border      1
default elevation      0
floating elevation     one subtle shadow only
```

Pill shapes are not used for general buttons or category controls.

## 7. Shared kiosk shell

All customer screens use the same full-window shell.

### 7.1 Header

- Full-window width with a single bottom divider.
- Inner content follows the common 1240 px grid.
- Target height is 60 px at 100% text scale.
- Left side: `BIXOLON Bakery · current stage`.
- Right side: neutral tertiary `관리자`.
- Remove the vertical stack of wordmark, kiosk name, and page title.

```text
┌────────────────────────────────────────────────────────────┐
│ BIXOLON Bakery · 주문 확인                         관리자 │
└────────────────────────────────────────────────────────────┘
```

### 7.2 Body

- Common maximum width: 1240 px.
- Horizontal margin: 24 px at 1280 and 1024 kiosk widths.
- No page-level scrolling at 100% text scale.
- Local task-panel scrolling is allowed when content or 200% text requires
  it.

### 7.3 Action rail

- The rail background and top divider span the full window width.
- Target height is 76 px at 100% text scale.
- The button aligns to the current task column on split screens.
- The button spans the usable content width on single-pane screens.
- If a state has no action, the action rail is absent rather than filled with
  an empty placeholder.

This eliminates the centered white slab and keeps the action visually tied to
the work being performed.

## 8. Screen designs

### 8.1 Ready

```text
compact header
one-line placement guidance
camera preview filling the remaining body
full-width action rail with one scan action
```

- Keep the real camera aspect ratio.
- Remove the large routine status card.
- Present the guidance as one neutral information row.
- Keep one primary `빵 확인하기` action.
- The entire tray must remain visible at 1024x720 and 1280x820 without
  page-level scrolling.

### 8.2 Analyzing

- Keep the compact header.
- Show a concise progress message and one progress indicator.
- Use the available camera/capture surface when it is already available;
  otherwise use the neutral body canvas.
- Do not show an empty action rail.
- Do not add progress percentages or fabricated timing.

### 8.3 Retake required

- Keep one clear explanation and one primary retake action.
- Use a tinted state surface only because customer attention is required.
- Keep manual entry subject to the existing retry policy.
- Do not expose model or policy detail.

### 8.4 Customer review

At kiosk width, use the established 60/40 operational split.

```text
┌ capture and canonical boxes ┬ selected exception and choices ┐
│                              │                                 │
│                              │                                 │
└──────────────────────────────┴─────────────────────────────────┘
```

- The capture is the dominant left surface.
- Avoid separate rounded outer cards for both panes.
- Use one vertical divider and pane spacing.
- Give only the selected or unresolved box the orange treatment.
- Keep all object selectors visible without horizontal scrolling for up to
  five objects.
- Replace card-like selectors with compact segments.
- Keep catalog search in the right task context.

### 8.5 Order review

The all-accepted path uses the same split workspace instead of removing the
capture.

```text
┌ capture and all boxes ┬ product rows, quantity, edit, total ┐
│                       │                                     │
│                       │                                     │
└───────────────────────┴─────────────────────────────────────┘
full-window action rail, action aligned to the task column
```

- A capture box and its product row select each other.
- Selection is communicated by outline, text, and subtle background, not
  color alone.
- Product rows use dividers, not cards.
- Product name, unit price, quantity, and edit action stay visually close.
- Total follows the last row with one stronger divider.
- Product add and count mismatch remain lower-hierarchy actions.
- The payment action remains the sole filled action.

This does not add a checkout step or capability; it restores the evidence
context inside the existing order-review state.

### 8.6 Catalog

- Customer review and order correction keep the originating context visible.
- Catalog content occupies the task pane or a right-side floating panel.
- Product addition retains the same catalog capability and session snapshot.
- Search is compact and functional.
- Featured products and categories use 6 px controls rather than pills.
- Product results are plain rows with name, category, and price.
- Only a genuinely floating side panel receives a subtle shadow.

### 8.7 Paying and completion

- Use the compact shell and restrained typography.
- Show factual save/payment progress only.
- Completion presents the result and next-customer action without decorative
  cards or marketing copy.

## 9. Interaction and state behavior

- Clicking a canonical box selects the matching customer task or order row.
- Clicking an object selector or order row selects the matching box.
- Selection never changes the inference result by itself.
- Customer correction uses the existing controller methods and audit path.
- Catalog close returns to the exact originating task without changing the
  checkout state.
- The action rail never covers scrollable content.
- Keyboard focus remains visible on boxes, rows, buttons, search, and
  quantity controls.

## 10. Accessibility and responsive behavior

- Required kiosk sizes: 1024x720 and 1280x820.
- Required text scales: 100% and 200%.
- At 100%, ready, review, and order require no page-level scroll.
- At 200%, the capture remains visible and only the task pane may scroll.
- All actions have at least a 48x48 target.
- State is never communicated through color alone.
- Reading order follows header, capture summary, task, total, and primary
  action.
- High-contrast focus treatments remain visible against neutral and selected
  surfaces.

## 11. Implementation boundaries

The visual redesign may reshape:

- the shared customer scaffold;
- header and action-rail composition;
- layout constraints and pane proportions;
- typography, spacing, borders, radius, fills, and shadows;
- customer-screen widget composition;
- capture-to-row selection presentation; and
- catalog presentation within the existing flow.

It must not change:

- inference acceptance;
- the phase transition contract;
- catalog snapshot identity;
- audit persistence;
- payment semantics;
- admin data behavior; or
- application version.

## 12. Verification

### Automated

- Add failing widget tests before each behavior-affecting layout change.
- Verify a full-width header and action rail.
- Verify no empty action rail during analysis.
- Verify ready preview visibility at both kiosk sizes.
- Verify order review contains capture and task panes.
- Verify box-to-order-row selection in both directions.
- Verify catalog open/close retains origin context.
- Verify 48 px touch targets and 200% text support.
- Update and inspect ready, analyzing, review, order, catalog, retake, paying,
  and completion goldens.
- Run static analysis and the full Flutter suite.
- Build and verify the version 1.1.0 Windows release payload.

### Live UX review

Exercise without initiating payment:

1. ready at 1024x720 and 1280x820;
2. analyzing;
3. all-accepted order review;
4. mixed accepted/exception review;
5. box-to-task and box-to-order selection;
6. catalog open, search, close, and correction;
7. count mismatch and retake; and
8. administrator-entry confirmation.

Inspect visual hierarchy, crop behavior, local scrolling, footer continuity,
and focus after every transition.

## 13. Acceptance criteria

- The header no longer vertically repeats brand and page identity.
- No central white footer slab is visible.
- Screens without actions have no empty action rail.
- Every customer screen uses the same horizontal grid.
- The tray remains fully visible in the ready state at required kiosk sizes.
- Customer review and order review preserve the capture context.
- Up to five detected objects are visible without horizontal selector
  scrolling.
- Product lists are divider-based rather than card-based.
- Only one filled primary action is visible per screen.
- No gradients, glow, blur, glass, nested decorative cards, or excessive
  radius are introduced.
- Functionality, inference truth, audit behavior, and checkout phase flow
  remain unchanged.
