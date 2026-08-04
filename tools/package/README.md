# 패키징 도구

`Build-Latest-DoubleClick.ps1`은 최신 Flutter Release를 빌드해 두 가지 배포 경로를 생성합니다.

- `<OutputRoot>\portable\bakery_camera_prototype.exe`: 폴더를 복사한 뒤 이 파일을 더블클릭하여 바로 실행합니다.
- `<OutputRoot>\installer\BixolonBakeryEvaluator-<Version>-win-x64-setup.exe`: 시작 메뉴와 선택적 바탕 화면 바로가기를 설치합니다.

```powershell
tools\package\Build-Latest-DoubleClick.ps1 `
  -RuntimeRoot C:\path\to\approved\runtime `
  -IsccPath 'C:\Program Files (x86)\Inno Setup 6\ISCC.exe' `
  -OutputRoot C:\releases\BixolonBakeryEvaluator-1.1.0
```

이 명령은 휴대용 패키지의 해시와 내장 모델·정책·워커 소스를 검증하고 워커 기동 검사까지 통과한 뒤 설치 관리자를 만듭니다. 생성물은 외부 아티팩트이며 Git에 추가하지 않습니다.
