# CPU RF-DETR 최종 파이프라인 문서화 설계

- 날짜: 2026-07-29
- 상태: 승인된 문서화 설계

## 목적

프로젝트의 최종 추론 경로를 CPU 기반 RF-DETR-L과 fail-closed fusion
classifier로 명확히 하고, 기존 D-FINE/Box Assurance/GPU 경로는 삭제하지
않은 채 레거시 기능 및 과거 설계로 구분한다.

## 최종 런타임 계약

```text
EXIF-transposed RGB canonical image
  -> RF-DETR-L on CPU/FP32
  -> calibrated product proposals in canonical visual coordinates
  -> RepViT-M1 direct-decision gate
  -> conditional DINOv3 global + local evidence
  -> immutable fusion consensus decision
  -> SKU or Unknown, per-object records, aggregate, evaluation report
```

RF-DETR-L은 `models/rfdetr_large_bakery_v1/manifest.json`에 고정된 모델,
SHA-256, 그리고 calibration score threshold를 사용한다. 제품 클래스와
유한·양의·화면 내 박스만 `BreadProposal`로 변환하고, 순서는 결정적으로
유지한다.

RepViT 직접 확정 기준을 통과한 객체는 DINOv3를 실행하지 않는다. 직접
확정하지 못한 객체만 DINOv3 global prototype 및 local patch-bank evidence를
생성한다. SKU 확정은 다음 중 하나일 때만 허용한다.

1. fusion Top-1이 DINOv3 local Top-1과 같다.
2. fusion Top-1이 RepViT Top-1 및 DINOv3 global Top-1과 같고, fusion
   Top-1/Top-2 margin이 0.85 이상이다.

그 외 결과는 반드시 `Unknown`이다.

## 문서 및 진입점 정리

- `AGENTS.md`는 위 CPU 최종 계약, 출력 계약, 측정 규칙과 실패-폐쇄 원칙을
  최우선 규범으로 둔다.
- `README.md`는 최종 CPU 런타임, 오프라인 ZIP 사용법, SHA-256 검증, Batch2
  9장 평가 산출물을 먼저 설명한다.
- 최신 CPU RF-DETR 문서 세 개(데스크톱 9장 평가, fusion consensus, 오프라인
  배포)를 최종 설계군으로 상호 링크한다.
- D-FINE/Box Assurance/기존 CPU smoke/GPU 0.5초 게이트 문서 및 자산은
  이동하거나 삭제하지 않는다. 각 진입점에서 레거시 또는 과거 실험이며 최종
  CPU 경로가 아님을 명시한다.

## 결과 및 검증 계약

최종 객체는 canonical box, SKU 또는 `Unknown`, confidence, decision path,
unknown reason(해당 시)을 기록한다. 9장 Batch2 평가는 one-to-one IoU 0.50
매칭에서 GT, predictions, matched, FP, FN, Top-1, Top-3과 E/M/H 평균 E2E
지연을 기록한다. CPU 성능 수치는 이 PC와 패키지된 CPU/FP32 환경에서 실제
측정한 값만 주장한다.

## 비범위

- 기존 D-FINE 모델, Box Assurance, resolver, portable CPU smoke 및 GPU
  실험 코드를 삭제·이동·재작성하지 않는다.
- 모델 가중치·calibration·사용자 작업 파일을 변경하지 않는다.
- 새 정확도나 성능 수치를 문서에 임의로 추가하지 않는다.

## 검증

문서 링크와 최종 경로의 명칭을 점검하고, CPU RF-DETR 패키지의 기존 단위
테스트를 실행한다. 변경 후 Git diff에서 레거시 런타임 파일이 수정 또는
삭제되지 않았는지 확인한다.
