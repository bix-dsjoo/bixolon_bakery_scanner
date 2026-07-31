# Kiosk Hierarchy Refinement

**Date:** 2026-07-31
**Status:** Approved visual direction; implementation awaits written-spec review
**Scope:** Customer-ready and customer-order visual hierarchy
**Version:** 1.1.0

## Objective

Refine the approved customer kiosk design into a simpler, more professional
operational interface. Preserve every checkout, correction, inference, audit,
and payment behavior. This change only adjusts presentation, placement, and
visual priority.

## Decisions

### Shared header

- Use one 56 px header with one bottom divider and a fixed 24 px horizontal
  inset at kiosk widths.
- Place the BIXOLON wordmark and the current stage as a single left-aligned
  group. Remove the redundant kiosk-name text.
- Show the administrator action only on the Ready screen, at the far right of
  the header. It is a neutral tertiary text action, not an orange action.
- Hide the administrator action from analyzing, retake, review, order,
  payment, and completion states.

### Ready screen

- Remove the white camera overlay entirely. It is not a customer-facing
  control and currently resembles an unexplained selection box.
- Retain exactly one short placement instruction: `트레이를 카메라 아래에
  맞춰주세요.`
- Remove the status icon, title, and duplicate supporting sentence.
- Keep the uncropped 16:9 camera preview as the visual focus and retain the
  existing bottom primary scan action.

### Type and spacing system

- Apply a disciplined 4 px base spacing scale: 8, 12, 16, 24, and 32 px.
- Use 20/28 semibold only for a screen-level task title, 16/24 semibold for
  a panel title, 14/20 regular for body copy, and 12/18 medium for supporting
  copy. Avoid multiple bold weights within one small area.
- Use a 56 px header, 24 px page inset, 16 px panel inset, and 1 px neutral
  dividers as the shared structural rhythm.
- Retain a single orange filled control only for the primary next action.

### Order screen

- Preserve the existing left captured-image/right order two-column workspace,
  overlay behavior, box-to-row and row-to-box selection, quantity editing,
  catalog behavior, mismatch behavior, and payment flow.
- Tighten row spacing and align product name, unit price, quantity, and edit
  controls to a consistent baseline.
- Keep the total as the only visually strong element in the order footer.
- Style `상품 추가` and `실제 빵 수가 달라요` as compact, neutral outlined
  secondary buttons below the total. Their labels and callbacks stay exactly
  as they are; only their visual priority and affordance change.

## Constraints and checks

- Do not change any customer action, state transition, model decision,
  catalog revision, persisted audit record, or payment semantics.
- Keep at least 48 px touch targets and visible keyboard focus.
- Update focused widget tests and 1280x820 customer goldens for the changed
  visual contract.
- Validate with formatting, static analysis, the full Flutter test suite, and
  a Windows release build before packaging.

## Acceptance criteria

1. Ready shows no camera overlay and only one placement sentence.
2. Administrator appears at the far right only on Ready.
3. Header, text hierarchy, and spacing follow one repeatable system across
   Ready and Order.
4. Exception actions remain usable but visually subordinate to total and
   payment.
5. Customer recognition, correction, and payment behavior remains unchanged.
