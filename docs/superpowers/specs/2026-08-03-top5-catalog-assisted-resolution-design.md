# Top5 + 상품 검색 사용자 확인 설계

**상태:** 2026-08-03 사용자 승인

**책임:** 자동 추론의 immutable evidence를 바꾸지 않으면서 `Unknown` 객체를 Top5 또는 전체 등록 상품 검색으로 사용자가 안전하게 확정하게 한다.

## 1. 목표

- 자동 판정이 수락하지 않은 객체는 계속 `Unknown`이다.
- 각 `Unknown`은 서로 다른 등록 SKU 다섯 개를 점수 내림차순의 안정적인 순위로 제공한다.
- 사용자는 Top5 중 하나를 선택하거나 전체 활성 상품 catalog를 검색해 선택할 수 있다.
- 선택 전, 취소, 검색 실패 또는 `모두 아님`은 `Unknown`을 유지한다.
- 사용자 선택은 immutable inference receipt를 수정하지 않고 별도의 audited resolution로 저장한다.
- 촬영 또는 객체 배치가 부적합한 경우에는 후보를 보여주지 않고 재배치·재촬영을 요청한다.

## 2. 기존 구현과 변경점

현재 worker와 Flutter 앱에는 다음 기능이 이미 있다.

- detector box overlap 및 no-bread presentation gate
- `Unknown`의 Top3 후보
- 사용자 Top3 선택
- 전체 상품 catalog 검색과 선택
- immutable inference와 customer resolution의 분리 저장

이번 변경은 새 UX를 별도로 만드는 작업이 아니라 기존 수직 경로를 정확히 다음처럼 확장하는 작업이다.

| 현재 | 변경 후 |
| --- | --- |
| `unknown_top3` | 신규 실행은 `unknown_top5` |
| 정확히 3개 후보 | 정확히 5개 후보 |
| `customer_top3` | 신규 선택은 `customer_top5` |
| 약한 Unknown은 재촬영 가능 | 분류가 애매한 경우 Top5 + 검색 |
| no-bread/overlap 재촬영 | 그대로 유지 |

기존 DB의 `unknown_top3` 및 `customer_top3` 기록은 감사 증거로 보존한다. migration은 과거 행을 새 의미로 다시 쓰지 않고 두 legacy 값을 읽을 수 있게 유지한다.

## 3. 자동 추론과 사용자 확인 경계

```text
canonical image
  -> RF-DETR-L
  -> scene presentation gate
       -> no object 또는 overlap: needs_retake, 후보 없음
       -> usable scene: classification
  -> RepViT direct gate
       -> 수락: registered SKU
       -> 거절: conditional DINOv3 + immutable fusion
            -> 수락: registered SKU
            -> 거절: Unknown + ranked Top5
  -> Flutter customer review
       -> Top5 선택: customer_top5
       -> catalog 검색 선택: customer_catalog
       -> 취소/모두 아님: Unknown 유지
```

Top5는 worker의 100ms 측정 payload에 포함한다. catalog 검색, 사용자 입력과 선택 시간은 worker latency에서 제외하고 UX 지표로 별도 측정한다.

## 4. 후보 계약

새 worker result의 Unknown 객체는 다음 조건을 만족한다.

- `decision_path == "unknown_top5"`
- `sku_id == null`, `sku_name == "Unknown"`
- `top5` 배열 길이가 정확히 5이다.
- rank는 정확히 `1, 2, 3, 4, 5`이다.
- SKU ID는 모두 서로 다르고 등록 범위 `1..20`에 속한다.
- score는 유한한 `[0, 1]` 값이며 rank 순으로 non-increasing이다.
- 동일 점수의 tie-break는 canonical SKU order로 결정돼 반복 실행에서 변하지 않는다.
- registered SKU 객체는 `top5`가 비어 있고 `unknown_reason`이 없다.

RepViT direct reject 후 DINO 오류가 난 경우에도 RepViT calibrated score의 Top5와 failure provenance를 보존한다. 후보는 자동 수락 threshold나 fusion rule을 우회하지 않는다.

## 5. Presentation gate

재촬영과 사용자 확인은 서로 다른 문제다.

- detector 결과가 0개이면 scan retake `no_bread_detected`
- detector box가 calibrated overlap threshold 이상이면 object retake `separate_breads`
- scene이 usable하고 자동 분류만 실패하면 presentation state `unknown`
- 분류 Top1 score나 Top1-Top2 margin이 낮다는 이유만으로 재촬영을 강제하지 않는다. 검색 escape hatch가 있으므로 `candidate_evidence_weak`은 신규 실행에서 사용하지 않는다.

향후 blur, edge truncation, 최소 크기 gate를 추가하려면 별도의 calibrated presentation-policy artifact와 locked scene-quality evidence가 필요하다. 이번 변경에서 검증되지 않은 heuristic을 추가하지 않는다.

## 6. Flutter 사용자 흐름

- review panel은 다섯 후보를 순위, 상품명, 상품 사진, 가격과 함께 표시한다.
- 각 후보 선택은 해당 object의 exact candidate SKU인지 다시 검증한다.
- `다른 상품 찾기`는 session이 snapshot한 활성 catalog만 검색한다.
- 검색은 상품명과 등록 catalog가 제공하는 검색 contract를 사용하며 inference 결과를 수정하지 않는다.
- catalog에 mapping되지 않은 candidate는 숨기지 않고 unavailable 상태로 표시하고 검색으로 이동할 수 있게 한다.
- `모두 아님` 또는 뒤로가기는 객체를 resolved로 만들지 않는다.
- 모든 Unknown이 resolved되기 전에는 결제 단계로 진행하지 않는다.

## 7. Audit 및 DB migration

- DB schema를 v5로 올린다.
- candidate rank constraint를 `1..5`로 넓힌다.
- inference object는 legacy `unknown_top3`와 신규 `unknown_top5`를 모두 허용한다.
- resolution/final-order source는 legacy `customer_top3`와 신규 `customer_top5`를 모두 허용한다.
- 신규 Top5 선택만 `customer_top5`로 기록하고 선택 rank `1..5`를 저장한다.
- catalog 검색 선택은 계속 `customer_catalog`이며 candidate rank는 null이다.
- v4 -> v5 migration은 immutable 행의 값과 ID를 변경하지 않고 table constraints만 재구성한다.
- migration 전후 row count와 receipt hash에 쓰이는 canonical inference JSON의 일관성을 검증한다.

## 8. 평가

locked acceptance set에서 다음을 보고한다.

- 자동 registered-SKU 오분류, miss, duplicate, non-target, split, merge, Unknown
- Unknown denominator
- Unknown Top1/Top3/Top5 correct count와 recall
- Top5 miss 목록
- Top5 선택률, catalog 검색 전환율, 검색 성공률
- candidate rank별 사용자 선택 분포
- 사용자 오선택 및 취소율
- 후보 표시부터 선택까지의 UX 시간

Top5 recall `100%`는 locked set의 목표이지 운영 중 모든 미지 입력에 대한 보장이 아니다. Top5에 정답이 없으면 catalog 검색을 사용하고, 검색에서도 확정하지 못하면 `Unknown`을 유지한다.

## 9. 수락 조건

- Python classification, worker result, Dart parser, UI, audit store와 admin view가 Top5 의미에 동의한다.
- 신규 Unknown은 정확히 다섯 후보를 갖고 신규 registered 결과는 후보가 없다.
- Top5와 catalog 선택이 서로 다른 audited source로 저장된다.
- 기존 Top3 감사 행을 읽을 수 있고 migration이 과거 evidence를 다시 쓰지 않는다.
- no-bread/overlap retake에는 후보가 노출되지 않는다.
- weak classification은 retake가 아니라 Unknown Top5 + 검색으로 이동한다.
- 취소/모두 아님은 `Unknown`을 유지한다.
- canonical SKU/count/location/confidence/path 및 provenance 불변식이 유지된다.
- 관련 Python 및 Flutter unit, contract, integration, migration 테스트가 통과한다.
