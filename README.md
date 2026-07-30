# Bixolon Bakery AI

베이커리 scan image에서 SKU, 수량, 위치를 재현 가능하게 추론하기 위한
연구·개발 저장소입니다. 데이터 구축, 모델 학습, 실험, canonical CPU 추론,
평가·benchmark, Windows camera app과 배포를 하나의 versioned control plane으로
관리합니다.

정확성과 재현성이 latency보다 우선이며, 근거가 acceptance rule을 통과하지
못하면 반드시 `Unknown`으로 종료합니다.

## Canonical CPU pipeline

```text
Input image
  -> EXIF-transposed RGB canonical frame
  -> RF-DETR-L (CPU/FP32, manifest calibration)
  -> RepViT-M1 immutable direct-decision gate
  -> conditional DINOv3 global + local evidence
  -> immutable fusion consensus
  -> registered SKU or Unknown
```

- Detector threshold는
  `models/rfdetr_large_bakery_v1/manifest.json`에서만 읽습니다.
- RepViT direct gate가 거절한 object에만 DINOv3를 실행합니다.
- Fusion SKU는 local Top-1과 같거나, RepViT/DINO global Top-1 consensus와
  margin `>= 0.85`를 동시에 만족할 때만 승인합니다.
- 등록 SKU만 SKU 합계에 포함하고 `Unknown`은 decision path·ranked evidence와
  함께 별도 보고합니다.
- 모델, calibration, policy, prototype/support bank는 실행 전 SHA-256 검증을
  통과해야 합니다.

Composition은 `configs/pipelines/canonical_cpu.yaml`, classifier artifact binding은
`configs/cpu_rfdetr_classifier_policy.yaml`, 저장소 전체 외부 자산 identity는
`artifacts.lock.json`이 정의합니다.

## Repository map

| 경로 | 책임 |
|---|---|
| `apps/` | Flutter camera evaluator 등 사용자 application |
| `src/bakery_scanner/` | data, detection, classification, pipelines, evaluation, benchmarking, artifact code |
| `configs/` | pipeline/data/training/evaluation/deployment configuration |
| `data/` | catalog, dataset manifest, split identity, synthetic fixture |
| `models/` | model README와 manifest; weight는 외부 저장 |
| `policies/` | Git에서 관리하는 immutable calibrated policy |
| `experiments/` | hypothesis, resolved config, receipt, compact conclusion |
| `benchmarks/` | protocol, reviewed baseline, locked evidence identity |
| `tools/` | 새 운영 도구의 책임별 entry point |
| `scripts/` | 기존 command compatibility path |
| `deployment/` | installer와 runtime lock |
| `tests/` | hermetic, contract, integration, artifact, GPU suite |
| `docs/` | architecture, workflow, runbook, ADR, research/archive |

상세 설계는 `docs/architecture/repository.md`, 실험 흐름은
`docs/workflows/experiment-lifecycle.md`를 참고하세요.

## Quick start

Python 3.11 환경에서:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
$env:PYTHONPATH = (Resolve-Path .\src).Path
python -m pytest
python -m bakery_scanner.artifacts.cli --manifest-only
```

기본 test suite는 외부 자산 없이 실행되는 first-party test만 수집합니다.
로컬 model/data를 materialize한 뒤 전체 artifact integration을 실행하려면:

```powershell
python -m bakery_scanner.artifacts.cli
python -m pytest -m artifact
```

`gpu`, `slow` suite는 각각 명시적으로 선택합니다. Test skip은 release gate 통과를
의미하지 않습니다.

## Data and experiment workflow

1. `data/manifests/`와 `data/splits/`에서 dataset와 역할을 version합니다.
2. `experiments/template/experiment.yaml`로 hypothesis와 모든 입력 identity를
   고정합니다.
3. Development에서 학습·탐색하고 calibration에서 threshold/policy를 선택합니다.
4. Candidate를 freeze한 후 locked acceptance를 한 번 평가합니다.
5. IoU `0.50` one-to-one error taxonomy와 warmed CPU E/M/H benchmark를 별도
   기록합니다.
6. Evidence가 baseline을 통과할 때만 새 model/policy version과 배포 package를
   만듭니다.

Locked set이 선택에 사용되면 그 set은 더 이상 acceptance evidence가 아닙니다.

## Artifact and Git policy

Git에는 code, config, manifest, split identity, 작은 immutable calibration과
policy, 작은 fixture와 reviewed summary만 저장합니다. Dataset, checkpoint, full run, raw prediction,
prototype/support bank, runtime, wheel, installer는 외부 artifact store에 둡니다.

Git LFS는 license와 재배포 권한을 검토한
`release-assets/models/**`와 `release-assets/prototype-banks/**`에만 제한합니다.
일반 `*.pt`, `*.pth`, `*.onnx` wildcard LFS rule은 사용하지 않습니다. 자세한
복구·검증 절차는 `docs/runbooks/artifacts.md`에 있습니다.

## Evaluation and performance

Canonical-frame box를 deterministic one-to-one IoU `0.50`으로 match하고 SKU
error, miss, duplicate, non-target, split, merge, `Unknown`, final/GT count를
보고합니다. CPU 성능은 warm-up 뒤 detector, crop, RepViT, conditional DINOv3,
fusion을 포함한 E/M/H mean과 stage timing, DINO execution rate로 측정합니다.

측정된 result receipt 없이 정확도나 속도 향상을 주장하지 않습니다.

## Applications and deployment

Windows Flutter evaluator는 `apps/bakery_camera_flutter/`, installer definition과
runtime lock은 `deployment/camera_installer/`에 있습니다. Package builder는
allowlist와 hash manifest를 사용하며 생성된 runtime·payload·installer는 Git에
commit하지 않습니다.

## Legacy compatibility

기존 D-FINE-N → MobileNetV4 Box Assurance → conditional ConvNeXt-Tiny →
component resolver → RepViT → conditional DINOv3 GPU pipeline은 legacy입니다.
`portable_cpu_smoke/`와 기존 config/script/import path의 동작은 보존됩니다.
Canonical RF-DETR 문서나 구현이 legacy 경로로 silently fallback해서는 안 됩니다.
