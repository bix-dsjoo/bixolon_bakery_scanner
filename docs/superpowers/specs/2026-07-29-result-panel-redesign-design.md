# Bakery inference evaluation panel redesign

## Purpose

Redesign the right pane for a person who is evaluating model inference for
the first time. The evaluator must be able to verify:

1. whether every bread location and final label look correct;
2. whether every `알 수 없음` result exposes an appropriate Top-3;
3. which classifier path produced each final decision; and
4. whether press-to-render and model inference latency are acceptable.

The redesign changes presentation and selection behavior only. Camera
capture, model execution, policy, boxes, scores, timing measurements, and
result contracts remain unchanged.

## Research basis

- LandingLens exposes prediction overlays, supports instance-level inspection,
  and sorts low-confidence instances first for troubleshooting.
- Roboflow separates visual output from raw/technical output.
- AWS Rekognition presents label and confidence as aligned result data and
  reveals additional results on demand.
- Supabase tables use stable columns, right-aligned numeric values, one scroll
  region, restrained badges, and structurally stable empty states.
- Production vision checkout products prioritize an itemized result, while
  hiding model internals until an exception or inspection requires them.

References:

- https://landinglens.docs.landing.ai/view-predictions
- https://docs.roboflow.com/workflows/test-a-workflow
- https://docs.aws.amazon.com/rekognition/latest/dg/detect-labels-console.html
- https://supabase.com/design-system/docs/components/table
- https://supabase.com/design-system/docs/components/badge
- https://supabase.com/design-system/docs/ui-patterns/layout
- https://www.imupos.com/en/sw/ai/bakery-scanner/
- https://www.mashgin.com/solution/overview

## Current problems

- The overlay label, product-count list, and per-object list repeat confirmed
  information three times.
- `Unknown` appears as if it were a product quantity and is then repeated with
  three candidates for every unresolved object.
- Total count, latency, and device have equal headline weight while unresolved
  objects are the primary evaluation concern.
- Confidence is visually presented like measured accuracy.
- Decision-path descriptions and model details repeat in the default flow.
- Nested gray cards and simultaneously expanded candidate lists make scanning
  difficult in a narrow pane.

## Stable panel regions

### 1. Evaluation summary

The header uses factual labels rather than one mixed sentence:

- `대상 9`
- `확정 4`
- `알 수 없음 5`
- `화면 표시까지 726 ms`
- `모델 추론 412 ms`
- `GPU` or `CPU`

`화면 표시까지` is press-to-render. `모델 추론` is worker total. They must
never share one unlabeled duration. During initialization and analysis, the
same footprint shows a plain Korean phase and elapsed time without layout
shift.

### 2. Object evaluation list

Show every detected object in one dense list because the evaluator needs to
verify both confirmed and unresolved outputs. Each row has four aligned
fields:

- image-linked display number;
- final product name or `알 수 없음`;
- decision path (`RepViT`, `DINOv3`, `Fusion`, or `알 수 없음`);
- right-aligned decision score.

Unresolved objects appear first. Within that group, lower leading-candidate
score appears first. Confirmed objects retain canonical object order. UI order
does not mutate the immutable inference result.

The default list does not repeat explanatory sentences. A row is at least
44 px high and exposes visible hover, keyboard focus, and selected states.

### 3. Selected unresolved detail

On first result display, select the first unresolved object when one exists.
Otherwise select the first confirmed object. Selection synchronizes with the
image overlay.

Only one unresolved row can expand. It displays:

`AI가 이 빵의 품목을 알 수 없다고 판단했어요. 가능성이 높은 품목 3개를
참고용으로 보여드려요.`

The read-only detail table has aligned columns:

- `순위`
- `예상 품목`
- `판정 점수`

It always shows exactly three candidates. Candidates must not look clickable
or corrective. `후보` is not used as the unresolved state name; the state is
always `알 수 없음`.

### 4. Secondary disclosures

- `품목별 수량`: confirmed SKU quantities only; `알 수 없음` is excluded.
- `단계별 시간`: capture, preprocessing, Detector, RepViT, DINOv3, and
  postprocessing. A zero DINOv3 duration is rendered as `실행 안 함`.
- `모델 정보`: model identifiers, policy, load, and warm-up evidence.

The score explanation appears once in technical information:

`판정 점수는 모델이 품목을 선택한 상대 점수이며 실제 정확도를 의미하지
않습니다.`

Technical terms get plain-language pairings:

- `빵 위치 찾기 · Detector`
- `1차 품목 분류 · RepViT`
- `재확인 · DINOv3`

The fixed `다시 촬영` action stays outside the single content scroll region.

## Image overlay

- Always show a thin box and a compact display number.
- Confirmed boxes use teal; unresolved boxes use amber.
- Only the selected box uses a thick outline and visible name or `알 수 없음`.
- Display numbers match evaluation-list numbers.
- Selecting an overlay selects and reveals its list row; selecting a list row
  highlights its overlay.
- Large filled labels are removed so labels do not obscure neighboring bread.

## First-use copy

- Initial: `트레이를 카메라 아래에 놓고 분석하기를 눌러주세요.`
- Detecting: `빵을 찾고 있어요.`
- Classifying: `빵 종류를 확인하고 있어요.`
- Rechecking: `분류 결과를 다시 확인하고 있어요.`
- Aggregating: `결과를 정리하고 있어요.`
- No detection: `빵을 찾지 못했어요. 트레이 위치를 확인하고 다시 촬영해
  주세요.`
- Camera failure: `카메라를 찾지 못했어요. 연결을 확인한 후 다시 연결해
  주세요.`
- Model failure: `모델을 준비하지 못했어요. 앱을 다시 시작해 주세요.`

Failures show one actionable summary. Raw worker errors stay in technical
details and do not replace the primary instruction.

## Visual rules

- One white result surface with one-pixel neutral separators; no nested gray
  cards and no decorative `SCAN RESULT` heading.
- BIXOLON Orange remains limited to primary action and selected keyline.
- Teal and amber are small semantic marks, never full-row backgrounds.
- Tabular figures and right alignment for counts, scores, and timing.
- The result pane has a minimum practical width of 360 px; use approximately
  64/36 image/result allocation while preserving supported window sizes.
- One vertical scrollbar for result content and a fixed bottom action.

## Component boundaries

- `EvaluationSummary`: state, counts, two labeled durations, device.
- `EvaluationObjectList`: ordering, selection, focus, and compact rows.
- `CandidateEvidenceTable`: exactly three read-only candidate rows.
- `QuantityDisclosure`: confirmed quantities only.
- `StageTimingDisclosure`: plain-language stage labels and durations.
- `ModelInfoDisclosure`: identifiers, load/warm-up, score explanation.
- `EvaluationOverlayPainter`: numbered boxes and selected-name treatment.

Components consume immutable view data and emit object selection only. A
dedicated presentation adapter may derive display order, display numbers, and
plain-language labels, but it must not change inference decisions or scores.

## Verification

- Summary invariant: confirmed plus unresolved equals detected.
- Every object appears exactly once in the default evaluation list.
- Unresolved objects are ordered first; exactly one selected detail expands.
- Selected unresolved detail always contains ranks 1, 2, and 3 exactly once.
- Quantity disclosure excludes unresolved objects.
- Default content does not repeat confirmed rows as a second visible section.
- Press-to-render and worker total have distinct labels and values.
- Zero DINOv3 time displays `실행 안 함`.
- Overlay numbers match list numbers and selection works in both directions.
- No overflow at 1280x820 or 1024x720; one content scroll and fixed action.
- Existing camera, worker, timing, Unknown, and inference-contract tests pass.
