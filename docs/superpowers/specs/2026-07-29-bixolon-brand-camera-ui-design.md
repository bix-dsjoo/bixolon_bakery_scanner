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

- Header: white, BIXOLON Orange wordmark at left, `Bakery AI Scanner` product
  title beside it, quiet camera/device status at right.
- Camera stage: black surface occupying about 70 percent of the screen.
  A narrow Orange readiness accent and a subtle X motif appear only outside
  live image content.
- Result rail: white, receipt-like column. It retains the existing hierarchy:
  headline, counts, objects, timing/model disclosures.
- Primary action: `분석하기` uses BIXOLON Orange. `다시 촬영` is a black outlined
  secondary action. There is only one primary action in every state.

## Semantic colors

- Brand Orange controls only action, readiness, selection, and non-semantic
  decoration.
- Confirmed detection remains teal; Unknown remains amber; error remains red.
  This preserves established visual meaning in boxes and rows.

## Interaction and accessibility

- Existing 44px action targets, focus visibility, single-flight analysis,
  Korean status copy, and right-rail-only scrolling remain unchanged.
- The header and visual motif are decorative and do not enter the semantic
  navigation order.

## Scope and verification

Only Flutter theme, UI composition, local assets, and corresponding UI tests
change. The worker protocol, camera service, models, thresholds, and result
contracts are not changed. Verify theme tokens, semantic states, focus, both
supported window sizes, full Flutter tests, analyzer, and Windows release
build.
