# 최신 더블클릭 배포 설계

## 목적

최신 커밋의 BIXOLON Bakery AI Evaluator를 개발 환경 변수, Git, Flutter,
별도 Python 설치 없이 실행한다. 사용자는 무설치 배포 폴더의 EXE, 또는
설치 후 생성된 시작 메뉴/바탕화면 바로가기를 더블클릭해 같은 앱을 시작한다.

## 산출물

1. 휴대용 배포 폴더
   `bakery_camera_prototype.exe`, Flutter DLL/자산, 내장 Python 런타임,
   `pipeline/`, 모델, 정책, 패키지 manifest를 함께 포함한다.
2. Inno Setup 설치 프로그램
   동일한 휴대용 배포 폴더를 설치하고 시작 메뉴와 바탕화면 바로가기를
   생성한다.

앱 버전은 `1.1.0`을 유지한다. 패키지 manifest와 워커 시작 provenance에는
빌드한 Git 커밋과 코드 identity SHA-256을 기록한다.

## 실행과 무결성

배포된 워커는 개발 checkout을 복사하거나 Git 상태를 요구하지 않는다.
대신 패키지 생성 단계가 `pipeline/worker-identity.json`에 다음 값을 기록한다.

- Git 커밋
- `src`, `dino`, `data`, `configs`, `policies` 및 필수 엔트리 파일의
  SHA-256 기반 코드 identity

배포 워커는 이 파일을 읽어 패키지 내부 pipeline의 실제 코드 identity와
비교한다. 불일치, 누락, 잘못된 JSON은 fail-closed로 `fatal` 이벤트를 낸다.
검증에 성공하면 패키지 내부 source를 직접 로드하고 기존 모델/정책 SHA-256
검증을 그대로 적용한다. 개발 checkout 실행은 현재의 clean-Git-snapshot
규칙을 유지한다.

## 패키징 흐름

1. 최신 Flutter Windows Release를 빌드한다.
2. 패키지 빌더가 release, 고정 Python runtime, 허용된 pipeline 입력,
   VC runtime을 새 staging 폴더로 복사한다.
3. 빌더가 staging pipeline에서 worker identity를 계산하고
   `worker-identity.json`을 기록한다.
4. 전체 패키지 SHA-256 manifest를 작성한다.
5. 같은 폴더를 Inno Setup 입력으로 사용한다.

패키지 빌더는 선택한 attested 입력에 추적된 수정이 있으면 중단한다.
선택 범위 밖의 사용자 데이터나 문서는 배포물에 포함하지 않으며, 패키징을
막지 않는다.

## 검증

- 단위: deployment identity metadata의 생성, 누락/변조 거부,
  개발 checkout 경로 보존.
- 패키지: 기존 전체 package manifest 및 내장 runtime 검증.
- 실행: 환경 변수 없이 휴대용 EXE를 시작해 워커 `ready`와 provenance를
  확인한다.
- 설치: 설치 후 생성된 시작 메뉴/바탕화면 바로가기가 같은 휴대용 payload를
  시작하는지 확인한다.

## 비범위

- 모델, 정책, SKU 결정 규칙의 변경
- 카메라/결제 기능 변경
- Git LFS 또는 외부 모델 저장소 정책 변경
