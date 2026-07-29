# Bixolon bakery camera evaluator (Windows)

카메라 정지 영상을 현재 RF-DETR-L + RepViT-M1 + 조건부 DINOv3 파이프라인으로
분석하는 Windows 전용 평가 프로토타입이다. 카메라가 준비되고 Python 추론
워커가 모델 로드와 1회 워밍업을 끝낸 뒤에만 `분석하기` 버튼이 활성화된다.

## 다른 PC에 설치

`dist\BixolonBakeryEvaluator-1.0.0-win-x64-setup.exe` 한 파일을 Windows
10/11 x64 PC로 복사해 실행한다. Python, Flutter, Git, 모델 파일 또는 인터넷
연결을 별도로 준비할 필요가 없다. 설치 파일에는 GPU 런타임과 동일 파이프라인의
CPU 폴백이 모두 들어 있으며, NVIDIA GPU와 호환 드라이버가 있으면 `cuda:0`을
자동 선택하고 그렇지 않으면 CPU를 사용한다.

전달 전 함께 생성된 `.sha256` 파일과 해시를 비교한다. 1.0.0 내부 평가 빌드의
SHA-256은
`70f0c12d9ecdf689641d73498d642c9a8caef5e69b5e1e4c099c0dd54d4d8c71`이다.
코드 서명이 없는 내부 테스트 빌드이므로 Windows SmartScreen 안내가 표시될
수 있다. 설치 후 시작 메뉴의 `BIXOLON Bakery AI Evaluator`를 실행한다.

## 실행

저장소와 모델 아티팩트를 그대로 유지한 상태에서 PowerShell을 열고 이 폴더로
이동한다. 현재 PC의 CUDA 지원 Python 환경을 자동 선택 모드로 실행하는 예:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\Run-Camera-Prototype.ps1 `
  -Python C:\workspace\bixolon_bakery_scanner\.venv\Scripts\python.exe
```

포터블 폴더에 CPU 의존성이 설치된 Python을 함께 둔 경우의 예:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\Run-Camera-Prototype.ps1 `
  -Python .\runtime\python\python.exe
```

실행 스크립트는 자신의 위치에서 저장소 루트와 Release EXE를 계산하므로 저장소
폴더 전체를 다른 드라이브로 옮겨도 절대 경로를 수정할 필요가 없다. 단, 전달한
Python에는 이 저장소의 추론 의존성이 설치되어 있어야 하고 모델·정책 파일은
설정에 선언된 SHA-256과 일치해야 한다.

## 평가 화면 사용법

왼쪽 카메라에서 트레이를 확인하고 `분석하기`를 누른다. 결과가 나오면 오른쪽
패널을 위에서 아래로 읽는다.

1. 요약에서 전체 대상, 확정, `알 수 없음`, 버튼 누름부터 화면 표시까지의 시간,
   모델 추론 시간과 실제 사용 장치(CPU/GPU)를 확인한다.
2. 대상별 결과에서 번호, 박스, Top-1 결과와 점수를 확인한다. 화면의 번호 박스와
   결과 행은 서로 선택이 연동된다.
3. `알 수 없음` 대상은 선택한 한 건에 대해서만 Top-3 후보가 펼쳐진다. 후보는
   판단 근거를 확인하기 위한 읽기 전용 정보이며 자동으로 수량에 포함되지 않는다.
4. 확정 수량, 단계별 소요 시간, 모델 정보는 필요할 때만 아래의 접힌 항목을
   펼쳐 확인한다.

목록은 `알 수 없음`을 먼저, 같은 상태에서는 Top-1 점수가 낮은 대상을 먼저
보여준다. 다만 화면과 목록의 대상 번호는 분석 결과 전체에서 고정되어 선택해도
바뀌지 않는다.

## 시간과 결과 해석

첫 실행의 `load_ms`와 `warmup_ms`는 모델을 한 번 올리고 워밍업하는 시작 비용이다.
화면에서 캡처할 때마다 표시되는 worker total과 단계별 시간에는 이 시작 비용이
포함되지 않는다. `버튼 누름 → 결과 표시` 시간은 캡처·IPC·화면 갱신까지 포함하므로
worker total보다 크다.

화면의 점수와 `알 수 없음` Top-3는 한 입력에 대한 모델 관찰값이다. 정답 라벨과
비교한 정확도가 아니며, 라이브 카메라 화면만으로 정확도나 POS 출하 적합성을
판정해서는 안 된다. `알 수 없음`은 등록 SKU로 임의 집계하지 않는다.

## BIXOLON 화면 원칙

평가 화면은 BIXOLON의 산업용 콘솔 톤을 적용한다. 기본 작업 배경은
`#F7F7F5`, 카메라 스테이지와 본문 잉크는 `#171717`, 주요 실행 동작에만
BIXOLON Orange `#EE7203`를 사용한다. 헤더의 BIXOLON 워드마크는 색상이나
형태를 변형하지 않는다. 장식 띠나 불필요한 중첩 카드를 쓰지 않고 1px 구분선,
6px 모서리, 명확한 타이포 계층으로 정보를 구분한다. 화면은 1280×820에서
카메라/결과 패널을 약 64/36으로 배치하고 1024×720에서도 결과 패널 360px를
확보한다.

브랜드 오렌지는 작업과 준비 상태만 나타내며, 분석 결과의 의미색은 보존한다.
확정 SKU와 확정 박스는 청록 `#0E8A72`, `알 수 없음`과 Top-3 후보는 앰버
`#C76B00`, 복구가 필요한 오류는 적색 `#C43A3A`으로 구분한다. 키보드 포커스는
브랜드 상태와 혼동되지 않도록 파랑 `#176BFF` 외곽선으로 표시한다.

## Release 빌드

```powershell
$env:Path = 'C:\workspace\tools\flutter-3.44.7\bin;' + $env:Path
flutter pub get
flutter test
flutter analyze
flutter build windows --release
```

생성 파일은 `build\windows\x64\runner\Release` 아래에 있다. EXE만 단독 복사하지
말고 Release 폴더의 DLL과 `data` 폴더를 함께 보관해야 한다.

## 고정 이미지 warm benchmark

저장소 루트에서 한 워커를 시작해 한 번만 로드·워밍업한 뒤 같은 이미지를 20회
측정한다.

```powershell
$env:PYTHONPATH='src'
python scripts\benchmark_camera_worker.py `
  --repo-root . `
  --device auto `
  --image samples\batch2_e3_m3_h3\g20_b02_e_0301.jpg `
  --runs 20 `
  --output artifacts\evaluations\flutter_camera_prototype_20260729\warm_benchmark.json
```

보고서의 p50/p95는 worker total과 각 단계에 대해 nearest-rank 방식으로 계산된다.
