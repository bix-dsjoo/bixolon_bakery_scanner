# BIXOLON brand camera evaluator design

## Goal

Rebrand the Windows bakery camera evaluator as a BIXOLON industrial scan
console without changing capture, inference, result, or timing behavior.

## Brand rules applied

- Use BIXOLON Orange `#EE7203` as the primary action and readiness accent.
- Use the approved black/gray palette for surfaces and text.
- Use Pretendard first, with the current Korean-capable system fallback.
- Keep the BIXOLON wordmark unmodified, with clear space at least equal to the
  wordmark height; do not tint the wordmark.
- Use the BIXOLON X diagonal motif only as a restrained, low-contrast
  background element. It must not reduce camera or result readability.

## Screen composition

- Header: a compact white product bar with an unmodified BIXOLON Orange
  wordmark, product name, and quiet inline status. It has only a one-pixel
  bottom divider: no colour band and no decorative motif.
- Camera stage: a black, square-cornered work surface occupying about 70
  percent of the screen. It has a single hairline border and no background
  artwork over or beside the live image.
- Result rail: a flat white pane separated by one vertical divider, not a
  receipt card. It retains the existing hierarchy: headline, counts, object
  rows, and collapsed timing/model details.
- Primary action: `분석하기` uses BIXOLON Orange with a compact 6px radius.
  `다시 촬영` is a neutral outlined secondary action. There is only one
  primary action in every state.

## Semantic colors

- Brand Orange controls only the primary action, a compact readiness dot, and
  a selected-row keyline. It is not used as a band, a panel background, or
  decoration.
- Confirmed detection remains teal; Unknown remains amber; error remains red.
  This preserves established visual meaning in boxes and rows.

## Interaction and accessibility

- Existing 44px action targets, focus visibility, single-flight analysis,
  Korean status copy, and right-rail-only scrolling remain unchanged.
- Controls use small, consistent radii, one-pixel neutral borders, visible
  focus rings, and state-resolved disabled styling. Decorative motifs are
  removed.

## Scope and verification

Only Flutter theme, UI composition, local assets, and corresponding UI tests
change. The worker protocol, camera service, models, thresholds, and result
contracts are not changed. Verify theme tokens, semantic states, focus, both
supported window sizes, full Flutter tests, analyzer, and Windows release
build.
