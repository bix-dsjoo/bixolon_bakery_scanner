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

The kiosk must look like a customer-facing member of the production BIXOLON
POS family. It adopts the POS system's typography, color semantics, component
geometry, divider-led structure, and spacing rhythm without copying the dense
operator layout.

## Production POS reference audit

The proposal is based on these production POS frames:

- `1593:51015`: empty order and product browsing
- `2602:39407`: populated order and product browsing
- `2615:42466`: card approval dialog
- `6355:37402`: table map and operational actions
- `1844:55007`: packaging order management
- `2615:45475`: simple-payment dialog

All six frames use a 1024 x 768 work surface and a 61 px shared navigation
shell. Their recurring visual language is:

- Pretendard with a compact 12–16 px working range;
- 13 px body text as the primary information density;
- 4, 8, 12, and 16 px spacing increments;
- white surfaces, neutral gray borders, and almost no elevation;
- 3–5 px control radii, with 10 px reserved for large dialogs;
- BIXOLON orange for brand, selection, and transactional confirmation;
- pale orange for selected rows and active task context;
- dark blue for persistent operator commands;
- one-pixel dividers and background changes instead of nested cards;
- reusable navigation, button, tab, segmented-control, list, table, tag,
  icon-button, and popup-title components.

The kiosk should inherit the discipline, not the staff-only density. Customer
touch targets remain at least 48 px and body text is one step larger where
viewing distance requires it.

## Visual character

The intended feeling is direct, dependable, and operational. The design should
look like dedicated BIXOLON equipment rather than a generic app:

- white work surfaces with clearly bounded regions;
- short labels and immediate feedback;
- no decorative card grid, gradient, glow, glass, or floating ornament;
- a small number of repeatable component forms;
- strong emphasis only on the current task and next action;
- visible evidence of what the camera recognized.

## Decisions

### Shared header

- Use 60 px of header content plus a 1 px bottom divider, matching the
  production POS shell.
- Use a fixed 24 px horizontal inset at customer-kiosk widths.
- Place the BIXOLON wordmark and current stage as one left-aligned group with
  a 16 px gap. Remove the vertical separator and redundant kiosk-name text.
- Render the stage with the `title` text token, not a large page heading.
- Show the administrator action only on the Ready screen, at the far right of
  the header. It is a neutral tertiary text action, not an orange action.
- Hide the administrator action from analyzing, retake, review, order,
  payment, and completion states.

### Ready screen

- Remove the white camera overlay entirely. It is not a customer-facing
  control and currently resembles an unexplained selection box.
- Retain exactly one short placement instruction: `트레이를 카메라 아래에
  맞춰주세요.`
- Place that sentence once, above the camera and aligned with its left edge.
- Remove the status icon, title, and duplicate supporting sentence.
- Keep the uncropped 16:9 camera preview as the visual focus and retain the
  existing bottom primary scan action.
- Use a 5 px camera radius and no shadow.

### Order screen

- Preserve the existing left captured-image/right order two-column workspace,
  overlay behavior, box-to-row and row-to-box selection, quantity editing,
  catalog behavior, mismatch behavior, and payment flow.
- Replace the current 20 + 1 + 20 px inter-pane gutter with 12 + 1 + 12 px.
- Align both panel titles, list content, totals, and footer controls to a
  common top and side grid.
- Use pale orange selection fill, an orange detection outline, and dark text.
  Do not add a colored left stripe.
- Tighten row spacing and align product name, unit price, quantity, and edit
  controls to a consistent baseline.
- Keep the total as the only visually strong element in the order footer.
- Style `상품 추가` and `실제 빵 수가 달라요` as compact neutral outlined
  secondary buttons below the total. Their labels and callbacks stay exactly
  as they are.
- Keep the full-width payment rail and orange transactional action.

## Design tokens

### Color

Use the production POS values and semantic roles:

| Token | Value | Kiosk role |
| --- | --- | --- |
| `brand.orange` | `#EE7203` | wordmark, selected detection, primary transaction |
| `brand.orangeSubtle` | `#FCEAD9` | selected order row or active choice |
| `brand.orangeBorder` | `#F5AA68` | optional selected-control border |
| `brand.orangeDisabled` | `#FAD5B3` | disabled orange action |
| `action.blue` | `#184C9F` | keyboard focus and operational emphasis |
| `gray.900` | `#000000` | primary text and totals |
| `gray.800` | `#424242` | standard labels and secondary headings |
| `gray.700` | `#5C5C5C` | secondary text |
| `gray.600` | `#757575` | tertiary controls |
| `gray.500` | `#8F8F8F` | helper text and inactive labels |
| `gray.400` | `#C2C2C2` | stronger borders |
| `gray.300` | `#D8D8D8` | disabled fills and controls |
| `gray.200` | `#E8E8E8` | dividers |
| `gray.100` | `#F5F5F5` | quiet background |
| `white` | `#FFFFFF` | working surface |
| `semantic.red` | `#CC2427` | destructive or error state |
| `semantic.green` | `#268B20` | completed state |
| `semantic.teal` | `#1895A5` | informational task state |

Rules:

- orange does not style tertiary or exception actions;
- blue is not a second competing primary action on customer screens;
- state colors always include text or shape, never color alone;
- selected rows use the pale-orange surface instead of shadow or glow;
- the base customer work surface is white, with gray-100 used only where a
  region needs separation.

### Typography

Use Pretendard exclusively, zero letter spacing, and the POS line-height
ratios. Do not mix arbitrary Material defaults with these roles.

| Token | Font | Use |
| --- | --- | --- |
| `label` | 12 / 16.8, Medium 500 | helper, metadata, low-priority label |
| `body` | 13 / 17.6, Regular 400 | dense order details |
| `bodyMedium` | 13 / 17.6, Medium 500 | row values and compact controls |
| `labelMedium` | 14 / 19.6, Medium 500 | customer guidance and button support |
| `labelStrong` | 14 / 19.6, SemiBold 600 | row and section emphasis |
| `title` | 15 / 20.3, SemiBold 600 | stage and panel titles |
| `action` | 16 / 21.6, SemiBold 600 | primary action labels |
| `amount` | 18 / 24.3, SemiBold 600 | total and payment amount |
| `numericLarge` | 24 / 32.4, Medium 500 | dedicated numeric input only |

Customer adaptations:

- use `labelMedium` rather than 13 px body for the single Ready instruction;
- use `title` for header and pane titles;
- use `bodyMedium` for product name and `label` or `body` for unit price;
- use `amount` for the total;
- do not use 20 or 24 px bold headings in the normal checkout shell.

### Spacing, borders, and shape

The base unit is 4 px.

| Role | Value |
| --- | --- |
| inline icon/label gap | 4 or 8 |
| row internal gap | 8 |
| compact group gap | 12 |
| section gap | 16 |
| screen horizontal inset | 24 |
| header height | 60 + 1 divider |
| control radius | 5 |
| image radius | 5 |
| modal radius | 10 |
| structural border | 1 |
| focus border | 2 |
| minimum touch target | 48 |

Do not use a 20 px gap where 16 or 24 has not been chosen intentionally.
Structural panes have no radius and no shadow. Only modal or side-panel layers
may float above the work surface.

## Component system

### `CheckoutHeader`

- one shared 60 + 1 px shell;
- wordmark, 16 px gap, stage title on the left;
- Ready-only administrator text action at the far right;
- no kiosk-name repetition, divider ornament, or secondary navigation row.

### `PrimaryActionRail`

- full-window white surface with one-pixel gray-200 top border;
- 24 px horizontal and 10 px vertical padding;
- one 56 px orange primary button with 5 px radius;
- no secondary action inside the rail.

### `ReadyInstruction`

- one line of `labelMedium` text in gray-800;
- no icon, status badge, card, border, or explanatory subtitle;
- 12 px gap to the camera.

### `CameraViewport`

- canonical uncropped camera frame;
- 5 px clip radius;
- no placement box or pre-recognition overlay;
- recognized boxes appear only after analysis, when they represent real
  evidence.

### `SplitWorkspace`

- captured evidence and task content remain visible together;
- one-pixel gray-200 divider with 12 px breathing room on both sides;
- no surrounding cards;
- local scrolling only in the task pane when content exceeds its height.

### `OrderRow`

- 12 px horizontal and 8 px vertical content padding;
- product and unit price form one left-aligned text stack;
- quantity and correction controls align on one right-side baseline;
- selected state uses orangeSubtle, without elevation or a colored stripe;
- row separation uses a one-pixel gray-200 divider.

### `QuantityStepper`

- 48 px minimum height, 5 px radius, gray-300 border;
- 48 px minus and plus hit areas;
- 13 px Medium quantity with tabular numerals;
- no orange until the control itself has focus or active adjustment.

### `ExceptionActions`

- `상품 추가` and `실제 빵 수가 달라요` remain separate callbacks;
- each is a 44–48 px neutral outlined button with 5 px radius;
- place them below the total with an 8 px gap;
- gray-800 text and gray-300 border at rest;
- orange is prohibited at rest, because these are rare recovery actions.

### `ModalTaskPanel`

- follow the POS dialog pattern: white surface, 10 px radius, clear title
  row, close action, body, divider, and bottom action area;
- preserve captured evidence behind the panel when useful;
- use dimming only to establish modality, not as decoration;
- one orange confirmation action and one neutral or negative alternative.

## Screen hierarchy

### Ready

```text
60 px header:  BIXOLON  셀프 계산                         관리자
1 px divider
24 px inset
14 px instruction: 트레이를 카메라 아래에 맞춰주세요.
12 px gap
uncropped camera using the remaining height
full-width action rail: 빵 확인하기
```

### Order

```text
60 px header:  BIXOLON  주문 확인
1 px divider
24 px inset
captured evidence (3fr) | 1 px divider | order task (2fr)
                                  order rows
                                  1 px divider
                                  합계              17,000원
                                  [상품 추가] [실제 빵 수가 달라요]
full-width action rail: 17,000원 결제하기
```

The image-to-order selection remains bidirectional. This evidence relationship
is the signature customer interaction and is more important than decorative
branding.

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
3. Header, typography, color, spacing, radius, and component states use the
   POS-derived tokens defined in this document.
4. Exception actions remain usable but visually subordinate to total and
   payment.
5. Customer recognition, correction, and payment behavior remains unchanged.
6. Ready and Order remain usable at 1024 x 720 and 1280 x 820, including 200%
   text scale and keyboard navigation.
7. No structural card, gradient, glow, glass, unnecessary shadow, or
   decorative badge is introduced.
