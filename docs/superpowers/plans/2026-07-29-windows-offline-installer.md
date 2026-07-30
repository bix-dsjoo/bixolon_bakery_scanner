# Windows Offline Evaluator Installer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Python이나 모델을 별도로 설치하지 않은 다른 Windows 10/11 x64 PC에서 설치 EXE 하나로 앱을 설치하고, NVIDIA GPU가 사용 가능하면 GPU를 선택하며 그렇지 않으면 같은 FP32 파이프라인을 CPU로 실행할 수 있게 한다.

**Architecture:** Flutter Release 출력, relocatable CPython 3.11.9, 검증된 CUDA-enabled PyTorch 런타임, 설치된 `bakery_scanner` wheel, worker entrypoint, 설정, 모델, 정책, warm-up 이미지를 하나의 Inno Setup payload로 조립한다. 앱은 개발 환경변수가 있으면 기존 override를 사용하고, 일반 설치에서는 실행 파일 기준 상대경로로 런타임과 pipeline root를 찾는다. 빌드 시 모든 payload 파일의 SHA-256 manifest를 만들고, 설치 후 worker가 기존 모델/정책 SHA 검증과 GPU→CPU fallback을 그대로 수행한다.

**Tech Stack:** Flutter Windows Release, CPython 3.11.9 embeddable x64, PyTorch 2.13.0+cu130, torchvision 0.28.0+cu130, Inno Setup 6.4.3, PowerShell 5.1+, Python manifest tests.

## Global Constraints

- 배포 대상은 Windows 10/11 x64이며 설치 PC에 Python, Flutter, Visual Studio, Git, 네트워크가 없어도 실행 가능해야 한다.
- 설치본에는 Flutter DLL/data, Python runtime, Python dependencies, worker, `bakery_scanner`, configs, RF-DETR-L, RepViT-M1, DINOv3, prototype/local support, fusion policy, calibration, warm-up image를 모두 포함한다.
- CUDA-enabled PyTorch runtime 하나를 포함하며 `torch.cuda.is_available()`와 실제 allocation이 성공할 때만 `cuda:0`을 선택한다. GPU 초기화나 warm-up 실패 시 한 번 CPU로 재시도한다.
- 설치와 실행은 사용자 PC의 전역 Python, `PATH`, 저장소 절대경로에 의존하지 않는다.
- Detector, 분류 정책, 임계값, FP32 설정, 모델 파일, SHA-256 검증, worker JSON 계약을 변경하지 않는다.
- 설치 payload는 `package-manifest.json`에 package-relative path, byte size, SHA-256을 기록한다.
- 설치 중 관리자 권한을 요구하지 않고 기본 경로는 `{localappdata}\Programs\BIXOLON Bakery AI Evaluator`다.
- Flutter 및 Python에 필요한 MSVC x64 runtime DLL은 application-local 방식으로 앱과 embedded Python 옆에 포함한다.
- 내부 테스트 설치본은 Authenticode 미서명으로 명시하고, 설치 EXE의 SHA-256을 별도 파일로 배포한다.
- 모델 로드와 warm-up은 앱 시작 시 한 번 수행하며 같은 앱 세션의 연속 분석에서 반복하지 않는다.
- 설치본 용량과 설치 후 용량은 실제 빌드 결과로 기록하며 추정치를 결과처럼 제시하지 않는다.

---

## File Structure

```text
apps/bakery_camera_flutter/
  lib/main.dart
  lib/src/inference/inference_launch_config.dart
  test/inference/inference_launch_config_test.dart
  windows/runner/Runner.rc
  windows/CMakeLists.txt
  pubspec.yaml
  README.md

deployment/camera_installer/
  BakeryCameraEvaluator.iss       Inno Setup 정의
  runtime-lock.json               검증된 Python/핵심 package/tool 버전
  runtime-requirements-cu130.lock.txt
                                  전체 전이 dependency exact-version lock
  payload-paths.json              source payload allowlist
  README.txt                      설치/첫 실행/CPU·GPU 설명

scripts/
  freeze_camera_runtime_requirements.py
  prepare_camera_installer_runtime.ps1
  build_camera_installer_payload.py
  build_camera_installer.ps1
  verify_camera_installation.py

tests/deployment/
  test_camera_installer_payload.py
  test_camera_installer_manifest.py

dist/
  BixolonBakeryEvaluator-1.0.0-win-x64-setup.exe
  BixolonBakeryEvaluator-1.0.0-win-x64-setup.exe.sha256
  BixolonBakeryEvaluator-1.0.0-build-report.json
```

### Task 1: Resolve an installed package without environment variables

**Files:**
- Modify: `apps/bakery_camera_flutter/lib/src/inference/inference_launch_config.dart`
- Modify: `apps/bakery_camera_flutter/lib/main.dart`
- Modify: `apps/bakery_camera_flutter/test/inference/inference_launch_config_test.dart`

**Interfaces:**
- Produces: `InferenceLaunchConfig.resolve({required Map<String, String> environment, required String executablePath})`.
- Development override requires both `BAKERY_INFERENCE_PYTHON` and `BAKERY_REPO_ROOT`.
- Installed layout resolves `runtime\python\python.exe` and `pipeline` beside the Flutter executable.

- [ ] **Step 1: Write failing launch-resolution tests**

```dart
test('uses installed package layout when overrides are absent', () {
  final config = InferenceLaunchConfig.resolve(
    environment: const {},
    executablePath: r'C:\Program Files\App\bakery_camera_prototype.exe',
  );
  expect(config.pythonExecutable,
      r'C:\Program Files\App\runtime\python\python.exe');
  expect(config.repoRoot, r'C:\Program Files\App\pipeline');
  expect(config.workerScript,
      r'C:\Program Files\App\pipeline\scripts\run_camera_inference_worker.py');
});

test('rejects a partial development override', () {
  expect(
    () => InferenceLaunchConfig.resolve(
      environment: const {'BAKERY_REPO_ROOT': r'C:\repo'},
      executablePath: r'C:\App\app.exe',
    ),
    throwsStateError,
  );
});
```

Keep a third test proving both environment variables preserve the current repository launcher behavior.

- [ ] **Step 2: Run the focused test and verify RED**

Run:

```powershell
$env:Path='C:\workspace\tools\flutter-3.44.7\bin;'+$env:Path
Set-Location apps\bakery_camera_flutter
flutter test test\inference\inference_launch_config_test.dart
```

Expected: FAIL because `resolve` does not exist.

- [ ] **Step 3: Implement deterministic path resolution**

Use `package:path` with `path.Style.windows` or an internal Windows path helper so tests are stable on the build host:

```dart
factory InferenceLaunchConfig.resolve({
  required Map<String, String> environment,
  required String executablePath,
}) {
  final python = environment['BAKERY_INFERENCE_PYTHON']?.trim();
  final root = environment['BAKERY_REPO_ROOT']?.trim();
  if ((python == null || python.isEmpty) != (root == null || root.isEmpty)) {
    throw StateError('개발 실행 경로 두 개를 모두 설정한 뒤 앱을 다시 시작하세요.');
  }
  if (python != null && python.isNotEmpty) {
    return InferenceLaunchConfig._(pythonExecutable: python, repoRoot: root!);
  }
  final appRoot = windowsPath.dirname(executablePath);
  return InferenceLaunchConfig._(
    pythonExecutable:
        windowsPath.join(appRoot, 'runtime', 'python', 'python.exe'),
    repoRoot: windowsPath.join(appRoot, 'pipeline'),
  );
}
```

Add `path: 1.9.1` as a direct dependency, create one
`Context(style: Style.windows)`, and call the resolver from `main.dart` with
`Platform.resolvedExecutable`. Do not search `PATH` or registry.

- [ ] **Step 4: Run config and worker client tests**

Run:

```powershell
flutter test test\inference\inference_launch_config_test.dart test\inference\inference_worker_client_test.dart
```

Expected: PASS.

- [ ] **Step 5: Commit installed-layout resolution**

```powershell
git add apps/bakery_camera_flutter/lib/src/inference/inference_launch_config.dart apps/bakery_camera_flutter/lib/main.dart apps/bakery_camera_flutter/test/inference/inference_launch_config_test.dart apps/bakery_camera_flutter/pubspec.yaml apps/bakery_camera_flutter/pubspec.lock
git commit -m "feat: resolve bundled inference runtime"
```

### Task 2: Build a relocatable validated GPU/CPU Python runtime

**Files:**
- Create: `deployment/camera_installer/runtime-lock.json`
- Create: `deployment/camera_installer/runtime-requirements-cu130.lock.txt`
- Create: `scripts/freeze_camera_runtime_requirements.py`
- Create: `scripts/prepare_camera_installer_runtime.ps1`
- Create: `tests/deployment/test_camera_installer_payload.py`

**Interfaces:**
- `prepare_camera_installer_runtime.ps1 -OutputRoot <new-dir> -WheelCache <dir>` creates `<new-dir>\python\python.exe`.
- The runtime imports `torch`, `torchvision`, `timm`, `rfdetr`, `bakery_scanner`, `PIL`, `numpy`, `yaml`, and `pydantic` without host Python paths.
- The same runtime must import and execute a CPU tensor on a PC without an NVIDIA driver.

- [ ] **Step 1: Add the exact runtime lock**

Record:

```json
{
  "schema_version": 1,
  "python": {
    "version": "3.11.9",
    "url": "https://www.python.org/ftp/python/3.11.9/python-3.11.9-embed-amd64.zip",
    "sha256": "009d6bf7e3b2ddca3d784fa09f90fe54336d5b60f0e0f305c37f400bf83cfd3b"
  },
  "packages": {
    "torch": "2.13.0+cu130",
    "torchvision": "0.28.0+cu130",
    "timm": "1.0.28",
    "rfdetr": "1.8.3",
    "numpy": "2.4.4",
    "Pillow": "12.2.0",
    "PyYAML": "6.0.3",
    "pydantic": "2.13.4",
    "scipy": "1.17.1",
    "scikit-learn": "1.9.0",
    "opencv-python": "5.0.0.93",
    "supervision": "0.29.1",
    "pycocotools": "2.0.11"
  },
  "inno_setup": "6.4.3"
}
```

The Python SHA-256 corresponds to the official 64-bit embeddable file whose published MD5 is `6d9aa08531d48fcc261ba667e2df17c4`.

- [ ] **Step 2: Generate and review the complete dependency closure**

`freeze_camera_runtime_requirements.py` starts from these normalized roots:

```python
ROOTS = {
    "torch", "torchvision", "timm", "rfdetr", "numpy", "Pillow",
    "PyYAML", "pydantic", "scipy", "scikit-learn", "opencv-python",
    "supervision", "pycocotools",
}
```

It recursively follows `importlib.metadata.requires`, evaluates markers for
CPython 3.11 on Windows x64, rejects editable/VCS/local-path requirements,
normalizes distribution names, and writes every reachable distribution once
as `name==exact-version` sorted by normalized name. Generate the committed
lock from the validated runtime:

```powershell
C:\Users\OMEN\AppData\Local\Programs\Python\Python311\python.exe `
  scripts\freeze_camera_runtime_requirements.py `
  --runtime-lock deployment\camera_installer\runtime-lock.json `
  --output deployment\camera_installer\runtime-requirements-cu130.lock.txt
```

The script fails if any root version differs from `runtime-lock.json` or the
closure contains an unpinned requirement.

- [ ] **Step 3: Write failing runtime-layout tests**

Test rejects:

- a Python version other than 3.11.9;
- missing `python311._pth` `import site`;
- a package version mismatch;
- site-packages containing `.pth` entries with absolute build-PC paths;
- missing CPU tensor execution;
- missing `bakery_scanner` wheel metadata.

- [ ] **Step 4: Run the deployment test and verify RED**

Run:

```powershell
$env:PYTHONPATH='src'
C:\Users\OMEN\AppData\Local\Programs\Python\Python311\python.exe -m pytest -q tests\deployment\test_camera_installer_payload.py
```

Expected: FAIL because runtime preparation does not exist.

- [ ] **Step 5: Implement runtime preparation**

The PowerShell script must:

1. refuse an existing output directory;
2. download the pinned embeddable ZIP only when absent from `-WheelCache`;
3. verify SHA-256 before extraction;
4. enable `import site` and add `Lib\site-packages` in `python311._pth`;
5. bootstrap pinned pip into the staging runtime;
6. download the committed lock into `-WheelCache` from the official CUDA 13.0 PyTorch index plus PyPI, then install with `--no-index --find-links <WheelCache> --no-deps -r runtime-requirements-cu130.lock.txt`;
7. build `bixolon_bakery_scanner-0.1.0-py3-none-any.whl` and install it with `--no-deps`;
8. reject editable installs, absolute `.pth` files, pip cache, `__pycache__`, tests, and build metadata not required at runtime;
9. run version/import/CPU tensor checks with the staged `python.exe`;
10. write `runtime-manifest.json` with every runtime file size and SHA-256.

Use a staging directory beside `-OutputRoot`, rename only after every verification passes, and clean only that exact staging path on failure.

- [ ] **Step 6: Build and verify the prepared runtime**

Run:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts\prepare_camera_installer_runtime.ps1 `
  -OutputRoot artifacts\installer_runtime\cu130 `
  -WheelCache artifacts\installer_wheel_cache
```

Then:

```powershell
artifacts\installer_runtime\cu130\python\python.exe -c "import torch; print(torch.__version__, torch.version.cuda); print(torch.ones(1, device='cpu'))"
```

Expected: `2.13.0+cu130`, CUDA runtime `13.0`, and a CPU tensor. CUDA availability may be true or false depending on the build PC, but import and CPU execution must always work.

- [ ] **Step 7: Commit runtime tooling**

Do not commit the multi-gigabyte generated runtime or wheel cache.

```powershell
git add deployment/camera_installer/runtime-lock.json deployment/camera_installer/runtime-requirements-cu130.lock.txt scripts/freeze_camera_runtime_requirements.py scripts/prepare_camera_installer_runtime.ps1 tests/deployment/test_camera_installer_payload.py
git commit -m "build: prepare bundled camera runtime"
```

### Task 3: Assemble and hash the exact application payload

**Files:**
- Create: `deployment/camera_installer/payload-paths.json`
- Create: `scripts/build_camera_installer_payload.py`
- Create: `scripts/verify_camera_installation.py`
- Create: `tests/deployment/test_camera_installer_manifest.py`

**Interfaces:**
- `build_camera_installer_payload.py --release-dir <dir> --runtime-root <dir> --output <new-dir> --vc-runtime-dir <dir>` creates the exact Inno source tree.
- `verify_camera_installation.py --root <payload-or-installed-root> [--launch-worker-smoke]` verifies manifest and optional real worker startup.
- Output layout:

```text
payload\
  bakery_camera_prototype.exe
  flutter_windows.dll
  camera_windows_plugin.dll
  data\
  msvcp140.dll
  vcruntime140.dll
  vcruntime140_1.dll
  runtime\python\
  pipeline\scripts\run_camera_inference_worker.py
  pipeline\configs\
  pipeline\models\
  pipeline\artifacts\e2e_current_source\classification\
  pipeline\samples\batch2_e3_m3_h3\g20_b02_e_0301.jpg
  package-manifest.json
  README.txt
```

- [ ] **Step 1: Define the source allowlist**

`payload-paths.json` must explicitly include:

- both `configs/gpu_rfdetr_classifier_policy.yaml` and `configs/cpu_rfdetr_classifier_policy.yaml`;
- `models/rfdetr_large_bakery_v1/{checkpoint.pth,calibration_corrected_gt_299_fp0_20260729.json,manifest.json}`;
- `models/repvit_m1_15plus5_v1/{repvit_m1_15plus5_v1.pt,repvit_m1_15plus5_v1.manifest.json}`;
- `models/dinov3_vits16_15plus5_v1/{dinov3_vits16_pretrain_lvd1689m-08c60483.pth,dinov3_vits16_15plus5_v1_support.pt}`;
- the four classifier artifacts referenced by both configs;
- worker entrypoint and warm-up image.

Resolve config references and detector manifest references programmatically and fail when the explicit allowlist differs from the referenced set.

- [ ] **Step 2: Write failing manifest tests**

Create temporary fake Release/runtime/pipeline trees and verify:

```python
assert manifest["schema_version"] == 1
assert manifest["app_version"] == "1.0.0"
assert manifest["files"]["pipeline/configs/gpu_rfdetr_classifier_policy.yaml"]["sha256"]
assert not any(Path(path).is_absolute() for path in manifest["files"])
```

Reject a missing model, hash mismatch, existing output, symlink/reparse point, path outside repository root, host Python path, and undeclared file.

- [ ] **Step 3: Run manifest tests and verify RED**

Run:

```powershell
C:\Users\OMEN\AppData\Local\Programs\Python\Python311\python.exe -m pytest -q tests\deployment\test_camera_installer_manifest.py
```

Expected: FAIL because the payload builder and verifier do not exist.

- [ ] **Step 4: Implement transactional payload assembly**

The builder copies the complete Flutter Release directory, prepared runtime, explicit pipeline allowlist, and three application-local MSVC DLLs. It writes a sorted manifest:

```json
{
  "schema_version": 1,
  "app_version": "1.0.0",
  "architecture": "windows-x64",
  "runtime_profile": "python311-torch213-cu130-cpu-fallback",
  "files": {
    "bakery_camera_prototype.exe": {
      "bytes": 123,
      "sha256": "64 lowercase hex characters"
    }
  }
}
```

The verifier recalculates every hash, reports extra/missing files, checks model/config internal SHA references, imports the bundled runtime, and optionally starts the worker until `ready` then sends `shutdown`.

- [ ] **Step 5: Build and verify a real payload**

Run from repository root:

```powershell
$env:Path='C:\workspace\tools\flutter-3.44.7\bin;'+$env:Path
Set-Location apps\bakery_camera_flutter
flutter build windows --release
Set-Location ..\..
C:\Users\OMEN\AppData\Local\Programs\Python\Python311\python.exe scripts\build_camera_installer_payload.py `
  --release-dir apps\bakery_camera_flutter\build\windows\x64\runner\Release `
  --runtime-root artifacts\installer_runtime\cu130 `
  --vc-runtime-dir "$env:VCToolsRedistDir\x64\Microsoft.VC143.CRT" `
  --output artifacts\installer_payload\1.0.0
C:\Users\OMEN\AppData\Local\Programs\Python\Python311\python.exe scripts\verify_camera_installation.py `
  --root artifacts\installer_payload\1.0.0 `
  --launch-worker-smoke
```

Expected: all hashes pass and the worker reaches `ready` once.

- [ ] **Step 6: Commit payload tooling**

```powershell
git add deployment/camera_installer/payload-paths.json scripts/build_camera_installer_payload.py scripts/verify_camera_installation.py tests/deployment/test_camera_installer_manifest.py
git commit -m "build: assemble evaluator installer payload"
```

### Task 4: Create the per-user Inno Setup installer

**Files:**
- Create: `deployment/camera_installer/BakeryCameraEvaluator.iss`
- Create: `deployment/camera_installer/README.txt`
- Create: `scripts/build_camera_installer.ps1`
- Modify: `apps/bakery_camera_flutter/windows/runner/Runner.rc`
- Modify: `apps/bakery_camera_flutter/windows/CMakeLists.txt`
- Modify: `apps/bakery_camera_flutter/pubspec.yaml`

**Interfaces:**
- `build_camera_installer.ps1 -PayloadRoot <verified-dir> -IsccPath <ISCC.exe> -Version 1.0.0 -OutputDir <new-dir>` creates setup EXE, SHA file, and build report.
- Inno defines a stable AppId and supports install, repair/upgrade, and uninstall.

- [ ] **Step 1: Set product identity and version consistently**

Use:

```text
ProductName: BIXOLON Bakery AI Evaluator
Publisher: BIXOLON
Version: 1.0.0
Architecture: x64
Executable: bakery_camera_prototype.exe
```

Set Flutter `version: 1.0.0+1`, Windows `ProductName`, `FileDescription`, and `CompanyName` to the same identity. Keep the on-disk executable name stable to avoid breaking launch paths.

- [ ] **Step 2: Implement the Inno definition**

Required setup properties:

```ini
[Setup]
AppId={{E6B7A8D8-CE4D-4B3D-9B48-7A27279140B2}
AppName=BIXOLON Bakery AI Evaluator
AppVersion={#AppVersion}
DefaultDirName={localappdata}\Programs\BIXOLON Bakery AI Evaluator
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
Compression=lzma2/ultra64
SolidCompression=yes
UninstallDisplayIcon={app}\bakery_camera_prototype.exe
```

Copy the verified payload recursively, create a Start Menu shortcut, offer an unchecked desktop shortcut, and offer `BIXOLON Bakery AI Evaluator 실행` on the final page. Do not add launch arguments or environment variables.

- [ ] **Step 3: Implement the installer build wrapper**

The PowerShell wrapper must:

1. require Inno Setup 6.4.3 `ISCC.exe`;
2. reject an unverified or existing output directory;
3. run `verify_camera_installation.py` before compilation;
4. compile with `/DAppVersion=1.0.0`, `/DPayloadRoot=<absolute path>`, `/O<output>`;
5. verify compiler exit code 0;
6. calculate setup EXE SHA-256;
7. write UTF-8 `.sha256` and build report containing payload bytes, installer bytes, installed bytes, compression ratio, manifest hash, git commit, build timestamp, and unsigned status.

- [ ] **Step 4: Compile the installer**

Run:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts\build_camera_installer.ps1 `
  -PayloadRoot artifacts\installer_payload\1.0.0 `
  -IsccPath 'C:\Program Files (x86)\Inno Setup 6\ISCC.exe' `
  -Version 1.0.0 `
  -OutputDir dist
```

Expected:

```text
dist\BixolonBakeryEvaluator-1.0.0-win-x64-setup.exe
dist\BixolonBakeryEvaluator-1.0.0-win-x64-setup.exe.sha256
dist\BixolonBakeryEvaluator-1.0.0-build-report.json
```

- [ ] **Step 5: Verify silent install and uninstall in an isolated target directory**

Run:

```powershell
dist\BixolonBakeryEvaluator-1.0.0-win-x64-setup.exe /VERYSILENT /SUPPRESSMSGBOXES /NORESTART /DIR="$env:LOCALAPPDATA\Programs\BIXOLON Bakery AI Evaluator Test"
& "$env:LOCALAPPDATA\Programs\BIXOLON Bakery AI Evaluator Test\runtime\python\python.exe" `
  "$env:LOCALAPPDATA\Programs\BIXOLON Bakery AI Evaluator Test\pipeline\scripts\run_camera_inference_worker.py" `
  --repo-root "$env:LOCALAPPDATA\Programs\BIXOLON Bakery AI Evaluator Test\pipeline" `
  --device cpu `
  --warmup-image "$env:LOCALAPPDATA\Programs\BIXOLON Bakery AI Evaluator Test\pipeline\samples\batch2_e3_m3_h3\g20_b02_e_0301.jpg"
```

Use the JSON Lines protocol to wait for `ready`, send `shutdown`, then run the generated uninstaller with `/VERYSILENT /NORESTART`. Verify the exact test install directory is removed and no repository/model files are touched.

- [ ] **Step 6: Commit installer definition**

Do not commit `dist`, payload, runtime, or wheel cache.

```powershell
git add deployment/camera_installer/BakeryCameraEvaluator.iss deployment/camera_installer/README.txt scripts/build_camera_installer.ps1 apps/bakery_camera_flutter/windows/runner/Runner.rc apps/bakery_camera_flutter/windows/CMakeLists.txt apps/bakery_camera_flutter/pubspec.yaml
git commit -m "build: add Windows evaluator installer"
```

### Task 5: Clean-PC GPU and CPU acceptance

**Files:**
- Modify: `apps/bakery_camera_flutter/README.md`
- Create: `docs/deployment/windows-installer-test-matrix.md`
- Create: `artifacts/installer_validation/validation-report.json`

**Interfaces:**
- Consumes: setup EXE and SHA-256.
- Produces: external-PC evidence for CPU and GPU, plus end-user instructions.

- [ ] **Step 1: Verify installer hash before transfer**

Run:

```powershell
Get-FileHash -Algorithm SHA256 -LiteralPath dist\BixolonBakeryEvaluator-1.0.0-win-x64-setup.exe
Get-Content -LiteralPath dist\BixolonBakeryEvaluator-1.0.0-win-x64-setup.exe.sha256
```

Expected: hashes match exactly.

- [ ] **Step 2: Test the CPU-only clean machine**

Use Windows 10/11 x64 with no Python, Flutter, Visual Studio, Git, or NVIDIA driver. Disconnect network after copying the installer. Verify:

1. per-user install succeeds;
2. app starts from Start Menu;
3. camera preview opens;
4. status reports `CPU`;
5. model load and warm-up complete;
6. two consecutive analyses complete;
7. second analysis does not reload models;
8. boxes, labels, `알 수 없음`, Top-3, path, and timings render;
9. uninstall succeeds.

Record OS build, CPU, RAM, camera, load/warm-up, first and second press-to-render, worker total, and any failure code.

- [ ] **Step 3: Test the NVIDIA GPU clean machine**

Use Windows 10/11 x64 with a driver compatible with CUDA 13.0 and no developer tools. Verify the same checklist plus:

```text
device = cuda:0
fallback_reason = null
```

Record GPU and driver version, load/warm-up, warm worker p50/p95 over at least 20 analyses, and press-to-render for two real-camera captures.

- [ ] **Step 4: Test forced fallback evidence**

On the CPU machine, or with CUDA hidden in a controlled test, verify:

```text
device = cpu
fallback_reason = cuda_unavailable
```

On the GPU machine, use the existing injected runtime test to prove `cuda_load_failed` and `cuda_warmup_failed` each cause one CPU retry and never a mid-request device switch.

- [ ] **Step 5: Write the validation report**

`validation-report.json` includes:

```json
{
  "installer_sha256": "64 lowercase hex characters",
  "installer_bytes": 0,
  "installed_bytes": 0,
  "unsigned_internal_test_build": true,
  "cpu_machine": {
    "device": "cpu",
    "two_scans_without_reload": true
  },
  "gpu_machine": {
    "device": "cuda:0",
    "two_scans_without_reload": true,
    "warm_worker_p50_ms": 0,
    "warm_worker_p95_ms": 0
  }
}
```

Replace numeric zero examples with measured values when writing the report; reject the report schema if a measured field is zero or absent.

- [ ] **Step 6: Update installation documentation**

Document:

- installer hash verification;
- double-click installation and Start Menu launch;
- expected first-start load/warm-up delay;
- GPU automatic selection and CPU fallback;
- `알 수 없음`/Top-3/score interpretation;
- camera reconnect and model preparation failure actions;
- unsigned internal build/SmartScreen expectation;
- uninstall path;
- actual installer and installed sizes from the build report.

- [ ] **Step 7: Run the final local suite**

Run:

```powershell
$env:PYTHONPATH='src'
C:\Users\OMEN\AppData\Local\Programs\Python\Python311\python.exe -m pytest -q tests\prototype tests\deployment
$env:Path='C:\workspace\tools\flutter-3.44.7\bin;'+$env:Path
Set-Location apps\bakery_camera_flutter
flutter test
flutter analyze
flutter build windows --release
```

Expected: all Python and Flutter tests pass, analyzer is clean, Windows Release build succeeds.

- [ ] **Step 8: Commit validated deployment documentation**

```powershell
git add apps/bakery_camera_flutter/README.md docs/deployment/windows-installer-test-matrix.md artifacts/installer_validation/validation-report.json
git commit -m "docs: validate evaluator installer"
```

## Self-Review

- Spec coverage: Task 1 removes environment-variable dependency. Task 2 creates one relocatable CUDA runtime that executes on CPU. Task 3 bundles every required app, runtime, model, policy, and warm-up asset with SHA-256. Task 4 produces install/upgrade/uninstall behavior. Task 5 proves clean-PC CPU and GPU operation.
- Reproducibility: Python URL/SHA, package versions, Inno version, app version, payload manifest, model/policy hashes, git commit, installer hash, and measured sizes are recorded.
- Pipeline boundary: the same worker, FP32 configs, detector threshold, fusion policy, model artifacts, and GPU→CPU initialization behavior are packaged without inference changes.
- External-PC usability: no Python, PowerShell command, repository checkout, `PATH`, or network is required after the installer is copied.
- Safety: per-user installation avoids elevation; payload assembly refuses existing destinations and reparse points; uninstall is tested only against the exact installer-created target.
- Release honesty: the internal installer is explicitly unsigned and its SHA-256 is distributed; CPU timing is not represented as the RTX 5080 release gate.
