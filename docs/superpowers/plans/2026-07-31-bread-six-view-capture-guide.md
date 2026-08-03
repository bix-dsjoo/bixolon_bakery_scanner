# Bread Six-View Capture Guide Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce one kiosk-ready illustration that maps six numbered capture directions directly to the six faces surrounding one bread item.

**Architecture:** Generate a single 16:9 raster illustration from the revised face-mapping specification, then inspect the result against an explicit visual checklist. Iterate only when a checklist requirement fails, and retain one approved PNG as the deliverable.

**Tech Stack:** OpenAI ImageGen, local image inspection, PNG

## Global Constraints

- The primary surface is a landscape POS/kiosk display.
- The final composition ratio is 16:9, with a preferred working size of 1920 × 1080 pixels.
- The main diagram uses one bread inside a transparent dotted-line cuboid.
- Six numbered straight arrows map one-to-one to the cuboid's six faces.
- No camera icon, circular rotation arrow, or thumbnail strip appears.
- The only Korean copy is `빵의 6면이 보이도록 돌려 촬영해 주세요`.
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
dotted-line isometric cuboid at the center. Around the cuboid, place
exactly six thick straight deep-navy arrows, each perpendicular to and
terminating at the center of one distinct face: front, back, left, right,
top, and bottom. At the outer tail of each arrow place one large warm-
orange circular number badge, using 1, 2, 3, 4, 5, and 6 exactly once.
Use a dotted treatment for hidden rear-direction geometry so all six
directions remain readable in two dimensions. Add only this Korean heading
at the top: "빵의 6면이 보이도록 돌려 촬영해 주세요". Use a white or very
light warm-gray background, precise navy guide lines, natural bread color,
clean vector-like instructional styling, generous whitespace, and strong
kiosk readability. Do not show any camera icon, circular rotation arrow,
thumbnail strip, hands, people, counters, trays, extra breads, explanatory
copy, watermark, logo, or decorative scenery.
```

- [ ] **Step 2: Inspect the generated image**

Open the raster at original detail and verify all of the following:

```text
[ ] 16:9 landscape composition
[ ] Korean heading is exact and legible
[ ] one dominant bread is inside a dotted cuboid
[ ] exactly six straight arrows are visible
[ ] arrows map one-to-one to front, back, left, right, top, and bottom faces
[ ] each arrow terminates at its intended face center
[ ] badges 1-6 each appear exactly once and belong to one arrow
[ ] hidden rear directions remain distinguishable
[ ] top and bottom are unmistakably opposite
[ ] no camera, circular arrow, thumbnail strip, extra bread, hand, or label appears
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
