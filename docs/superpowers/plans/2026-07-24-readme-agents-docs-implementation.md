# README and AGENTS Documentation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bakery Scanner의 최종 제품 목표와 모든 개발 에이전트가 따라야 할 구현·검증 원칙을 루트 `README.md`와 `AGENTS.md`에 문서화한다.

**Architecture:** `README.md`는 제품을 처음 접하는 사람에게 전체 추론 흐름과 성공 기준을 설명한다. `AGENTS.md`는 같은 흐름을 구현하는 작업자가 지켜야 할 책임 경계, 판정 정책, 데이터 계약, 검증 기준을 규정하며 현재 구현 진척은 두 문서 모두에서 제외한다.

**Tech Stack:** Markdown, D-FINE/RTMDet, MobileNetV4/RepViT, DINOv3, CPU inference

## Global Constraints

- Detector → Verifier → Classifier → 조건부 DINOv3 재확인 순서를 유지한다.
- DINOv3는 분류 신뢰도가 낮거나 제품 간 구분이 어려운 경우에만 실행한다.
- 등록 제품임을 충분히 입증할 수 없는 결과는 `Unknown`으로 처리한다.
- 최종 결과는 각 제품의 품목, 수량, 위치, 판정 신뢰도를 제공한다.
- 정확성 출하 기준은 잠긴 승인 평가셋에서 오분류, 누락, 중복, 비대상 검출 각각 0건이다.
- 전체 CPU 추론 시간 목표는 현재 기준 PC에서 이미지당 0.5초 이하이다.
- 현재 구현 상태, 확정되지 않은 임계값, 존재하지 않는 실행 명령은 문서에 포함하지 않는다.

---

### Task 1: 제품 목표 README 작성

**Files:**
- Create: `README.md`

**Interfaces:**
- Consumes: `docs/superpowers/specs/2026-07-24-readme-agents-docs-design.md`
- Produces: 프로젝트 목표, 추론 흐름, 출력 계약, 품질 및 성능 기준을 설명하는 루트 문서

- [ ] **Step 1: 아래 내용으로 `README.md`를 작성한다**

```markdown
# Bixolon Bakery Scanner

스캔 이미지 한 장에서 빵의 **품목, 수량, 위치**를 빠르고 정확하게
추론하는 CPU 기반 비전 파이프라인입니다.

## 목표

Bakery Scanner는 검출, 영역 검증, 제품 분류, 조건부 재확인을 결합하여
최종 판매 대상만 식별합니다.

- 빵을 하나도 놓치지 않습니다.
- 같은 빵을 중복 집계하지 않습니다.
- 집게, 포장지, 라벨, 트레이 등 비대상 물체를 빵으로 판단하지 않습니다.
- 등록 제품을 다른 제품으로 잘못 분류하지 않습니다.
- 확실하지 않은 품목은 억지로 분류하지 않고 `Unknown`으로 반환합니다.

## 추론 파이프라인

```text
스캔 이미지
  → Detector (D-FINE / RTMDet)
  → Verifier
  → Classifier (MobileNetV4 / RepViT)
  → 저신뢰·난분류 결과만 DINOv3 재확인
  → 품목·수량·위치 결과
```

### 1. Detector

D-FINE 또는 RTMDet가 입력 이미지에서 빵의 위치와 후보 박스를 검출합니다.
이 단계의 출력은 최종 결과가 아니라 Verifier가 확인할 후보 집합입니다.

### 2. Verifier

Verifier는 Detector의 후보 박스를 검증하고 필요한 보정과 정리를 수행합니다.
누락된 빵, 하나의 빵을 가리키는 중복 박스, 여러 빵을 합친 박스, 배경이나
비대상 물체의 오검출을 제거하여 빵 하나당 하나의 최종 대상 영역을
확정합니다.

### 3. Classifier

검증된 각 빵 영역은 MobileNetV4 또는 RepViT 기반 Classifier로 전달됩니다.
Classifier는 제품 종류와 분류 신뢰도를 산출하며, 신뢰도가 충분하고 혼동
가능성이 낮은 결과는 즉시 사용합니다.

### 4. DINOv3 재확인

DINOv3는 모든 대상에 실행하지 않습니다. 분류 신뢰도가 낮거나 서로
유사한 제품을 구분하기 어려운 경우에만 재확인을 수행합니다.

- 등록 제품임이 충분히 확인되면 해당 품목으로 확정합니다.
- 등록 제품으로 확정할 근거가 부족하면 `Unknown`으로 처리합니다.

이 조건부 경로는 정확도를 보완하면서 평균 추론 시간을 제한합니다.

## 출력

최종 추론 결과는 다음 정보를 제공합니다.

- 각 대상의 제품 식별자 또는 `Unknown`
- 원본 이미지 좌표계 기준 위치
- 각 대상의 판정 신뢰도와 판정 경로
- 품목별 수량
- 전체 제품 수량

개별 위치는 `[x_min, y_min, x_max, y_max]` 형식의 경계 상자로 표현합니다.
판정 경로는 Classifier 직접 확정, DINOv3 재확인, `Unknown`을 구분할 수
있어야 합니다.

## 성공 기준

### 정확성

고정된 운영 조건과 사전에 잠근 승인 평가셋에서 다음 오류가 각각 0건이어야
합니다.

- 오분류
- 누락
- 중복 집계
- 비대상 물체 검출

여기서 오인율 0%는 검증된 운영 범위의 출하 기준입니다. 검증되지 않은
모든 환경과 입력에 대한 절대적 무오류 보장을 의미하지 않습니다.

### 성능

현재 기준 PC의 CPU에서 Detector부터 최종 집계까지 전체 파이프라인의
이미지당 추론 시간 **0.5초 이하**를 목표로 합니다. 정확성 승인 기준을
훼손하는 속도 최적화는 허용하지 않습니다.

## 핵심 원칙

1. 정확성이 속도보다 우선합니다.
2. 불확실한 오분류보다 명시적인 `Unknown`이 안전합니다.
3. 각 모델은 하나의 명확한 책임을 가집니다.
4. 신뢰도 임계값과 모델 선택은 재현 가능한 평가 결과로 결정합니다.
5. 최적화 전후에 동일한 승인 평가 기준을 통과해야 합니다.
```

- [ ] **Step 2: README의 필수 용어와 제외 항목을 검사한다**

Run:

```powershell
$readme = Get-Content -Raw README.md
@(
  'D-FINE', 'RTMDet', 'Verifier', 'MobileNetV4', 'RepViT',
  'DINOv3', 'Unknown', '0.5초', '품목', '수량', '위치'
) | ForEach-Object {
  if (-not $readme.Contains($_)) { throw "README missing: $_" }
}
if ($readme -match '현재 구현|구현 완료|미구현') {
  throw 'README must not describe implementation status'
}
```

Expected: 출력 없이 exit code 0.

- [ ] **Step 3: README 변경을 커밋한다**

```powershell
git add -- README.md
git commit -m "docs: define bakery scanner product goal"
```

### Task 2: 개발 에이전트 규칙 작성

**Files:**
- Create: `AGENTS.md`

**Interfaces:**
- Consumes: 루트 `README.md`의 제품 목표와 출력 용어
- Produces: 저장소 전체에 적용되는 구현 책임, 판정 정책, 검증 및 완료 기준

- [ ] **Step 1: 아래 내용으로 `AGENTS.md`를 작성한다**

```markdown
# AGENTS.md

## 미션

이 저장소의 모든 작업은 스캔 이미지에서 빵의 품목, 수량, 위치를 정확하게
추론하는 CPU 파이프라인 완성을 목표로 한다. 최종 시스템은 Detector,
Verifier, Classifier, 조건부 DINOv3 재확인으로 구성한다.

우선순위는 다음과 같다.

1. 오분류, 누락, 중복, 비대상 검출 방지
2. 결정적이고 재현 가능한 결과
3. 현재 기준 PC CPU에서 전체 추론 0.5초 이하
4. 유지보수성과 구현 단순성

정확성을 희생하여 지연 시간 목표를 맞추지 않는다.

## 파이프라인 경계

처리 순서는 다음 계약을 유지한다.

```text
입력 이미지
  → Detector (D-FINE / RTMDet)
  → Verifier
  → Classifier (MobileNetV4 / RepViT)
  → 필요한 경우에만 DINOv3
  → 대상별 결과와 품목별 집계
```

### Detector

- 빵으로 보이는 모든 위치와 후보 박스를 생성한다.
- Detector 출력은 검증 전 후보이며 최종 제품 결과로 사용하지 않는다.
- 낮은 점수 후보를 너무 일찍 제거하여 recall을 훼손하지 않는다.
- 모델별 좌표와 점수를 공통 후보 계약으로 정규화한다.

### Verifier

- 후보가 정확히 하나의 대상 빵을 나타내는지 확인한다.
- 누락, 중복, 병합 박스, 분할 박스, 비대상 오검출을 해결한다.
- 최종 영역은 실제 빵 하나당 하나만 존재해야 한다.
- 제품 종류 분류 책임을 Verifier에 섞지 않는다.

### Classifier

- 검증된 빵 영역만 입력받는다.
- 제품 종류와 보정된 분류 신뢰도를 출력한다.
- 충분한 신뢰도와 클래스 간 분리도를 모두 만족한 결과만 직접 확정한다.
- 신뢰도 기준을 코드 여러 곳에 하드코딩하지 않는다.

### DINOv3 재확인

- 모든 영역에 기본 실행하지 않는다.
- 저신뢰 결과 또는 제품 간 구분이 어려운 결과에만 실행한다.
- 등록 제품과의 일치 근거가 충분할 때만 해당 품목으로 확정한다.
- 충분히 확신할 수 없으면 반드시 `Unknown`을 반환한다.

## 데이터 계약

모든 단계는 원본 이미지 좌표계를 보존한다. 경계 상자는
`[x_min, y_min, x_max, y_max]` 형식을 사용하며 유효한 이미지 범위 안에
있어야 한다.

대상별 최종 결과에는 최소한 다음 필드가 필요하다.

- 제품 식별자 또는 `Unknown`
- 원본 이미지 기준 경계 상자
- 판정 신뢰도
- 판정 경로: Classifier 직접 확정, DINOv3 재확인, `Unknown`

집계 결과의 품목별 수량 합계는 최종 대상 영역 수와 일치해야 한다.

## 정확성 불변 조건

- 실제 빵이 최종 결과에서 누락되지 않는다.
- 실제 빵 하나가 둘 이상으로 집계되지 않는다.
- 여러 빵을 하나의 대상으로 합치지 않는다.
- 배경, 트레이, 집게, 포장지, 라벨 등 비대상 물체를 집계하지 않는다.
- 등록 제품을 확신할 수 없을 때 임의의 등록 품목으로 대체하지 않는다.
- 좌표 변환 과정에서 대상 위치가 원본 이미지와 어긋나지 않는다.

정확성 출하 기준은 잠긴 승인 평가셋 전체와 필수 시나리오별로 오분류,
누락, 중복, 비대상 검출이 각각 0건인 것이다. 이 기준은 검증된 운영 범위에
적용하며 미관측 입력에 대한 절대 보장으로 표현하지 않는다.

## 성능 규칙

- 성능 지표는 모델 한 개가 아니라 입력부터 최종 집계까지 전체 지연
  시간으로 측정한다.
- 현재 기준 PC CPU에서 이미지당 0.5초 이하를 목표로 한다.
- 각 단계의 지연 시간을 별도로 기록하여 병목을 확인할 수 있어야 한다.
- DINOv3 조건부 실행률과 전체 지연 시간의 백분위 통계를 함께 확인한다.
- 저정밀도 변환, 입력 해상도 축소, 후보 제한 등 최적화는 정확성 회귀가
  없음을 검증한 뒤 채택한다.

## 변경 규칙

- 한 변경은 가능한 한 하나의 파이프라인 책임에 국한한다.
- 단계 간 계약을 바꾸면 생산자와 소비자 테스트를 함께 수정한다.
- 모델, 데이터, 임계값, 전처리, 후처리 버전을 결과와 함께 추적한다.
- 임계값은 평가 데이터로 보정하고 설정 파일이나 버전된 산출물에서
  관리한다.
- 재현 가능한 seed와 데이터 분할을 사용하며 학습/검증 누수를 막는다.
- 기존 사용자 변경이나 관련 없는 파일을 덮어쓰지 않는다.
- 현재 요청 범위를 벗어난 대규모 리팩터링을 섞지 않는다.

## 테스트 및 검증

변경 범위에 맞춰 다음을 검증한다.

1. 단위 테스트: 좌표, 후보 결합, 판정 분기, `Unknown`, 집계 계약
2. 통합 테스트: 전체 단계 순서와 단계 간 입출력
3. 회귀 테스트: 누락, 중복, 비대상, 유사 제품, 저신뢰 사례
4. 정확성 평가: 전체 및 시나리오별 오류 건수
5. 성능 평가: CPU warm-up 이후 전체 지연 시간과 단계별 지연 시간

평가 결과를 확인하지 않은 채 정확도나 속도 향상을 주장하지 않는다.
승인 평가셋을 보고 모델이나 임계값을 조정한 경우 새로운 잠금 평가셋으로
다시 검증한다.

## 완료 조건

작업은 다음 조건을 모두 만족해야 완료로 간주한다.

- 요청된 동작과 단계별 계약이 구현되어 있다.
- 관련 자동화 테스트가 통과한다.
- 오분류, 누락, 중복, 비대상 검출 회귀가 없다.
- 성능 관련 변경은 동일한 CPU 조건의 전후 수치가 있다.
- 최종 출력의 품목, 수량, 위치, 신뢰도, 판정 경로가 일관된다.
- 문서와 설정이 실제 동작과 모순되지 않는다.
```

- [ ] **Step 2: README와 AGENTS의 핵심 계약이 일치하는지 검사한다**

Run:

```powershell
$readme = Get-Content -Raw README.md
$agents = Get-Content -Raw AGENTS.md
@('Detector', 'Verifier', 'Classifier', 'DINOv3', 'Unknown', '0.5초') |
  ForEach-Object {
    if (-not $readme.Contains($_)) { throw "README missing: $_" }
    if (-not $agents.Contains($_)) { throw "AGENTS missing: $_" }
  }
if ($agents -notmatch '누락.*중복.*비대상') {
  throw 'AGENTS accuracy priorities are incomplete'
}
```

Expected: 출력 없이 exit code 0.

- [ ] **Step 3: AGENTS 변경을 커밋한다**

```powershell
git add -- AGENTS.md
git commit -m "docs: add repository agent guidelines"
```

### Task 3: 문서 최종 검증

**Files:**
- Verify: `README.md`
- Verify: `AGENTS.md`

**Interfaces:**
- Consumes: Task 1과 Task 2의 완성 문서
- Produces: 공백 오류와 금지된 자리표시자가 없는 검증 결과

- [ ] **Step 1: 자리표시자와 현재 상태 표현을 검사한다**

Run:

```powershell
if (rg -n 'TBD|TODO|FIXME|현재 구현|구현 완료|미구현' README.md AGENTS.md) {
  throw 'Documentation contains a placeholder or implementation status'
}
```

Expected: 검색 결과 없이 exit code 0.

- [ ] **Step 2: Git 공백 검사를 실행한다**

Run:

```powershell
git diff --check HEAD~2 -- README.md AGENTS.md
```

Expected: 출력 없이 exit code 0.

- [ ] **Step 3: 최종 변경 범위를 확인한다**

Run:

```powershell
git show --stat --oneline HEAD~1..HEAD
git status --short
```

Expected: 최근 문서 커밋에는 `AGENTS.md`만 포함되고, 작업 전부터 존재한
사용자 파일을 제외한 `README.md`와 `AGENTS.md` 변경은 모두 커밋된 상태.
