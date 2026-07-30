# All-Surfaces Visual Redesign

## Responsibility and acceptance

**Responsibility:** refine every existing customer and administrator surface so
the application reads as a mature operational product without changing
features, user flows, information meaning, destination structure, or the
canonical inference contract.

**Acceptance:** all existing customer and administrator states remain
reachable through the same actions; primary actions remain in their current
regions; repeated cards, decorative color bars, nested boxes, saturated status
fills, and unnecessary action icons are removed or reduced; the interface uses
type, alignment, spacing, thin dividers, lists, tables, and restrained panels
to express hierarchy; and the supported golden, widget, accessibility, and
contract tests pass after their expected visual output is intentionally
updated.

## Scope

The redesign covers every Flutter UI surface under
`apps/bakery_camera_flutter/lib/src/ui`, including:

- the customer ready, analyzing, retake, product confirmation, catalog,
  order, payment, and completion states;
- the administrator shell, dashboard, transaction history and detail, review
  inbox and detail, product management and editor, diagnostics, settings, and
  retention preview;
- the evaluator/scanner result rail and its disclosures; and
- shared theme, buttons, status messages, product rows, quantity controls,
  tables, dialogs, and navigation.

No model, pipeline, inference, persistence, catalog, payment, audit, or
navigation behavior changes are part of this work. No new user-visible feature
or destination is introduced.

## Design direction

The product should feel like a long-running local operations tool: quiet,
precise, legible, and dense enough for repeated use. BIXOLON orange remains the
single accent, but is reserved for the wordmark, the current primary action,
selected controls, and focus/active affordances. Status meaning uses a status
word and icon or shape in addition to restrained semantic color.

The visual system uses:

- canvas `#F7F7F5`;
- paper `#FFFFFF`;
- primary ink `#171717`;
- muted ink `#626262`;
- divider `#E5E3E0`;
- BIXOLON action orange `#EE7203`;
- restrained confirmed, uncertainty, and error colors already owned by the
  theme;
- Pretendard with the existing bundled weights;
- 4 px control radius and 8 px surface radius;
- no decorative gradient, glow, blur, glass effect, or ambient shadow; and
- shadow only for modal dialogs, menus, and genuinely floating layers.

The redesign's signature is a consistent **operational ledger** treatment:
important facts align into stable rows and columns with tabular figures and
hairline dividers. It is specific to a checkout and audit product and replaces
the generic bento-card appearance without adding decoration.

## Shared component rules

### Page framing

Page titles have no left color rule or decorative top bar. A compact title,
optional one-line supporting text, and the existing page-level action occupy a
single header row where width permits. The content begins after a 20–24 px
gap, rather than a large hero-like void.

Customer screens retain their centered maximum width and fixed bottom action
region. Administrator screens retain the left navigation and content region.

### Sections and surfaces

Default grouping uses:

1. section title and optional trailing action;
2. 8–12 px internal spacing;
3. a thin top or bottom divider when adjacency needs a hard boundary; and
4. 20–28 px between peer sections.

A bordered surface is used only when the boundary itself carries meaning, such
as a camera viewport, editable form, warning, selected record, or dialog.
Surfaces never nest as card inside card. Ordinary lists and settings groups use
flat rows.

### Buttons and actions

Each customer screen retains one filled primary action in the existing bottom
action region. Administrator screens use one filled primary action only for
the page's commit or refresh operation. Secondary actions use outlined or
neutral buttons. Tertiary actions use text buttons or compact icon-only
controls with tooltips where the icon is conventional.

Icons are removed from buttons when the action label is already unambiguous.
Destructive actions retain explicit text and semantic color. Focus visibility
and the minimum 44 px target remain.

### Status

Status messages use a small icon, a concrete status label, and concise
supporting text. They use a neutral or lightly tinted background and a
hairline border; they have no left color strip and no fully saturated fill.
Success does not receive more visual weight than an unresolved warning.

### Density and typography

Customer page titles use 24 px bold text; administrator page titles use
20–22 px semibold or bold text. Section headings use 15–16 px semibold text.
Body and table content remain 13–15 px. Metadata uses muted 12–13 px text.
Amounts, counts, hashes, and timings use tabular figures.

## Customer surfaces

The header removes the orange left rule while retaining the BIXOLON wordmark,
page name, divider, and existing position. Status banners become compact
inline guidance rows. Camera and evidence boundaries remain explicit because
they represent real image regions.

Product confirmation and order review use flat product rows separated by
dividers. Product name, price, quantity, and correction actions remain in the
same reading order. Secondary actions such as searching the catalog, adding a
product, or reporting a mismatch become text-level actions without decorative
icons unless the icon is required for recognition.

The bottom primary action remains fixed and filled. Its label remains
action-oriented. The bottom action region loses any unnecessary floating-card
appearance.

Retake, manual-cart, and completion illustrations remain secondary to the
instruction and action. Their size and surrounding whitespace are reduced
when they compete with operational content.

## Administrator surfaces

### Shell and navigation

The left navigation remains 264 px at full width and retains the current
destination order. The administrator-mode chip becomes quiet utility text
instead of a decorative pill. Selected navigation uses a subtle neutral
background and a narrow active indicator contained inside the navigation row;
this indicator communicates selection and is not a section-title decoration.
The return-to-customer action remains at the bottom as a secondary button
without a redundant icon.

### Dashboard

The four top facts become a single summary ledger with four aligned columns
inside one restrained surface or flat ruled region. Icons are removed. Only
attention and unavailable states use semantic color.

Operational rates become compact rows or columns below a shared heading rather
than five separate cards. Recent attention becomes a divided list with a clear
text action; decorative leading arrows are removed. Information order and
selection behavior remain unchanged.

### Transactions and review

Transaction history uses the existing filter area followed by a dense ruled
table/list. Filter chips are reduced to compact controls and only selected
filters receive accent treatment. Transaction detail uses a stable two-column
fact layout and a chronological ruled timeline. Evidence tables remain tables,
not cards.

Review inbox rows become a divided work queue. Review detail uses a fixed fact
column beside the decision form where width permits, stacking in the same order
on compact windows. Choice controls remain explicit and accessible, but avoid
pill-shaped badge styling.

### Products

Product management becomes a dense product list with one row per product:
thumbnail, product and price, sale state, recognition state, and edit action.
The same content and ordering are retained. Large product cards and nested
status chips are removed. The product editor groups fields with section
headings and dividers rather than wrapping every group in a card.

### Diagnostics

The readiness banner becomes a neutral status summary row. The refresh action
stays near the top but becomes a normal-width page action rather than a
full-width orange bar. Connectivity and pipeline facts use ruled definition
lists. Long hashes and provenance remain readable and copyable.

### Settings

Settings groups become a single flat form with section headings, short
descriptions, aligned labels and controls, and dividers between groups. The
existing apply timing and save behavior remain. The retention preview stays a
secondary action and loses its decorative icon.

## Responsive behavior

At widths below the existing `1100` px breakpoint, the administrator drawer
behavior remains. Two-column facts and forms stack without changing reading
order. Customer content retains its current supported-window bounds.

No screen may overflow at `1280×820` or `1024×720`. Text scaling, keyboard
focus, touch targets, semantic labels, and scroll reachability remain
supported.

## Testing and evidence

Before implementation, add or update design-system/widget tests that assert:

- the shared customer header and status component do not render decorative
  left strips;
- primary, secondary, and tertiary actions use distinct button families;
- dashboard metrics render as one grouped ledger rather than independent
  cards;
- product and attention collections render as divided lists;
- settings and diagnostics use flat sections;
- status text remains present alongside semantic icons or color; and
- all existing navigation and action callbacks remain unchanged.

Run focused widget tests first, then all Flutter UI tests, accessibility tests,
and golden tests. Regenerate only the golden images changed by the approved
visual redesign. Existing inference, checkout, audit, persistence, and
production-runtime contract tests must remain green. Unavailable platform or
artifact suites are reported as unverified, never passed.

## Self-review

- No features, destinations, data, or user-flow steps are added or removed.
- The chosen structural redesign changes information presentation, not
  information architecture.
- The single accent and operational-ledger signature are specific and
  restrained.
- Cards, nested cards, decorative strips, saturated fills, and action icons are
  explicitly addressed.
- Customer primary actions and administrator task actions remain discoverable.
- No placeholder, unresolved design choice, or contradictory radius/color rule
  remains.
