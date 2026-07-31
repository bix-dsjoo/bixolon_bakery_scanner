# Bread Six-View Capture Guide Design

**Date:** 2026-07-31
**Status:** Approved visual direction; written-spec review pending

## 1. Responsibility and acceptance test

Create one landscape, illustration-led guide for a POS/kiosk screen. A first-time
operator must understand within a few seconds that one bread item must be
rotated so each of its six sides can be photographed.

The guide passes when an unfamiliar viewer can correctly infer all of the
following without additional instruction:

1. place one bread item at the center of the implied six-sided volume;
2. recognize six distinct capture directions mapped to the volume's faces;
3. rotate or flip the bread to expose each indicated face; and
4. capture six images, one for each numbered direction.

## 2. Intended display

- Primary surface: landscape POS/kiosk display.
- Target composition ratio: 16:9.
- The image is illustration-led and must remain understandable without a
  paragraph of supporting copy.
- Use generous clear space and strong contrast so the guide remains legible
  when scaled down inside the kiosk UI.

## 3. Recommended composition

Use one dominant spatial diagram. Do not split attention between the main
diagram and a separate thumbnail sequence.

### 3.1 Main diagram

- Place one generic, appetizing bakery bread at the visual center.
- Enclose it in a transparent dotted-line cuboid.
- Place six thick directional arrows outside the cuboid, each perpendicular to
  and terminating at the center of one face: front, back, left, right, top, and
  bottom.
- Place one large orange number badge, `1` through `6`, at the outer tail of
  each arrow.
- Render arrows or segments belonging to hidden rear geometry with a dotted
  treatment so the three-dimensional mapping remains readable.
- Do not show a camera icon or a curved rotation arrow.
- The cuboid is a spatial guide only; it must not look like a physical box,
  package, oven, or cage.

### 3.2 Minimal copy

Use only one short Korean heading:

> 빵의 6면이 보이도록 돌려 촬영해 주세요

Do not add explanatory paragraphs, technical terms, or small-print notes.
The six face arrows and their number badges carry the operational instruction.

## 4. Visual language

- Style: polished instructional illustration with a softly dimensional bread,
  clean vector-like guide lines, and simple UI-grade icons.
- Background: white or very light warm gray.
- Primary line color: deep navy or charcoal.
- Step accent: warm orange.
- Bread color: natural golden brown, visually distinct from the orange step
  markers.
- Dotted cuboid: clearly visible but subordinate to the bread and arrows.
- Arrows: thick, straight, consistent, and visually attached to individual
  cuboid faces rather than to the bread as a generic rotation gesture.
- Avoid photorealistic environmental details, hands, counters, trays, multiple
  breads, decorative props, or busy shadows.

## 5. Misinterpretation controls

- Do not show a camera icon; it adds visual weight without clarifying which
  faces must be captured.
- Do not use circular arrows; they communicate generic rotation but do not map
  the six required views.
- Do not add a six-thumbnail strip; it competes with the spatial diagram.
- Each number must belong unambiguously to one arrow and one cuboid face.
- Arrowheads terminate at face centers and never appear to pierce the bread.
- Keep visible and hidden directions distinguishable through solid versus
  dotted treatment.
- Do not imply six breads; the diagram contains one bread only.

## 6. Output

- One final 16:9 PNG suitable for a POS/kiosk interface.
- Preferred working size: 1920 × 1080 pixels.
- Intended repository destination:
  `docs/assets/guides/bread-six-view-capture-guide.png`.
- No implementation, UI integration, or alternate-language variant is in
  scope for this image request.

## 7. Visual review checklist

- The Korean heading is spelled correctly and fully legible.
- Numerals 1-6 each appear exactly once.
- Six arrows map one-to-one to the cuboid's six faces.
- No camera icon or circular rotation arrow appears.
- Each straight arrow terminates at its intended face center.
- The dotted cuboid remains visible at kiosk scale.
- Hidden rear geometry is distinguishable without becoming cluttered.
- No unintended extra bread, face, hand, label, or arrow appears.
- Top and bottom directions are unmistakably opposite.
- The composition remains clear at both full-screen and reduced kiosk-panel
  sizes.
