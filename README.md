# 빅솔론 베이커리 스캐너

스캔 이미지에서 베이커리 SKU, 수량, 위치를 결정론적으로 추론하는
CPU 추론 파이프라인입니다. 최종 경로는 정확성과 재현성, 그리고
오분류를 피하는 fail-closed `Unknown` 처리를 우선합니다.

## 최종 CPU 파이프라인

입력 이미지는 먼저 EXIF 방향을 반영하고 RGB로 변환한 canonical frame으로
고정됩니다. 그 프레임에서 다음 순서로 실행합니다.

```text
EXIF-transposed RGB canonical frame
  -> RF-DETR-L (CPU/FP32, manifest의 보정 임계값)
  -> RepViT-M1 직접 결정 gate
  -> 거부된 후보에 한해 DINOv3 global + local evidence
  -> immutable fusion consensus
  -> SKU 또는 Unknown
```

RF-DETR-L의 박스와 결과 위치는 canonical frame 좌표를 사용합니다. 모델,
보정값, 전처리, support/prototype bank, fusion 정책은 구성 파일에 지정된
SHA-256 무결성 검증을 통과해야 실행됩니다.

RepViT 직접 결정 gate가 승인하면 그 결정이 최종 결과입니다. 직접 결정이
거부된 경우에만 DINOv3 evidence와 fusion을 실행하며, fusion SKU는 다음 둘
중 하나일 때만 승인됩니다.

1. fusion Top-1이 DINOv3 local Top-1과 같다.
2. fusion Top-1, RepViT Top-1, DINOv3 global Top-1이 모두 같고 fusion
   Top-1/Top-2 margin이 0.85 이상이다.

이 조건을 충족하지 못하는 모든 분류 결과는 `Unknown`입니다. 임의의 등록
SKU로 대체하지 않으며, `Unknown`은 SKU 합계와 분리해 decision path 및
근거와 함께 보고합니다.

## 오프라인 ZIP 실행

최종 오프라인 CPU 패키지는 `portable_rfdetr_cpu/`입니다. ZIP을 로컬 드라이브에
압축 해제한 뒤, 해당 디렉터리에서 PowerShell을 실행합니다. Python 설치,
패키지 설치, 네트워크, GPU는 필요하지 않습니다.

```powershell
powershell -ExecutionPolicy Bypass -File .\Verify-Package.ps1
powershell -ExecutionPolicy Bypass -File .\Run-CPU-Batch2.ps1
```

`portable_rfdetr_cpu/Verify-Package.ps1`는 `package-manifest.json`에 기록된
모든 패키지 파일의 SHA-256과 CPU 전용 런타임 import를 확인합니다.
`portable_rfdetr_cpu/Run-CPU-Batch2.ps1`는 번들 런타임으로
`scripts/run_cpu_rfdetr_fusion.py`를 실행하고, 기본적으로
`results/batch2-<timestamp>/`에 결과를 만듭니다. 세부 패키지 안내는
[portable RF-DETR CPU README](portable_rfdetr_cpu/README.md)를 참고하세요.

## `report.json` 계약

실행 결과의 `report.json`은 고정 Batch2 9개 이미지에 대한 CPU 결과를 담습니다.
검출 평가는 canonical-frame 박스를 one-to-one IoU `0.50`으로 매칭하며,
`metrics`에는 GT, predictions, matched, FP, FN, Top-1, Top-3 및 비율이
포함됩니다. `images`에는 이미지별 결과와 객체 결정(예측 SKU 또는 `Unknown`,
Top-3, IoU, 사유)이 기록되고, `profiles`에는 E/M/H 그룹별 end-to-end 시간
요약이 기록됩니다. 오버레이 이미지는 `overlays/`에 저장됩니다.

성능 또는 정확도 수치는 생성된 보고서에 실제로 기록된 값만 사용해야 합니다.

## 레거시 D-FINE smoke 경로

`portable_cpu_smoke`는 보존된 레거시 D-FINE CPU smoke 경로이며 최종 런타임이
아닙니다. 기존 D-FINE, Box Assurance, resolver, GPU 실행 및 portable CPU smoke
파일의 동작은 이 최종 CPU 경로 문서화로 변경하지 않습니다.

## 설계 문서

- [최종 CPU RF-DETR 문서화 설계](docs/superpowers/specs/2026-07-29-cpu-rfdetr-final-documentation-design.md)
- [오프라인 CPU RF-DETR fusion 배포 설계](docs/superpowers/specs/2026-07-29-offline-cpu-rfdetr-fusion-deployment-design.md)
- [RF-DETR desktop 9-image 평가 설계](docs/superpowers/specs/2026-07-29-rfdetr-desktop-nine-image-evaluation-design.md)
- [RF-DETR fusion consensus 설계](docs/superpowers/specs/2026-07-29-rfdetr-fusion-consensus-design.md)
