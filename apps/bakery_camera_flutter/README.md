# BIXOLON Bakery Self Checkout 1.1.0

Windows용 빵 셀프 계산대 프로토타입입니다. 고객은 트레이를 카메라 아래에 놓고 빵을 확인한 뒤, 필요한 경우 화면에서 직접 상품을 선택하고 결제 직전까지 진행합니다.

## 설치와 실행

Windows 10/11 x64에서 Flutter 3.44.7과 Windows 빌드 도구를 준비한 뒤 이 폴더에서 실행합니다.

```powershell
$env:Path = 'C:\workspace\tools\flutter-3.44.7\bin;' + $env:Path
flutter pub get
flutter run -d windows
```

릴리스 패키지를 만들 때는 다음을 사용합니다.

```powershell
flutter build windows --release
```

실행 파일만 따로 복사하지 말고 `build\windows\x64\runner\Release` 전체를 함께 배포해야 합니다.

## 고객 여정

1. 고객이 트레이를 카메라 아래에 놓고 **빵 확인하기**를 누릅니다.
2. 등록된 상품은 주문에 담기고, 확신할 수 없는 빵은 화면에 제시된 후보 또는 전체 상품 목록에서 고객이 직접 고릅니다.
3. 고객은 전체 목록에서 상품을 추가하고 수량을 조정할 수 있습니다. 실제 트레이 수량이 다르면 다시 촬영합니다.
4. 주문의 수량과 금액을 확인한 뒤 한 번만 **결제하기**를 누릅니다.
5. 완료 화면은 로컬 저장이 끝난 뒤에만 표시되며, 다음 고객 시작으로 새 준비 화면으로 돌아갑니다.

반복 촬영으로도 확인되지 않으면 직접 담기 모드가 열립니다. 이때도 같은 전체 상품 목록과 수량 조정 화면을 사용합니다.

## 고객 선택과 추론 기록

고객의 상품 선택은 모델 결과를 고치지 않습니다. 자동 결과 수락, 제시된 후보 선택, 전체 목록 선택, 자동 결과 변경, 직접 담기 중 어떤 방식으로 주문되었는지 별도 기록됩니다. 확신할 수 없는 결과는 원본 추론 기록에서 계속 `Unknown`으로 남고 AI 상품 합계에 포함되지 않습니다.

1.1.0의 결제는 **시뮬레이션**입니다. 카드사, PG, POS, 영수증 프린터와 연동하지 않으며 실제 승인·청구를 만들지 않습니다. 저장 트랜잭션이 실패하면 완료 화면을 표시하지 않습니다.

## 로컬 감사 기록과 복구

Windows 앱 데이터 아래 `BixolonBakeryScanner/`에 SQLite 데이터베이스와 감사 파일을 둡니다.

```text
BixolonBakeryScanner/
├── scanner.db
└── sessions/YYYY/MM/DD/{session_id}/
    ├── attempt-001.jpg
    ├── attempt-001.inference.json
    └── final-order.json
```

캡처 이미지, 추론 영수증, 최종 주문 파일에는 크기와 SHA-256을 함께 기록합니다. 앱이 비정상 종료되면 이전의 진행 중 세션은 `interrupted`로 표시됩니다. 이미 저장된 이미지와 영수증은 보존하며, 결제를 재개하거나 자동으로 완료 처리하지 않습니다. 다음 고객은 새 세션으로 시작합니다.

## 글꼴과 생성 일러스트 자산

Pretendard 1.3.9의 400/500/600/700 웨이트를 앱에 포함합니다. 버전, 라이선스, 크기, SHA-256은 `assets/fonts/pretendard_manifest.json`과 `assets/fonts/OFL.txt`에서 확인할 수 있습니다.

생성 이미지는 `manual_cart_entry`와 `payment_complete` 두 개뿐이며, 고객 안내용 보조 일러스트입니다. 제품 사진, 카메라 증거, 후보 이미지, 추론·학습·평가 데이터로 사용하지 않습니다. 각 자산의 프롬프트, 생성 경로, 금지사항, 크기, SHA-256은 `assets/asset_manifest.json`에 기록되어 있고 다음 검증으로 확인합니다.

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

저장소 루트에서는 Python 계약 테스트도 실행할 수 있습니다.

```powershell
$env:PYTHONPATH='src'
python -m pytest tests\contract -q
```

## 관리자 범위

이 고객 모듈은 계산 전 고객 흐름과 감사 기록까지만 제공합니다. 추론 근거·오답 검토·거래 조회·카탈로그 관리·설정·진단은 별도 관리자 콘솔 계획에서 다룹니다. 고객 화면에는 모델명, 점수, 해시, 장치, 단계 시간 또는 관리자 조작을 노출하지 않습니다.
