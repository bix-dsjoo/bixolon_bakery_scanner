# BIXOLON Brand Camera UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Apply the approved BIXOLON industrial-console design system to the Windows bakery camera evaluator without changing inference behavior.

**Architecture:** Keep scanner state, camera capture, worker protocol, and overlay semantics unchanged. Add centralized brand tokens and decorative widgets, then consume them in the existing scanner screen, status strip, and result rail.

**Tech Stack:** Flutter/Dart, existing Material widgets, Windows desktop runner, flutter_test.

## Global Constraints

- Primary action uses BIXOLON Orange `#EE7203`; the wordmark is never tinted.
- Do not use Orange bands, panel fills, or the X motif; use flat panes,
  hairline borders, small radii, and compact inline status components.
- Pretendard precedes Korean-capable system fallback.
- Confirmed teal, Unknown amber, and error red retain their current meaning.
- Preserve one primary action, 44px targets, keyboard focus, and Korean factual copy.
- Do not alter models, worker, camera, timing, or result contracts.

### Task 1: Define restrained BIXOLON component tokens

**Files:**
- Modify: `apps/bakery_camera_flutter/lib/src/ui/app_theme.dart`
- Create: `apps/bakery_camera_flutter/lib/src/ui/bixolon_brand.dart`
- Test: `apps/bakery_camera_flutter/test/ui/bixolon_brand_test.dart`

- [ ] Write failing tests asserting `bixolonOrange == Color(0xFFEE7203)`, result semantic colors differ from Orange, and shared controls expose 1px border/6px radius tokens.
- [ ] Run `flutter test test/ui/bixolon_brand_test.dart` and confirm RED.
- [ ] Implement approved orange/neutral tokens, Pretendard-first text theme, unmodified Orange text wordmark, compact status dot, 1px border, and 6px radius tokens. Remove the X motif.
- [ ] Run focused test and `flutter analyze`; commit `feat: add Bixolon UI tokens`.

### Task 2: Recompose each scan-console component

**Files:**
- Modify: `apps/bakery_camera_flutter/lib/src/ui/scanner_screen.dart`
- Modify: `apps/bakery_camera_flutter/lib/src/ui/status_strip.dart`
- Modify: `apps/bakery_camera_flutter/lib/src/ui/result_rail.dart`
- Test: `apps/bakery_camera_flutter/test/ui/scanner_screen_test.dart`

- [ ] Write failing widget tests for a compact divider-only header, Orange primary action, flat bordered camera/result panes, preserved teal/amber result semantics, disabled styles, and no 1280x820 or 1024x720 overflow.
- [ ] Run `flutter test test/ui/scanner_screen_test.dart` and confirm RED.
- [ ] Add white header with wordmark/title/inline status, 70/30 flat black camera/white result panes, Orange analysis button, neutral outlined recapture button, compact status badges, and dense row/list components. Remove all Orange bands and X artwork.
- [ ] Verify focus, scrolling, one-primary-action state rules, and existing camera/worker status tests; run analyzer; commit `feat: apply Bixolon scan console UI`.

### Task 3: Verify release output and document it

**Files:**
- Modify: `apps/bakery_camera_flutter/README.md`

- [ ] Document BIXOLON token use and preserved result semantic colors.
- [ ] Run `flutter test`, `flutter analyze`, and `flutter build windows --release` from `apps/bakery_camera_flutter`.
- [ ] Launch the release app through `Run-Camera-Prototype.ps1`; inspect header, action, result rail, focus, and both supported sizes.
- [ ] Commit `docs: describe Bixolon camera UI`.
