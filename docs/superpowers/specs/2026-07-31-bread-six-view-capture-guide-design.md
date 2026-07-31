# Bread Six-View Capture Guide Design

**Date:** 2026-07-31
**Status:** Approved visual direction; written-spec review pending

## 1. Responsibility and acceptance test

Create one landscape, illustration-led guide for a POS/kiosk screen. A first-time
operator must understand within a few seconds that the camera stays fixed while
one bread item is rotated and photographed from six sides.

The guide passes when an unfamiliar viewer can correctly infer all of the
following without additional instruction:

1. keep the camera in one place;
2. place one bread item at the center of the implied six-sided volume;
3. rotate or flip the bread rather than moving the camera; and
4. capture six images, one for each indicated view.

## 2. Intended display

- Primary surface: landscape POS/kiosk display.
- Target composition ratio: 16:9.
- The image is illustration-led and must remain understandable without a
  paragraph of supporting copy.
- Use generous clear space and strong contrast so the guide remains legible
  when scaled down inside the kiosk UI.

## 3. Recommended composition

Use a hybrid composition with one dominant spatial diagram and one compact
six-step sequence.

### 3.1 Main diagram

- Place one generic, appetizing bakery bread at the visual center.
- Enclose it in a transparent dotted-line cuboid.
- Show one camera icon in a fixed position in front of the cuboid.
- Use curved rotation arrows around the bread, not an orbiting path around the
  camera.
- The camera icon must not be repeated at multiple locations.
- The cuboid is a spatial guide only; it must not look like a physical box,
  package, oven, or cage.

### 3.2 Six-step strip

Place six compact, evenly spaced direction thumbnails along the lower portion
of the guide. Use large, high-contrast numerals:

1. front;
2. right side;
3. back;
4. left side;
5. top;
6. bottom.

Steps 1-4 communicate horizontal rotation. Steps 5-6 communicate tilting or
flipping the bread. The exact sequence is instructional rather than a required
dataset constraint; its purpose is to make completion easy to track.

### 3.3 Minimal copy

Use only one short Korean heading:

> 빵을 돌려 6면을 촬영해 주세요

Do not add explanatory paragraphs, technical terms, or small-print notes.
Numbers and arrows carry the operational instruction.

## 4. Visual language

- Style: polished instructional illustration with a softly dimensional bread,
  clean vector-like guide lines, and simple UI-grade icons.
- Background: white or very light warm gray.
- Primary line color: deep navy or charcoal.
- Step accent: warm orange.
- Bread color: natural golden brown, visually distinct from the orange step
  markers.
- Dotted cuboid: clearly visible but subordinate to the bread and arrows.
- Arrows: thick enough for kiosk viewing and consistent in shape.
- Avoid photorealistic environmental details, hands, counters, trays, multiple
  breads, decorative props, or busy shadows.

## 5. Misinterpretation controls

- Do not draw an arrow that makes the camera appear to move.
- Do not place six camera icons around the cuboid.
- Do not point all six face arrows toward the fixed camera simultaneously.
- Do not imply six breads; the thumbnails are views of the same bread.
- Keep the bread upright for steps 1-4 and visibly change its pose only for the
  top and bottom views.
- Make the bottom view unmistakable through the thumbnail pose, while keeping
  the overall handling clean and food-safe in tone.

## 6. Output

- One final 16:9 PNG suitable for a POS/kiosk interface.
- Preferred working size: 1920 × 1080 pixels.
- Intended repository destination:
  `docs/assets/guides/bread-six-view-capture-guide.png`.
- No implementation, UI integration, or alternate-language variant is in
  scope for this image request.

## 7. Visual review checklist

- The Korean heading is spelled correctly and fully legible.
- Numerals 1-6 each appear exactly once in the step strip.
- All six views are distinct.
- The camera appears exactly once and remains fixed.
- Rotation arrows belong visually to the bread.
- The dotted cuboid remains visible at kiosk scale.
- No unintended extra bread, face, hand, camera, label, or arrow appears.
- The bottom-view instruction cannot be mistaken for another top view.
- The composition remains clear at both full-screen and reduced kiosk-panel
  sizes.
