# CPU RF-DETR 최종 문서화 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** CPU RF-DETR-L + fail-closed fusion을 프로젝트의 유일한 최종 경로로 문서화하고 기존 D-FINE 경로를 레거시로 명확히 분리한다.

**Architecture:** `AGENTS.md`는 운영 규범과 최종 런타임 계약을, `README.md`는 사용자 진입점과 배포 방법을 맡는다. 최신 CPU 문서군은 상호 연결하며, D-FINE 문서와 런타임은 파일을 이동하지 않고 역사적/레거시로 표기한다.

**Tech Stack:** Markdown, PowerShell, Git, pytest.

## Global Constraints

- 최종 경로는 canonical EXIF-transposed RGB → CPU/FP32 RF-DETR-L → RepViT 직접 gate → 조건부 DINOv3 global/local fusion이다.
- fusion SKU 허용 조건은 local Top-1 일치 또는 세 모델 global Top-1 일치와 margin 0.85 이상뿐이다.
- 다른 모든 분류 결과는 `Unknown`이다.
- 기존 D-FINE, Box Assurance, resolver, GPU 실험, portable CPU smoke 파일은 삭제·이동·기능 변경하지 않는다.
- 모델, calibration, 사용자 작업 파일과 평가 수치를 수정하거나 새로 주장하지 않는다.

---

### Task 1: 최종 운영 계약을 AGENTS에 반영

**Files:**
- Modify: `AGENTS.md`
- Test: `AGENTS.md` 정적 문자열 검증

**Interfaces:**
- Consumes: `models/rfdetr_large_bakery_v1/manifest.json`, `configs/cpu_rfdetr_classifier_policy.yaml`, `src/bakery_scanner/classification/fusion_policy.py`
- Produces: CPU RF-DETR-L을 최종 경로로 규정하고 레거시 경로를 비최종으로 명시한 저장소 지침

- [ ] **Step 1: 오래된 최종 모델 참조를 확인한다**

Run: `rg -n "D-FINE-N|MobileNetV4|ConvNeXt|RTX 5080|0.5초" AGENTS.md`

Expected: 기존 GPU/assurance 최종 경로 참조가 확인된다.

- [ ] **Step 2: AGENTS의 미션·경계·검증 조항을 CPU 최종 계약으로 교체한다**

```markdown
입력 이미지
  → EXIF-transposed RGB canonical frame
  → RF-DETR-L (CPU/FP32, calibrated threshold)
  → RepViT-M1 direct-decision gate
  → conditional DINOv3 global + local evidence
  → immutable fusion consensus
  → SKU or Unknown, aggregate and evaluation report
```

`Unknown` 허용/거절 기준, canonical box, IoU 0.50 일대일 평가, E/M/H 평균 지연, SHA-256 무결성 검증을 명시한다. D-FINE/assurance 항목은 레거시로 한 단락에 보존한다.

- [ ] **Step 3: 정적 검증을 실행한다**

Run: `@('RF-DETR-L','CPU/FP32','fusion','0.85','레거시') | ForEach-Object { if (-not (Select-String -Path AGENTS.md -SimpleMatch $_ -Quiet)) { throw "missing: $_" } }`

Expected: PASS.

- [ ] **Step 4: 변경만 커밋한다**

Run: `git add AGENTS.md; git commit -m "docs: make CPU RF-DETR pipeline canonical"`

Expected: AGENTS 단독 커밋이 생성된다.

### Task 2: README를 최종 CPU 사용 안내로 재구성

**Files:**
- Modify: `README.md`
- Test: `README.md` 링크 및 명령 정적 검증

**Interfaces:**
- Consumes: `portable_rfdetr_cpu/README.md`, `portable_rfdetr_cpu/Run-CPU-Batch2.ps1`, `portable_rfdetr_cpu/Verify-Package.ps1`, `scripts/run_cpu_rfdetr_fusion.py`
- Produces: 최종 CPU 실행·검증·결과 계약과 레거시 D-FINE smoke를 구분한 UTF-8 README

- [ ] **Step 1: README의 최종 경로와 문자 인코딩 문제를 확인한다**

Run: `rg -n "D-FINE|RF-DETR|portable_rfdetr|CPU" README.md`

Expected: D-FINE 중심 또는 깨진 기존 안내가 확인된다.

- [ ] **Step 2: README를 UTF-8 한국어 최종 안내로 교체한다**

README에는 프로젝트 목적, 최종 CPU 파이프라인, fusion의 두 허용 규칙과 `Unknown`, 오프라인 ZIP의 `Verify-Package.ps1` 및 `Run-CPU-Batch2.ps1` 실행, `report.json`의 IoU 0.50/FP/FN/Top-1/Top-3/E/M/H 계약, 레거시 D-FINE CPU smoke의 비최종 고지, 최신 설계 문서 링크를 순서대로 둔다.

- [ ] **Step 3: 필수 사용자 진입점 링크를 확인한다**

Run: `@('portable_rfdetr_cpu/Verify-Package.ps1','portable_rfdetr_cpu/Run-CPU-Batch2.ps1','docs/superpowers/specs/2026-07-29-offline-cpu-rfdetr-fusion-deployment-design.md') | ForEach-Object { if (-not (Select-String -Path README.md -SimpleMatch $_ -Quiet)) { throw "missing: $_" } }`

Expected: PASS.

- [ ] **Step 4: 변경만 커밋한다**

Run: `git add README.md; git commit -m "docs: document final CPU RF-DETR runtime"`

Expected: README 단독 커밋이 생성된다.

### Task 3: 최신 및 레거시 설계 문서를 연결

**Files:**
- Modify: `docs/superpowers/specs/2026-07-29-rfdetr-fusion-consensus-design.md`
- Modify: `docs/superpowers/specs/2026-07-29-rfdetr-desktop-nine-image-evaluation-design.md`
- Modify: `docs/superpowers/specs/2026-07-29-offline-cpu-rfdetr-fusion-deployment-design.md`
- Modify: `docs/superpowers/specs/2026-07-27-final-inference-pipeline-design.md`
- Modify: `docs/superpowers/specs/2026-07-28-production-e2e-pipeline-design.md`
- Test: Markdown 링크 대상 존재 검증

**Interfaces:**
- Consumes: `docs/superpowers/specs/2026-07-29-cpu-rfdetr-final-documentation-design.md`
- Produces: 최신 CPU 문서군 상호 링크와 이전 D-FINE 최종 설계의 역사적 상태 표기

- [ ] **Step 1: 최신·이전 설계의 상태 문구를 확인한다**

Run: `rg -n "Status:|approved|final|D-FINE|RF-DETR" docs/superpowers/specs/2026-07-27-final-inference-pipeline-design.md docs/superpowers/specs/2026-07-28-production-e2e-pipeline-design.md docs/superpowers/specs/2026-07-29-*-design.md`

Expected: 충돌하는 최종 경로 상태를 확인한다.

- [ ] **Step 2: CPU 문서군에 최종 상태와 상호 링크를 추가한다**

세 2026-07-29 RF-DETR 문서의 서두에 최종 채택 CPU 경로 및 서로의 상대 링크를 추가한다. CPU 경로가 D-FINE smoke를 대체하지만 삭제하지 않는다는 범위를 적는다.

- [ ] **Step 3: 이전 최종 설계 문서에 대체 고지를 추가한다**

2026-07-27 및 2026-07-28 생산 설계 문서의 제목 아래에 `2026-07-29 CPU RF-DETR 최종안으로 대체된 역사적 설계`라는 고지와 새 설계 링크를 추가한다. 나머지 본문은 보존한다.

- [ ] **Step 4: 링크 대상을 검증한다**

Run: `@('2026-07-29-rfdetr-fusion-consensus-design.md','2026-07-29-rfdetr-desktop-nine-image-evaluation-design.md','2026-07-29-offline-cpu-rfdetr-fusion-deployment-design.md') | ForEach-Object { if (-not (Test-Path (Join-Path 'docs/superpowers/specs' $_))) { throw "missing: $_" } }`

Expected: PASS.

- [ ] **Step 5: 변경만 커밋한다**

Run: `git add docs/superpowers/specs; git commit -m "docs: separate CPU final and legacy pipeline designs"`

Expected: 설계 문서만 포함한 커밋이 생성된다.

### Task 4: 문서 변경 및 CPU 경로 회귀 검증

**Files:**
- Test: `tests/test_rfdetr.py`
- Test: `tests/test_rfdetr_cpu.py`
- Test: Git diff

**Interfaces:**
- Consumes: Tasks 1–3의 문서와 기존 CPU RF-DETR 테스트
- Produces: 레거시 런타임 무변경, 문서 정합성, CPU RF-DETR 테스트 통과 증거

- [ ] **Step 1: RF-DETR CPU 테스트를 실행한다**

Run: `$env:PYTHONPATH='src'; pytest tests/test_rfdetr.py tests/test_rfdetr_cpu.py -q`

Expected: PASS.

- [ ] **Step 2: 이번 작업이 레거시 런타임을 건드리지 않았는지 확인한다**

Run: `git diff --name-only HEAD~3..HEAD; git diff --name-only -- AGENTS.md README.md docs/superpowers/specs`

Expected: 이번 작업 범위는 `AGENTS.md`, `README.md`, `docs/superpowers/specs/`이며 `src/`, `models/`, `portable_cpu_smoke/`의 레거시 파일은 변경되지 않는다.

- [ ] **Step 3: 최종 상태를 기록한다**

최종 응답에 CPU 테스트 결과, 수정 파일, 기존 사용자 변경을 보존했다는 사실을 기록한다. 실제 E/M/H 성능 수치는 이번 작업에서 실행·검증하지 않았으므로 새 수치를 주장하지 않는다.

## Self-Review

- Spec coverage: Task 1은 규범 계약, Task 2는 사용자 실행 안내, Task 3은 최종/레거시 문서 상태, Task 4는 회귀와 범위 확인을 각각 다룬다.
- Placeholder scan: 미결정 표식이나 나중에 결정할 항목이 없다.
- Type consistency: 코드 API를 새로 정의하지 않으며, 모든 명령은 현 저장소 경로를 사용한다.
