# 1.1.0 Self-checkout and Admin Console Design

## Responsibility and acceptance

**Responsibility:** turn the Windows camera evaluator into a local self-checkout
prototype that guides a bakery customer from tray placement through a simulated
payment, while giving an administrator an auditable view of the original
inference, customer resolutions, final order, system health, catalog, and
operational settings.

**Acceptance:** a customer can complete every supported happy and recovery path
without staff assistance; the app shows payment completion only after durable
local persistence; the administrator can reconstruct every scan attempt and
compare immutable AI output with customer and administrator decisions; and no
customer or administrator action rewrites the canonical inference receipt.

## Scope

Version 1.1.0 is a full product-mode redesign of the existing Windows Flutter
prototype. It remains one executable on one PC, with two clearly separated
modes:

1. **Customer mode** is the default and supports scan, recovery, product
   resolution, order review, simulated payment, completion, and reset.
2. **Admin mode** supports operational overview, transaction audit, exception
   review, product catalog management, system diagnostics, and settings.

The current prototype user acts as both customer and administrator. Version
1.1.0 does not require an account, PIN, remote server, or multi-kiosk
aggregation. The mode boundary must nevertheless allow a future authentication
gate or remote administrator client without coupling those concerns to checkout
or inference.

Actual payment-provider or POS integration is out of scope. The app creates a
simulated payment receipt, displays completion, and returns to the next customer
screen.

## Product principles

The customer and administrator experience applies the following Toss product
principles without copying Toss branding or restricted design-system assets:

- **One thing per one page:** each screen has one primary user goal.
- **Clear call to action:** each customer screen has one emphasized action.
- **Easy to answer:** customer questions can be answered in about three seconds.
- **Less policy:** model policy and retry rules are not taught to customers.
- **Minimum features:** technical evidence stays out of the customer path.
- **Explain why:** recovery copy briefly connects the problem to the requested
  action.
- **Context based:** the next screen preserves the context of the selected
  bread, remaining work, and current order.
- **Low-cost action:** candidate selection applies immediately and advances
  without an extra save step.
- **No more loading:** the prototype does not introduce fake payment delays.
- **Respect:** copy describes the situation rather than blaming the customer.

The BIXOLON brand, colors, and visual language remain authoritative. Toss
Design System components and brand styling are not copied.

References:

- https://toss.tech/article/mydoc
- https://toss.tech/article/design-motivation
- https://toss.tech/article/21022
- https://toss.im/tossfeed/article/usercentric
- https://developers-apps-in-toss.toss.im/design/components.html
- https://toss.im/tossfeed/article/graphicdesign-team-interview
- https://toss.tech/article/44097
- https://toss.tech/article/44291
- https://toss.tech/article/insurance-claim-process
- https://toss.im/tossface

## Visual design system and generated assets

Version 1.1.0 treats typography, components, and graphics as one product system.
Graphics must make the current question easier to answer or mark a meaningful
transition. They are not decorative filler, inference evidence, or substitutes
for real product photography.

### Flutter foundation

The visual implementation uses:

- Flutter Material 3 as the component and accessibility foundation;
- a BIXOLON `ColorScheme` rather than an off-the-shelf palette;
- a project-owned `ThemeExtension` for status, spacing, radius, camera, and
  checkout-specific tokens;
- small project-owned customer and admin component families;
- Widgetbook or an equivalent isolated component gallery for difficult states;
- Flutter widget, golden, and accessibility-guideline tests; and
- SVG or code-native drawing for precise icons, arrows, boxes, and diagrams.

Version 1.1.0 does not replace the existing Material application with
`fluent_ui`, a Shadcn-style kit, or another complete UI framework. It also does
not require FlexColorScheme unless the built-in Material 3 theming proves
insufficient during implementation.

Project-owned components include:

```text
CustomerScaffold
PrimaryCheckoutButton
CustomerMessage
BreadCandidateCard
BreadSelectionProgress
OrderLineTile
OrderTotal

AdminScaffold
AdminNavigation
AdminMetric
TransactionTable
InferenceComparison
DiagnosticStatus
SettingsField
```

The shared scaffold and action components enforce one emphasized customer CTA,
stable title and supporting-copy placement, keyboard focus, minimum target
size, fixed action placement, and supported-window behavior.

### Typography

All application interface text uses locally bundled Pretendard. The BIXOLON
logo and official brand artwork remain unchanged.

The app bundles only the required static faces:

| Asset | Weight | Use |
| --- | ---: | --- |
| `Pretendard-Regular.ttf` | 400 | Body and secondary text |
| `Pretendard-Medium.ttf` | 500 | Product names and compact emphasis |
| `Pretendard-SemiBold.ttf` | 600 | Buttons and table headings |
| `Pretendard-Bold.ttf` | 700 | Customer titles, totals, and completion |

The initial type scale is:

| Role | Size | Weight |
| --- | ---: | ---: |
| Customer title | 28–32 px | 700 |
| Customer total | 24–28 px | 700 |
| Customer body and product | 16–18 px | 400–500 |
| Customer primary action | 17–18 px | 600 |
| Customer supporting copy | 14–15 px | 400 |
| Admin table body | 14–16 px | 400–500 |
| Admin table heading | 13–14 px | 600 |

Exact sizes are resolved against the supported Windows dimensions and text
scaling during visual QA. The implementation must not download fonts at
runtime. It pins the approved Pretendard release, records each bundled file's
size and SHA-256, and includes the SIL Open Font License notice with the
installer or third-party notices.

### Generated-asset gate

Before producing or accepting a generated bitmap, the asset owner must answer
yes to all of these questions:

1. Does the graphic make the customer's next action or transition easier to
   understand?
2. Does it help the customer answer the screen's question in about three
   seconds?
3. Does it strengthen the page's one primary goal?
4. Is it clearly distinct from a real product photo and inference evidence?
5. Can it follow the shared visual system rather than becoming a one-off style?

An asset that fails any gate is omitted. Essential information remains in
Flutter text, real imagery, and deterministic overlays, so generated assets may
fail to load without blocking checkout.

### Generated-asset scope

Version 1.1.0 has exactly two required generated illustrations:

| Asset ID | Screen | Job |
| --- | --- | --- |
| `manual-cart-entry` | Repeated-retake fallback | Show that checkout can continue through direct product selection |
| `payment-complete` | Completed payment | Mark a trustworthy end to the transaction with no further action required |

An admin review-empty state may reuse the same `payment-complete` asset at a
smaller presentation size or use a code-native check icon. It is not a third
generated asset.

The following screens deliberately use no generated bitmap:

- ready: live camera and deterministic tray guide;
- retake: real capture, canonical problem region, and SVG or code overlays;
- customer review: real selected object and real product photography;
- catalog: real sale-product photography;
- order review: real order content;
- dashboard and diagnostics: measured data and code-native status;
- transaction detail: real capture and immutable inference evidence.

### Graphic direction

The generated illustration family is `BIXOLON bakery receipt`:

- simple bread silhouettes built from readable base shapes;
- top-down tray composition;
- black and neutral-gray line work;
- one BIXOLON Orange registration or completion accent;
- restrained thermal-receipt precision without dense hatching;
- an adult, ordered, and trustworthy tone rather than a childlike mascot;
- one consistent view direction, visual scale, line density, and palette;
- transparent background;
- no embedded words, prices, labels, or logos; and
- no confetti, coins, exaggerated rewards, or unrelated decoration.

The signature visual is a receipt-like line that connects the tray to direct
selection or resolves into one orange completion check. This is the one
expressive device; surrounding UI remains quiet.

### Asset-specific briefs

`manual-cart-entry` shows a simplified top-down tray and a small product-list
shape connected by the orange receipt line. It communicates an alternate path,
not an error. The Flutter screen asks `제품을 직접 담을까요?`, emphasizes
`직접 담기`, and retains `다시 확인하기` as the secondary action.

`payment-complete` shows a tray with bread and a short receipt whose line ends
as the orange check. It appears with the Flutter text `결제가 끝났어요` and
`이용해 주셔서 감사합니다`. It includes no fake payment-network, currency,
reward, or celebration imagery.

### Prohibited generated content

Generated assets must not be used as:

- sale-product or Top-3 candidate photography;
- model training, calibration, prototype-bank, support-bank, or evaluation
  data;
- source camera frames or transaction evidence;
- detection, count, location, or box explanations;
- BIXOLON logo generation or modification;
- customer-specific imagery;
- baked UI copy, product name, price, or score; or
- administrator evidence or model-health proof.

If a sale product lacks a real photo, the catalog uses a neutral code-native
`사진 준비 중` placeholder rather than a generated product image.

### Production and provenance

Asset production proceeds as:

1. generate three visual-direction variants using `payment-complete`;
2. place each variant in the real supported completion layout;
3. select one direction based on comprehension, visual hierarchy, and brand
   fit;
4. generate `manual-cart-entry` from the approved direction;
5. remove the flat generation background and validate alpha edges;
6. validate both assets at 1280×820, 1024×720, high Windows display scaling,
   and missing-asset fallback;
7. retain only approved final assets in the application; and
8. record prompt and file provenance.

Project-bound final assets live under:

```text
apps/bakery_camera_flutter/assets/illustrations/v1_1_0/
├── manual-cart-entry.png
├── payment-complete.png
└── manifest.json
```

The generated-asset manifest records asset ID, path, screen, purpose, prompt,
generation date, generator path where exposed, byte size, SHA-256, alpha
validation, review state, and the explicit `not_product_or_inference_evidence`
classification.

## System boundaries

```text
One Windows executable
├── Customer checkout
├── Admin console
└── Shared application services
    ├── Checkout session coordinator
    ├── Canonical inference gateway
    ├── Product catalog and price snapshots
    ├── Audit and persistence store
    ├── Simulated payment service
    ├── Operational settings
    └── Read-only model diagnostics
```

The canonical CPU pipeline remains:

```text
EXIF-transposed RGB
-> RF-DETR-L
-> RepViT-M1 direct gate
-> conditional DINOv3 global and local evidence
-> immutable fusion policy
-> registered SKU or Unknown
```

Version 1.1.0 adds checkout, customer resolution, audit, catalog, and
presentation responsibilities around this pipeline. It does not reinterpret
scores, hard-code alternate thresholds, or promote an `Unknown` inference into
an automatic registered SKU.

### Two count domains

The app must keep inference counts and transaction counts separate:

- `InferenceReceipt` counts only automatically registered inference objects.
  It retains `Unknown` separately under the canonical fail-closed contract.
- `FinalOrder` counts the products the customer will purchase. It may contain
  products selected by the customer from Top-3, the full catalog, or the manual
  cart, but every such line retains its non-AI resolution source.

Customer selection never makes the historical inference correct or automatic.

### Product and recognition identity

The sales catalog and recognition model use related but distinct identities:

- `product_id` is the immutable sales-catalog identity used by orders, prices,
  and product management.
- `recognition_sku_id` is the optional registered identity understood by the
  active recognition model and its immutable policy.

Every registered recognition SKU maps to one active or historically retained
catalog product in a catalog revision. A catalog-only product has
`recognition_sku_id: null`; customers can buy it through catalog or manual-cart
selection, but the app never claims that the model can recognize it. Top-3
candidates contain registered recognition SKUs and resolve through the
session's catalog revision.

Object-linked customer resolutions retain the canonical inference box and
object ID. A manual-cart line has no inferred object or location; it records
`source_object_id: null` and `location_source: manual_entry` rather than
inventing a box or confidence.

## Customer experience

### Customer-facing decision states

Analysis produces exactly three customer-facing decision states:

| State | Condition | Customer outcome |
| --- | --- | --- |
| `retakeRequired` | Count, location, image, detection, separation, or candidate evidence is not safe enough to use | Suppress product, price, quantity, and total output; request one concrete rearrangement |
| `customerReview` | Object count and location are usable, but at least one product identity is unresolved | Resolve one bread at a time with three likely products or the full catalog |
| `orderReview` | Every bread has an automatic or explicit customer resolution | Review the complete itemized order and start simulated payment |

Analyzing, payment persistence, and payment completion are transient workflow
states, not additional result states.

### State flow

```text
ready
-> analyzing
-> retakeRequired | customerReview | orderReview

retakeRequired
-> analyzing on rescan
-> customerReview/manual-cart mode after the configured retry limit

customerReview
-> customerReview while unresolved bread remains
-> orderReview when all bread is resolved

orderReview
-> customerReview when the customer edits a product
-> retakeRequired when tray and order count do not agree
-> paymentCommitting when the customer pays

paymentCommitting
-> completed only after durable commit
-> ready after the completion message
```

### 1. Ready

The screen asks the customer to place bread and start:

- Title: `빵을 트레이에 올려주세요`
- Supporting copy: `빵끼리 조금 떨어뜨려 놓으면 더 정확하게 확인할 수 있어요.`
- Primary action: `빵 확인하기`

The screen shows the live camera and tray placement guide. It does not show
object counts, confidence, model state, device, timing, or prior transaction
information.

Admin entry is available in the header for the prototype. Entering admin mode
with an active customer session requires an explicit session-cancel
confirmation. Production can later hide or authenticate this entry without
changing the admin module.

### 2. Analyzing

The app freezes the captured frame and prevents duplicate submission:

- Primary copy: `빵을 확인하고 있어요`
- No model names, phases, or confidence values
- Canceling records the session as `abandoned`

Camera, worker, storage, and catalog failures route to actionable error states,
not to an inferred product.

### 3. Retake required

This state is blocking. It publishes no usable product, price, quantity, or
total.

Supported instructions include:

- `빵 사이를 조금 벌려주세요`
- `빵이 모두 보이도록 안쪽으로 옮겨주세요`
- `빵이 잘 보이도록 다시 놓아주세요`

Supporting copy explains one reason, such as:

`빵 2개가 겹쳐 있어 제품을 구분하기 어려워요.`

The image highlights only the actionable area. The primary action is
`다시 확인하기`.

After the configured number of unsuccessful attempts, a secondary
`직접 담기` action becomes available. It enters the `customerReview` workflow
in manual-cart mode. The retry limit is an operational setting and is not
explained as model policy to the customer.

### 4. Customer review

The screen resolves one object at a time:

- Title: `이 빵이 맞나요?`
- Compact progress: `2개 중 첫 번째 빵`
- Selected bread image or highlighted camera box
- Three product-photo choices with name and price
- Secondary action: `여기에 없어요`

Customer-facing copy never uses `Unknown`, Top-1, Top-2, Top-3, RepViT,
DINOv3, fusion, or confidence percentages.

Selecting a proposed product records `customer_top3` and advances to the next
unresolved object without another save or next button. `여기에 없어요` opens
the full catalog and records `customer_catalog` after selection.

The full-catalog discovery order is:

1. frequently purchased products;
2. photo-based categories;
3. product-name search; and
4. the complete active catalog.

Manual-cart mode uses the same catalog but lets the customer add products and
quantities without inference-object links. It records
`customer_manual_cart`. Its entry screen may show the approved
`manual-cart-entry` illustration, but the question and actions remain fully
usable when that asset is absent.

### 5. Order review

The screen has one goal: verify the complete order.

- Title: `담은 빵을 확인해 주세요`
- Headline: `빵 7개 · 총 12,500원`
- Product photo, name, quantity, unit price, and line total
- Secondary action: `주문 수정하기`
- Primary action: `7개 · 12,500원 결제하기`

The count and amount in the primary action serve as the final easy-to-answer
confirmation. The app does not add a redundant confirmation modal.

Every automatic line remains editable. Replacing an automatically registered
SKU records `customer_overrode_auto`; leaving it unchanged and completing
payment records `ai_auto_customer_accepted`.

If the customer says the physical tray count and order count differ, an
inference-backed order returns to retake rather than allowing an unexplained
object deletion. A manual-cart order allows direct quantity editing.

### 6. Simulated payment and reset

The app does not display a fake payment spinner. If persistence takes long
enough to require feedback, it shows `주문을 마무리하고 있어요`.

The completion sequence is:

1. freeze the final order;
2. create the simulated payment receipt;
3. persist order, payment, session, images, and receipt references;
4. validate the committed references and hashes;
5. display `결제가 끝났어요` and `이용해 주셔서 감사합니다`;
6. create a new session and return to the ready screen.

The app must not display payment completion after a persistence failure.
The completion screen uses the approved `payment-complete` illustration as
secondary confirmation only; durable state and text remain authoritative.

## Admin information architecture

The admin console has six task-oriented destinations.

### 1. Dashboard

The dashboard answers: `지금 확인해야 할 문제가 있는가?`

It shows:

- completed transactions today;
- transactions with customer resolution;
- automatic decisions overridden by customers;
- transactions with retakes;
- manual-cart transactions;
- unresolved system failures; and
- a prioritized review queue.

Review priority is:

1. `customer_overrode_auto`;
2. `customer_catalog`;
3. repeated retake;
4. abandoned after inference;
5. camera, model, catalog, or persistence error.

The dashboard must not label non-correction as model accuracy. It may show
confirmed error counts only for administrator-reviewed evidence.

### 2. Transaction history

The history page finds a specific session. Its stable columns are:

- time;
- terminal state;
- bread count;
- final amount;
- scan-attempt count; and
- customer-resolution summary.

Supported filters are date, terminal state, automatic-only, Top-3 selection,
catalog selection, automatic override, retake, and model or policy version.
Search covers session ID and product name.

### Transaction detail subview

The detail page explains one transaction:

- chronological scan-attempt timeline;
- every retained source image;
- canonical boxes and selected object;
- original AI SKU or `Unknown`;
- ranked candidates and model evidence;
- customer selection and selection source;
- final paid product;
- final order and simulated payment receipt;
- model, policy, preprocessing, catalog, and setting revisions; and
- administrator reviews.

Model values are labeled as model decision evidence, not measured accuracy.

### 3. Review inbox

The inbox reviews one session or object at a time. A reviewer selects:

- `AI 판정이 맞아요`
- `고객 선택이 맞아요`
- `둘 다 아니에요`
- `사진만으로 판단하기 어려워요`

Optional issue tags are:

- product misclassification;
- miss;
- duplicate;
- merge;
- split;
- non-target detection;
- image quality; and
- catalog issue.

When required, the reviewer selects the correct catalog product and, when
applicable, its registered recognition SKU. The reviewer may also add a note.
The primary action is `검토 완료`.

An `AdminReview` is append-only. It does not mutate `InferenceReceipt`,
`CustomerResolution`, or a completed `FinalOrder`. Version 1.1.0 does not
automatically promote reviewed scans into training, calibration, or acceptance
data.

### 4. Product management

The product page manages:

- immutable sales `product_id`;
- optional registered `recognition_sku_id`;
- customer-facing name;
- product photo;
- price;
- category;
- active or inactive sale state; and
- last modification time.

A product ID used by a transaction is never deleted or reused. Product
retirement sets it inactive. A recognition SKU cannot be silently rebound to a
different product inside the same catalog revision. Historical order lines
retain checkout-time name and price snapshots.

A catalog product can be sold by customer selection before it is validated for
automatic recognition. The UI distinguishes:

- sale available;
- customer selection available; and
- automatic recognition validation state.

Adding a catalog product does not alter model artifacts.

### 5. System diagnostics

Diagnostics answer whether the local system is ready:

- camera;
- inference worker;
- persistence write test;
- active catalog;
- artifact integrity;
- recent failures;
- active pipeline composition;
- artifact IDs and SHA-256 values;
- detector threshold source;
- CPU or GPU device;
- load and warm-up receipt;
- recent per-stage timings; and
- conditional-DINO execution rate.

The primary action is `시스템 다시 확인하기`.

Recent operational timings are not labeled as formal performance evidence.
Detector thresholds, fusion margins, and calibrated model policies are
read-only. A future model-bundle replacement must require no active session,
complete SHA-256 verification, and worker restart.

### 6. Settings

Mutable operational settings are:

- camera device and resolution;
- unsuccessful-retake limit before manual cart;
- completion-screen duration;
- image retention period;
- whether to retain interrupted-session images;
- default customer-mode startup;
- prototype admin-entry visibility; and
- storage location and capacity warning.

Settings state whether they apply immediately or from the next customer.
Session-affecting settings apply only from the next session.

Returning to customer mode creates a new customer session but preserves the
last admin page and filter state.

## Persistent audit model

### Storage layout

Structured records use a local embedded database. Images and immutable JSON
receipts use the Windows application-data directory, not the Git repository.

```text
BixolonBakeryScanner/
├── scanner.db
└── sessions/
    └── YYYY/MM/DD/{session_id}/
        ├── attempt-001.jpg
        ├── attempt-001.inference.json
        ├── attempt-002.jpg
        ├── attempt-002.inference.json
        └── final-order.json
```

Every stored file records its byte size and SHA-256.

### CheckoutSession

One customer visit owns:

- session ID;
- state;
- start and terminal timestamps;
- catalog revision;
- settings revision;
- model and policy provenance;
- ordered scan attempts;
- object resolutions;
- final order;
- simulated payment; and
- zero or more administrator reviews.

### ScanAttempt

Every capture records:

- attempt number and capture time;
- image path, size, and SHA-256;
- canonical width and height;
- canonical objects and boxes;
- registered SKU or `Unknown`;
- candidate evidence;
- confidence and decision path;
- presentation state and retake reason;
- model, policy, calibration, and preprocessing provenance;
- per-stage timing; and
- immutable inference-receipt SHA-256.

A new capture appends an attempt. It never replaces a previous attempt.

### ObjectResolution

Resolution sources are:

| Source | Meaning |
| --- | --- |
| `ai_auto_customer_accepted` | The customer paid without changing an automatic result |
| `customer_top3` | The customer selected one of three authorized candidates |
| `customer_catalog` | The customer selected from the full catalog |
| `customer_overrode_auto` | The customer replaced an automatically accepted SKU |
| `customer_manual_cart` | The customer constructed a cart after repeated scan failure |

Each resolution records source object where applicable, original AI result,
selected catalog product, optional recognition SKU, timestamp, and relevant
candidate rank. Object-linked resolutions retain the canonical box. Manual-cart
resolutions explicitly have no inferred box or model confidence.

### FinalOrder and SimulatedPayment

A final order stores checkout-time product ID, optional recognition SKU,
product name, unit price, quantity, line amount, total quantity, total amount,
and resolution source.

The simulated payment stores a unique receipt ID, final-order hash, amount,
completion time, and `simulated` provider identity.

### Session terminal states

- `completed`: durable order and simulated payment commit succeeded;
- `abandoned`: the user intentionally restarted before payment;
- `interrupted`: the process exited with a nonterminal session; and
- `failed`: the session could not continue because of a system failure.

Only `completed` sessions contribute to sales and purchased-product totals.

## Transaction and consistency rules

At session start, the app snapshots:

- catalog revision;
- operational settings revision; and
- active model, calibration, preprocessing, and policy provenance.

Catalog or settings changes during a session apply to the next session. The
active model bundle cannot change during a session.

Before invoking inference, the app stages the captured image, calculates its
SHA-256, and creates the scan-attempt record. If this write fails, inference
does not run and the checkout cannot continue without audit evidence. After
strict worker-result validation, the immutable inference receipt is written and
linked to the attempt before customer resolution begins.

Payment completion uses one durable commit boundary:

1. freeze the final order;
2. write final order and simulated payment receipt;
3. update database rows and file references in a transaction;
4. verify expected references and hashes;
5. commit;
6. only then display completion.

## Retention

Image retention is configurable. When a retained image expires:

- delete the image file;
- keep transaction, inference, customer-resolution, and review records;
- keep original byte size and SHA-256;
- record `pruned_at`; and
- show a deliberate retention-expired state in admin detail.

Retention runs only while the customer flow is idle or the app is in admin
mode. It does not race with capture, inference, or payment persistence.

## Crash recovery

At startup, any nonterminal session from a previous process becomes
`interrupted`. Its already-persisted images and receipts remain available to
admin review. It is never treated as paid and is not automatically resumed.
Customer mode starts with a fresh session.

## Failure presentation

| Boundary | Customer copy | Admin evidence |
| --- | --- | --- |
| Camera unavailable | `카메라를 확인할 수 없어요` | Device identity and raw camera error |
| Model unavailable | `지금은 빵을 확인할 수 없어요` | Failed phase and artifact verification |
| Image persistence unavailable | `주문을 시작할 수 없어요` | Path, capacity, and write failure |
| Inference failure | `빵을 확인하지 못했어요` | Request ID, stage, and worker error |
| Payment commit failure | Never show completion | Database and file-commit state |
| Catalog unavailable | `판매 제품을 준비하지 못했어요` | Catalog revision and validation error |

Customer screens show one recovery action. Admin detail retains technical
diagnostics. Unexpected programming or invalid-schema errors do not become an
arbitrary SKU.

## Metrics

The admin dashboard may calculate:

- completed sessions;
- purchased product quantity and simulated sales amount;
- automatic results accepted without edit;
- Top-3 selections;
- full-catalog selections;
- automatic-result overrides;
- manual-cart selections;
- retake sessions and attempts;
- interrupted and failed sessions;
- measured operational timings; and
- administrator-reviewed issue counts.

It must not calculate live model accuracy by treating lack of correction as
ground truth. Administrator-reviewed evidence and locked evaluation receipts
remain separately labeled sources.

## Validation

### Customer flow

- automatic-only checkout reaches order review and completion;
- authorized candidate selection records `customer_top3`;
- full-catalog selection records `customer_catalog`;
- automatic-result editing records `customer_overrode_auto`;
- retake preserves the previous scan attempt;
- configured repeated failure enables manual cart;
- payment completion appears only after persistence;
- completion resets to a clean ready screen; and
- customer screens expose no model names, `Unknown`, confidence, device, or
  stage timing.

### Inference and audit integrity

- customer choice never mutates the inference receipt;
- administrator review never mutates inference, customer resolution, or paid
  order;
- inference counts continue to exclude `Unknown`;
- final-order lines retain an explicit resolution source;
- canonical boxes and object IDs remain stable within an attempt;
- image and receipt hashes are verified;
- registered recognition SKUs map through the frozen catalog revision;
- catalog-only products never appear as automatic recognition results;
- artifact and policy provenance is complete; and
- invalid or missing evidence fails closed.

### Transaction integrity

- completed orders are immutable;
- catalog price changes do not alter historical orders;
- nonterminal sessions never contribute to purchased totals;
- a failed payment commit cannot display completion;
- startup marks stale nonterminal sessions interrupted;
- image retention preserves hashes and a pruning record; and
- settings and catalog revisions remain stable for the active session.

### Admin behavior

- dashboard prioritizes actionable exception types;
- transaction filters find each resolution and failure path;
- transaction detail reconstructs every scan attempt;
- review choices append one `AdminReview`;
- product IDs cannot be deleted or reused after transaction use;
- model and calibrated policy values are read-only; and
- no dashboard metric presents unreviewed behavior as model accuracy.

### UI and accessibility

- each customer screen has one emphasized primary action;
- all customer questions are short, concrete, and action-oriented;
- Material 3, the BIXOLON theme extension, and project-owned components render
  each required customer and admin state in isolation;
- Pretendard 400, 500, 600, and 700 render without runtime network access and
  retain legibility at supported Windows text scaling;
- bundled font version, license notice, size, and SHA-256 are present;
- exactly `manual-cart-entry` and `payment-complete` are required generated
  illustrations;
- the generated-asset manifest contains every required provenance field;
- generated assets contain no text, logo, price, score, or product claim;
- real product, candidate, camera, and administrator-evidence surfaces contain
  no generated substitute;
- missing generated assets do not remove instructions or actions;
- alpha edges and one-illustration-per-screen limits pass visual review;
- customer and admin state cannot leak into one another;
- keyboard and touch input are supported;
- layouts do not overflow at 1280×820 or 1024×720; and
- BIXOLON visual identity remains distinct from Toss branding.

### Regression boundaries

- canonical RF-DETR-L, RepViT, conditional DINOv3, fusion, and `Unknown`
  contract tests continue to pass;
- existing camera and worker protocol failures remain strict;
- `portable_cpu_smoke/` and legacy behavior are unchanged; and
- skipped artifact, integration, package, or performance suites are reported
  as unverified rather than passed.

## Out of scope for 1.1.0

- real card, PG, or POS payment integration;
- remote or multi-kiosk administrator service;
- user accounts, administrator PIN, or role management;
- automatic training, calibration, or policy updates from live scans;
- live threshold editing;
- cloud backup or synchronization;
- AI-generated sale-product or candidate photography;
- generated images in model training, calibration, prototype or support banks,
  or evaluation evidence;
- more than the two required customer illustrations without a separately
  approved design change;
- formal accuracy claims from customer behavior; and
- deletion or migration of legacy pipeline assets.
