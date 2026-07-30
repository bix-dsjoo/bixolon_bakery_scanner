# BIXOLON Bakery Self Checkout 1.1.0

Windows용 베이커리 셀프 계산대 프로토타입입니다. 고객은 트레이를 카메라에 놓고 결과를 확인한 뒤, 필요한 경우 전체 상품 목록에서 직접 선택하여 시뮬레이션 결제까지 진행합니다. 결제 완료 또는 관리자 화면 종료 뒤에는 항상 다음 고객을 위한 준비 화면으로 돌아갑니다.

## 실행과 배포

Windows 10/11 x64와 Flutter 3.44.7이 필요합니다.

```powershell
$env:Path = 'C:\workspace\tools\flutter-3.44.7\bin;' + $env:Path
flutter pub get
flutter run -d windows
```

릴리스 패키지는 다음처럼 생성합니다. 실행 파일만 복사하지 말고 `build\windows\x64\runner\Release` 전체를 함께 배포해야 합니다.

```powershell
flutter build windows --release
```

## 고객 흐름

1. 트레이를 놓고 **빵 확인하기**를 누릅니다.
2. 자동으로 확정할 수 없는 빵은 상위 3개 제안 또는 전체 상품 목록에서 고객이 직접 선택합니다.
3. 반복 촬영으로도 확인할 수 없으면 직접 담기 모드에서 상품과 수량을 구성합니다.
4. 주문과 금액을 확인하고 **결제하기**를 누릅니다.
5. 로컬 감사 기록과 시뮬레이션 결제가 모두 저장된 뒤에만 완료 화면이 표시됩니다.

고객 선택은 과거의 모델 결과를 고치지 않습니다. 원본 추론은 계속 `Unknown`을 포함한 불변 감사 증거로 남고, 최종 주문에는 자동 수락·Top-3·전체 상품 선택·자동 결과 변경·직접 담기 중 어떤 경로였는지가 따로 기록됩니다.

1.1.0의 결제는 **시뮬레이션**입니다. 카드, PG, POS, 영수증 프린터와 연동하지 않으며 실제 청구를 만들지 않습니다.

## 관리자 콘솔

헤더의 프로토타입 관리자 진입 버튼으로 관리자 모드에 들어갑니다. 인증/PIN은 1.1.0 범위에 포함되지 않습니다. 진행 중인 고객 계산이 있으면 취소 확인이 필요하며, 관리자 종료는 새 고객 준비 화면으로 돌아갑니다.

관리자는 다음을 확인할 수 있습니다.

- 대시보드: 완료 결제, 금액, 재촬영, Unknown, 변경, 직접 담기, 실패와 확인 필요 항목
- 거래 이력/상세: 촬영·추론·고객 선택·최종 주문·시뮬레이션 결제·모델/정책/전처리 provenance
- 검토 인박스: 관리자 주석을 append-only로 추가; 추론, 고객 선택, 완료 주문은 수정하지 않음
- 상품 관리: 새 카탈로그 리비전으로만 저장; 기존 주문의 이름·가격 스냅샷은 유지
- 진단: 카메라, 워커, SQLite, 카탈로그, SHA-256 증거와 저장된 단계별 시간 정보 읽기 전용 확인
- 설정/보존: 다음 고객 세션부터 적용되는 지원 설정과, 확인이 필요한 이미지 보존 미리 보기

## 감사와 보존

애플리케이션 데이터 아래에 SQLite 데이터베이스와 감사 파일을 저장합니다.

```text
BixolonBakeryScanner/
├── scanner.db
└── audit/sessions/YYYY/MM/DD/{session_id}/
    ├── attempt-001.jpg
    ├── attempt-001.inference.json
    └── final-order.json
```

캡처, 추론 영수증, 최종 주문 영수증의 경로·크기·SHA-256을 기록합니다. 강제 종료 뒤의 비종료 세션은 `interrupted`로 남으며, 결제를 자동 완결하지 않습니다. 보존 실행은 이미지 파일만 대상으로 하며, 삭제 전 미리 보기와 명시적 확인을 요구합니다. 삭제 후에도 거래·추론·고객 선택·주문·결제·검토와 원래 SHA-256/바이트 크기는 유지됩니다.

## 디자인 자산

Pretendard 1.3.9(400/500/600/700)를 번들로 포함합니다. 버전·라이선스·파일 SHA-256은 `assets/fonts/pretendard_manifest.json`과 `assets/fonts/OFL.txt`에 있습니다.

생성 이미지는 `manual_cart_entry`와 `payment_complete` 두 개뿐이며 고객 안내용 보조 일러스트입니다. 제품 사진, 카메라 증거, 추론 입력, 학습/평가 데이터로 사용할 수 없습니다. 프롬프트·도구 provenance·크기·SHA-256·알파 검증은 `assets/asset_manifest.json`에 기록됩니다.

```powershell
dart run tool\verify_ui_assets.dart
```

## 검증

```powershell
dart run build_runner build --delete-conflicting-outputs
dart run tool\verify_ui_assets.dart
flutter test
flutter analyze
```

저장소 루트에서는 Python 계약/단위 테스트도 실행합니다.

```powershell
$env:PYTHONPATH='src'
python -m pytest tests\contract -q
python -m pytest tests\unit -q
```

릴리스 검증 범위와 현재 결과는 [docs/releases/1.1.0.md](../../docs/releases/1.1.0.md)에 기록합니다.
