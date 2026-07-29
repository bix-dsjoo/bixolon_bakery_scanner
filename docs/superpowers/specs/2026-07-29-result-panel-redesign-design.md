# Bakery result panel redesign

## Purpose

Redesign the right result pane for a model evaluator or store operator who
needs to answer three questions quickly:

1. Did the scan finish and how many objects were found?
2. Which products and quantities were confirmed?
3. Which objects need review, and what are their three candidates?

The redesign changes presentation only. Camera capture, model inference,
classification policy, boxes, selection, and result contracts stay unchanged.

## Evidence from the current screen

The current pane repeats each confirmed result in the image label, the product
count list, and the object list. It also repeats `Unknown`, Top-3 rows, scores,
and decision paths for every unresolved object. The headline gives total,
latency, and device equal visual weight, while the actionable fact - five
objects need review - appears lower in the pane. Confidence is displayed like
an accuracy percentage even though it is a model score.

## Reference principles

- Supabase tables use stable columns, explicit alignment, and one scroll area.
  Empty states keep the same structure as populated states.
- Supabase badges are short metadata, used sparingly rather than as primary
  communication.
- Supabase layout guidance puts actions where the user is already looking and
  omits chrome when the work area is self-explanatory.
- AWS Rekognition separates labels/confidence into a pane and reveals more
  results on demand.
- Roboflow treats boxes and labels as separate visualization layers; a result
  pane does not need to restate every overlay label at all times.

References:

- https://supabase.com/design-system/docs/components/table
- https://supabase.com/design-system/docs/components/badge
- https://supabase.com/design-system/docs/ui-patterns/layout
- https://supabase.com/design-system/docs/ui-patterns/empty-states
- https://docs.aws.amazon.com/rekognition/latest/dg/detect-labels-console.html
- https://docs.roboflow.com/workflows/workflow-blocks/visualize-predictions/bounding-box-visualization

## Information architecture

The pane has four stable regions.

### 1. Outcome header

Show `분석 완료` as the title. Directly below, show three compact values:

- `감지 9`
- `확정 4`
- `검토 필요 5`

Latency and compute device move to quiet metadata on the same header line:
`726 ms · GPU`. Do not repeat total count in a second sentence. During loading,
the same header footprint shows the current factual phase and elapsed time.

### 2. Confirmed quantity table

Show one dense table with `품목` and right-aligned `수량`. It includes only
confirmed product counts. `Unknown` is not a product row; it is represented by
the review-needed count. Rows are 36-40 px tall with hairline separators.

### 3. Review queue

If unresolved objects exist, show `검토 필요 5` followed by compact rows named
`항목 1`, `항목 2`, and so on. Each row has only a warning dot, the leading
candidate name, and its score. The queue is ordered by object order and is the
primary scrollable region. Clicking a row selects the matching image box.

Only the selected unresolved row expands. Its detail shows exactly three
candidates in aligned `순위 / 후보 / 점수` columns. This avoids repeating 15
candidate lines for five unresolved objects.

If there are no unresolved objects, show one quiet success row: `검토할 항목이
없습니다.` Do not render an empty queue card or illustration.

### 4. Secondary technical details

Confirmed per-object rows are hidden by default because product counts and
image labels already communicate them. A collapsed `확정 항목 4개` disclosure
contains per-object confidence and decision path for evaluator use.

`성능 정보` contains press-to-result, capture, worker total, model stages,
device, and model identifiers. It is collapsed by default. Use `판정 점수`,
not `정확도`, for model scores.

The fixed bottom action remains `다시 촬영`; it is outside the scroll area.

## Components

- `ResultSummaryHeader`: outcome/state title, three counts, latency/device.
- `ConfirmedCountTable`: confirmed SKU quantities only.
- `ReviewQueue`: compact unresolved rows and selection ownership.
- `ReviewCandidateTable`: selected Unknown's three aligned candidates.
- `ConfirmedObjectDisclosure`: optional evaluator evidence.
- `PerformanceDisclosure`: timing and model details.
- `ResultEmptyState`: stable, factual no-detection or no-review row.

Each component consumes immutable values and emits only object selection. The
panel does not derive or modify inference decisions.

## Visual rules

- White panel, one-pixel neutral dividers, no nested gray cards.
- Use BIXOLON Orange only for the primary action and selected keyline.
- Confirmed uses a small teal status mark; review-needed uses a small amber
  status mark. Badges never carry the entire row background.
- Sentence case Korean labels; no uppercase decorative `SCAN RESULT` heading.
- Tabular figures and right alignment for counts, scores, and time.
- One vertical scrollbar for panel content; disclosures expand within it.
- Preserve 44 px interactive targets and visible keyboard focus.

## States and errors

- Initial: `촬영 후 결과가 여기에 표시됩니다.` with no illustration.
- Loading: current phase and elapsed time in the stable header footprint.
- Empty detection: `감지된 빵이 없습니다.` and fixed `다시 촬영` action.
- Camera/model failure: one concise error summary; technical error text under
  a disclosure, not mixed into the main result hierarchy.

## Verification

- Widget tests for no duplicate confirmed objects in the default pane.
- Exactly one expanded Unknown candidate table at a time and exactly Top-3.
- Summary count invariant: confirmed plus review-needed equals detected.
- Confirmed quantity table excludes Unknown.
- Row/overlay selection remains bidirectional.
- No overflow at 1280x820 and 1024x720; one panel scroll area and fixed action.
- Existing camera, worker, timing, Unknown, and inference contract tests pass.
