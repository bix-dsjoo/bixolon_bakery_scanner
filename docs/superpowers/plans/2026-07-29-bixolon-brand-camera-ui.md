# BIXOLON Brand Camera UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Apply the approved BIXOLON industrial-console design system to the Windows bakery camera evaluator without changing inference behavior.

**Architecture:** Keep scanner state, camera capture, worker protocol, and overlay semantics unchanged. Add centralized brand tokens and decorative widgets, then consume them in the existing scanner screen, status strip, and result rail.

**Tech Stack:** Flutter/Dart, existing Material widgets, Windows desktop runner, flutter_test.

## Global Constraints

- Primary action uses BIXOLON Orange `#EE7203`; the wordmark is never tinted.
- Pretendard precedes Korean-capable system fallback.
- Confirmed teal, Unknown amber, and error red retain their current meaning.
- Preserve one primary action, 44px targets, keyboard focus, and Korean factual copy.
- Do not alter models, worker, camera, timing, or result contracts.

### Task 1: Define BIXOLON tokens and decorative primitives

**Files:**
- Modify: `apps/bakery_camera_flutter/lib/src/ui/app_theme.dart`
- Create: `apps/bakery_camera_flutter/lib/src/ui/bixolon_brand.dart`
- Test: `apps/bakery_camera_flutter/test/ui/bixolon_brand_test.dart`

- [ ] Write failing tests asserting `bixolonOrange == Color(0xFFEE7203)`, result semantic colors differ from Orange, and brand decoration is excluded from semantics.
- [ ] Run `flutter test test/ui/bixolon_brand_test.dart` and confirm RED.
- [ ] Implement approved orange/neutral tokens, Pretendard-first text theme, unmodified Orange text wordmark, and low-contrast semantic-excluded X motif.
- [ ] Run focused test and `flutter analyze`; commit `feat: add Bixolon UI tokens`.

### Task 2: Recompose the scan console

**Files:**
- Modify: `apps/bakery_camera_flutter/lib/src/ui/scanner_screen.dart`
- Modify: `apps/bakery_camera_flutter/lib/src/ui/status_strip.dart`
- Modify: `apps/bakery_camera_flutter/lib/src/ui/result_rail.dart`
- Test: `apps/bakery_camera_flutter/test/ui/scanner_screen_test.dart`

- [ ] Write failing widget tests for a BIXOLON header, Orange primary action, preserved teal/amber result semantics, and no 1280x820 or 1024x720 overflow.
- [ ] Run `flutter test test/ui/scanner_screen_test.dart` and confirm RED.
- [ ] Add white header with wordmark/title/status, 70/30 black camera/white result composition, restrained X motif outside image content, Orange analysis button, and black outlined recapture button.
- [ ] Verify focus, scrolling, one-primary-action state rules, and existing camera/worker status tests; run analyzer; commit `feat: apply Bixolon scan console UI`.

### Task 3: Verify release output and document it

**Files:**
- Modify: `apps/bakery_camera_flutter/README.md`

- [ ] Document BIXOLON token use and preserved result semantic colors.
- [ ] Run `flutter test`, `flutter analyze`, and `flutter build windows --release` from `apps/bakery_camera_flutter`.
- [ ] Launch the release app through `Run-Camera-Prototype.ps1`; inspect header, action, result rail, focus, and both supported sizes.
- [ ] Commit `docs: describe Bixolon camera UI`.
