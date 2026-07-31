# Bread Six-View Capture Guide Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce one kiosk-ready illustration that shows a fixed camera and one bread item rotated through six capture views.

**Architecture:** Generate a single 16:9 raster illustration from the approved design specification, then inspect the result against an explicit visual checklist. Iterate only when a checklist requirement fails, and retain one approved PNG as the deliverable.

**Tech Stack:** OpenAI ImageGen, local image inspection, PNG

## Global Constraints

- The primary surface is a landscape POS/kiosk display.
- The final composition ratio is 16:9, with a preferred working size of 1920 × 1080 pixels.
- The camera appears once in one fixed position.
- The bread, not the camera, is shown rotating or flipping.
- The main diagram uses one bread inside a transparent dotted-line cuboid.
- The lower strip contains six distinct views numbered 1 through 6 exactly once.
- The only Korean copy is `빵을 돌려 6면을 촬영해 주세요`.
- The final image contains no hands, counters, trays, multiple breads, decorative props, or busy environmental detail.
- The final repository destination is `docs/assets/guides/bread-six-view-capture-guide.png`.

---

### Task 1: Generate and visually verify the capture guide

**Files:**
- Consume: `docs/superpowers/specs/2026-07-31-bread-six-view-capture-guide-design.md`
- Create: `docs/assets/guides/bread-six-view-capture-guide.png`

**Interfaces:**
- Consumes: the approved composition, copy, color, and misinterpretation controls in the design specification.
- Produces: one 16:9 PNG that can be placed directly in a landscape POS/kiosk interface.

- [ ] **Step 1: Generate the first image**

Use ImageGen with the approved specification and explicitly request:

```text
Create a polished 16:9 Korean POS/kiosk instructional illustration.
One appetizing generic golden-brown bread sits inside a transparent
dotted-line cuboid at the center. Show exactly one stationary camera icon
in front of the cuboid. Thick curved arrows act on the bread and clearly
show that the bread rotates while the camera remains fixed. Along the
bottom, show six clean, evenly spaced thumbnails of the same bread, with
large orange number badges 1, 2, 3, 4, 5, 6: front, right, back, left,
top, bottom. Keep the bread upright in views 1-4; clearly tilt or flip it
for views 5-6. Add only this Korean heading at the top:
"빵을 돌려 6면을 촬영해 주세요". Use a white or very light warm-gray
background, deep navy guide lines, warm orange accents, natural bread
color, clean vector-like instructional styling, generous whitespace, and
strong kiosk readability. Do not show hands, people, counters, trays,
extra breads, multiple cameras, orbiting camera paths, small explanatory
copy, or decorative scenery.
```

- [ ] **Step 2: Inspect the generated image**

Open the raster at original detail and verify all of the following:

```text
[ ] 16:9 landscape composition
[ ] Korean heading is correct and legible
[ ] one dominant bread is inside a dotted cuboid
[ ] exactly one fixed camera icon is visible
[ ] rotation arrows visually belong to the bread
[ ] badges 1-6 each appear exactly once
[ ] six lower thumbnails are distinct
[ ] views 1-4 communicate horizontal rotation
[ ] views 5-6 clearly communicate top and bottom
[ ] no extra bread, camera, hand, label, or arrow creates ambiguity
```

- [ ] **Step 3: Correct any failed checklist item**

If any item fails, edit or regenerate the image with a prompt that names only
the failed visual requirements while preserving the approved composition.
Repeat original-detail inspection after every revision.

- [ ] **Step 4: Place the approved PNG**

Save the approved image at:

```text
docs/assets/guides/bread-six-view-capture-guide.png
```

Verify the file is a readable PNG and its dimensions have a 16:9 ratio.

- [ ] **Step 5: Commit the guide**

```powershell
git add -- docs/assets/guides/bread-six-view-capture-guide.png
git commit -m "docs: add six-view bread capture guide"
```
