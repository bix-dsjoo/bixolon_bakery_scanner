# 최신 더블클릭 배포 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 최신 BIXOLON Bakery AI Evaluator를 Git·환경 변수·별도 런타임 없이 휴대용 폴더 EXE와 설치 후 바로가기에서 더블클릭으로 실행한다.

**Architecture:** 패키지 빌더는 허용된 `pipeline/`을 복사한 뒤 그 코드 바이트와 Git commit을 `worker-identity.json`으로 고정한다. 워커는 identity가 있는 배포 pipeline에서 현재 바이트를 재해시해 검증한 뒤 직접 로드하고, identity가 없는 개발 checkout에서는 기존 clean-Git snapshot 흐름을 유지한다. 휴대용 payload는 Inno Setup의 단일 입력으로도 사용한다.

**Tech Stack:** Python 3.11, pytest, Flutter Windows, PowerShell, Inno Setup 6.4.3, SHA-256.

## Global Constraints

- 앱 버전은 `1.1.0`을 유지하고 worker provenance에는 Git commit과 코드 identity SHA-256을 포함한다.
- 모델, 정책, SKU 결정 규칙은 변경하지 않는다.
- 배포 worker는 Git 또는 개발 환경 변수에 의존하지 않으며 identity 누락·변조·불일치는 fail-closed `fatal`로 처리한다.
- 개발 checkout은 clean-Git snapshot을 계속 요구한다.
- 새 운영 도구는 `tools/package/`에 두고, 기존 `scripts/` 호환 동작을 바꾸지 않는다.
- 전체 payload manifest, 모델/정책 해시, runtime lock 검증이 모두 통과한 산출물만 실행·설치 검증한다.

---

## File Structure

- Modify: `scripts/run_camera_inference_worker.py` — deployment identity를 검증하고 packaged pipeline을 직접 실행한다.
- Modify: `scripts/build_camera_installer_payload.py` — staging `pipeline/worker-identity.json`을 package manifest 전에 생성한다.
- Modify: `scripts/verify_camera_installation.py` — worker identity를 package 검증 항목으로 추가한다.
- Modify: `tests/prototype/test_camera_worker_snapshot.py` — 개발 snapshot 보존과 deployment identity를 검증한다.
- Modify: `tests/deployment/test_camera_installer_payload.py` — payload identity 생성과 운영 명령 계약을 검증한다.
- Modify: `tests/deployment/test_camera_installer_manifest.py` — metadata 포함과 변조 거부를 검증한다.
- Create: `tools/package/Build-Latest-DoubleClick.ps1` — 최신 Flutter Release, 휴대용 payload, installer를 순서대로 만든다.
- Modify: `tools/package/README.md`, `deployment/camera_installer/README.txt` — 더블클릭 배포 절차를 문서화한다.

### Task 1: 배포 pipeline identity 계약

**Files:**
- Modify: `scripts/run_camera_inference_worker.py`
- Modify: `tests/prototype/test_camera_worker_snapshot.py`

**Interfaces:**
- Produces: `load_deployed_worker_identity(root: Path) -> dict[str, str] | None`
- Produces: `resolve_worker_execution_root(repo_root: Path, temporary_root: Path) -> tuple[Path, dict[str, str]]`
- Consumes: `compute_worker_code_identity(root: Path, *, commit: str) -> dict[str, str]`
- Contract: `pipeline/worker-identity.json` has exactly `schema_version`, `code_commit`, `code_identity_sha256`; schema is `1`, commit is 40 lowercase hex, identity is 64 lowercase hex.

- [ ] **Step 1: Write failing deployment identity tests**

```python
def test_deployed_identity_uses_packaged_root_without_git(tmp_path: Path) -> None:
    root = _attested_pipeline(tmp_path / "pipeline")
    identity = compute_worker_code_identity(root, commit="a" * 40)
    _write_identity(root, identity)

    execution_root, actual = resolve_worker_execution_root(root, tmp_path / "temporary")

    assert execution_root == root.resolve()
    assert actual == identity


def test_deployed_identity_rejects_tampered_attested_source(tmp_path: Path) -> None:
    root = _attested_pipeline(tmp_path / "pipeline")
    _write_identity(root, compute_worker_code_identity(root, commit="a" * 40))
    _write(root / "src" / "bakery_scanner" / "module.py", "VALUE = 'changed'\n")

    with pytest.raises(ValueError, match="deployed worker code identity does not match"):
        resolve_worker_execution_root(root, tmp_path / "temporary")
```

- [ ] **Step 2: Run test to verify failure**

Run: `python -m pytest tests/prototype/test_camera_worker_snapshot.py -k deployed_identity -q`

Expected: FAIL because `resolve_worker_execution_root` does not exist.

- [ ] **Step 3: Implement exact metadata parsing and root selection**

```python
_DEPLOYED_IDENTITY_FILE = "worker-identity.json"

def load_deployed_worker_identity(root: Path) -> dict[str, str] | None:
    path = root.resolve() / _DEPLOYED_IDENTITY_FILE
    if not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    if set(payload) != {"schema_version", "code_commit", "code_identity_sha256"}:
        raise ValueError("deployed worker identity schema is invalid")
    if payload["schema_version"] != 1:
        raise ValueError("deployed worker identity schema_version is invalid")
    identity = {"code_commit": payload["code_commit"], "code_identity_sha256": payload["code_identity_sha256"]}
    _validate_worker_identity(identity)
    return identity

def resolve_worker_execution_root(repo_root: Path, temporary_root: Path) -> tuple[Path, dict[str, str]]:
    root = repo_root.resolve()
    expected = load_deployed_worker_identity(root)
    if expected is None:
        return _capture_child_snapshot(root, temporary_root / "checkout")
    actual = compute_worker_code_identity(root, commit=expected["code_commit"])
    if actual != expected:
        raise ValueError("deployed worker code identity does not match")
    return root, actual
```

Use `resolve_worker_execution_root()` in `main()` before imports and retain `artifact_root=root` for packaged artifact paths.

- [ ] **Step 4: Run regression tests**

Run: `python -m pytest tests/prototype/test_camera_worker_snapshot.py tests/prototype/test_camera_worker.py -q`

Expected: PASS; metadata accepts exact bytes, rejects source mutation, and metadata-free development execution still stages a snapshot.

- [ ] **Step 5: Commit**

```powershell
git add scripts/run_camera_inference_worker.py tests/prototype/test_camera_worker_snapshot.py
git commit -m "feat(deployment): 배포 워커 코드 식별 검증 추가"
```

### Task 2: payload 생성 시 identity 기록과 attested 입력 검증

**Files:**
- Modify: `scripts/build_camera_installer_payload.py`
- Modify: `tests/deployment/test_camera_installer_payload.py`
- Modify: `tests/deployment/test_camera_installer_manifest.py`

**Interfaces:**
- Produces: `build_worker_identity(repo_root: Path, pipeline_root: Path) -> dict[str, object]`
- Consumes: `compute_worker_code_identity(pipeline_root, commit=commit)` from Task 1.
- Contract: selected `_ATTESTED_TREES` and `_ATTESTED_FILES` must have no tracked Git diff; untracked files and paths outside that set do not block packaging.

- [ ] **Step 1: Write failing payload tests**

```python
def test_payload_writes_worker_identity_before_package_manifest(payload_root: Path) -> None:
    identity = json.loads((payload_root / "pipeline" / "worker-identity.json").read_text(encoding="utf-8"))
    manifest = _load_payload_manifest(payload_root)

    assert identity["schema_version"] == 1
    assert len(identity["code_commit"]) == 40
    assert len(identity["code_identity_sha256"]) == 64
    assert "pipeline/worker-identity.json" in manifest["files"]


def test_build_worker_identity_rejects_modified_attested_input(tmp_path: Path, monkeypatch) -> None:
    repo = _attested_repo(tmp_path / "repo")
    monkeypatch.setattr(payload_module, "_git_diff_is_clean", lambda *_args: False)

    with pytest.raises(ValueError, match="attested inputs must be clean"):
        build_worker_identity(repo, repo)
```

- [ ] **Step 2: Run test to verify failure**

Run: `python -m pytest tests/deployment/test_camera_installer_payload.py tests/deployment/test_camera_installer_manifest.py -q`

Expected: FAIL because the builder has no worker identity output or tracked-input guard.

- [ ] **Step 3: Implement identity creation before the package manifest**

```python
def build_worker_identity(repo_root: Path, pipeline_root: Path) -> dict[str, object]:
    commit = _git_head(repo_root)
    if not _git_diff_is_clean(repo_root, _ATTESTED_TREES + _ATTESTED_FILES):
        raise ValueError("attested inputs must be clean before packaging")
    identity = compute_worker_code_identity(pipeline_root, commit=commit)
    return {"schema_version": 1, **identity}

# in assemble_payload(), after all pipeline inputs are copied:
identity = build_worker_identity(repo_root, staging / "pipeline")
(staging / "pipeline" / "worker-identity.json").write_text(
    json.dumps(identity, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8"
)
manifest = build_package_manifest(staging, app_version=app_version)
```

- [ ] **Step 4: Run payload tests**

Run: `python -m pytest tests/deployment/test_camera_installer_payload.py tests/deployment/test_camera_installer_manifest.py -q`

Expected: PASS; metadata is present before manifest creation and selected tracked changes prevent payload creation.

- [ ] **Step 5: Commit**

```powershell
git add scripts/build_camera_installer_payload.py tests/deployment/test_camera_installer_payload.py tests/deployment/test_camera_installer_manifest.py
git commit -m "feat(package): 배포 워커 식별 메타데이터 기록"
```

### Task 3: 설치 검증기에 worker identity 검사 추가

**Files:**
- Modify: `scripts/verify_camera_installation.py`
- Modify: `tests/deployment/test_camera_installer_manifest.py`

**Interfaces:**
- Produces: `verify_deployed_worker_identity(root: Path) -> dict[str, str]`
- Consumes: `load_deployed_worker_identity`, `compute_worker_code_identity` from Task 1.
- Contract: identity 누락 또는 current pipeline identity 불일치는 worker smoke 전에 실패한다.

- [ ] **Step 1: Write failing verifier tests**

```python
def test_payload_verifier_rejects_tampered_attested_worker_source(payload_root: Path) -> None:
    source = payload_root / "pipeline" / "src" / "bakery_scanner" / "module.py"
    source.write_text("tampered\n", encoding="utf-8")

    with pytest.raises(ValueError, match="deployed worker code identity does not match"):
        verify_deployed_worker_identity(payload_root)


def test_payload_verifier_rejects_missing_worker_identity(payload_root: Path) -> None:
    (payload_root / "pipeline" / "worker-identity.json").unlink()

    with pytest.raises(ValueError, match="worker identity is missing"):
        verify_deployed_worker_identity(payload_root)
```

- [ ] **Step 2: Run test to verify failure**

Run: `python -m pytest tests/deployment/test_camera_installer_manifest.py -k worker_identity -q`

Expected: FAIL because `verify_deployed_worker_identity` does not exist.

- [ ] **Step 3: Implement verification and CLI result provenance**

```python
def verify_deployed_worker_identity(root: Path) -> dict[str, str]:
    pipeline = root.resolve() / "pipeline"
    identity = load_deployed_worker_identity(pipeline)
    if identity is None:
        raise ValueError("worker identity is missing")
    actual = compute_worker_code_identity(pipeline, commit=identity["code_commit"])
    if actual != identity:
        raise ValueError("deployed worker code identity does not match")
    return identity

# after verify_internal_artifact_hashes(root):
result["worker_identity"] = verify_deployed_worker_identity(args.root)
```

- [ ] **Step 4: Run package verification tests**

Run: `python -m pytest tests/deployment/test_camera_installer_manifest.py tests/deployment/test_camera_installer_payload.py -q`

Expected: PASS; package manifest, model/policy files, and worker code all reject tampering.

- [ ] **Step 5: Commit**

```powershell
git add scripts/verify_camera_installation.py tests/deployment/test_camera_installer_manifest.py
git commit -m "fix(deployment): 패키지 워커 코드 변조 차단"
```

### Task 4: 휴대용·설치형 최신 빌드 운영 명령

**Files:**
- Create: `tools/package/Build-Latest-DoubleClick.ps1`
- Modify: `tools/package/README.md`
- Modify: `deployment/camera_installer/README.txt`
- Modify: `tests/deployment/test_camera_installer_payload.py`

**Interfaces:**
- Produces: `<OutputRoot>/portable/` and `<OutputRoot>/installer/BixolonBakeryEvaluator-1.1.0-win-x64-setup.exe`.
- Consumes: Flutter release build, payload builder, payload verifier, and existing `scripts/build_camera_installer.ps1`.
- Parameters: required `-RuntimeRoot`, `-IsccPath`, `-OutputRoot`; optional `-FlutterPath`, `-Python`, `-Version '1.1.0'`.

- [ ] **Step 1: Write failing command and documentation tests**

```python
def test_latest_double_click_builder_creates_both_distribution_routes() -> None:
    script = REPO_ROOT / "tools" / "package" / "Build-Latest-DoubleClick.ps1"
    source = script.read_text(encoding="utf-8")

    assert "RuntimeRoot" in source
    assert "IsccPath" in source
    assert "flutter.bat" in source
    assert "verify_camera_installation.py" in source
    assert "build_camera_installer.ps1" in source
    assert "portable" in source
```

Assert in the same test that both package README files contain `bakery_camera_prototype.exe` and `바로가기`.

- [ ] **Step 2: Run test to verify failure**

Run: `python -m pytest tests/deployment/test_camera_installer_payload.py -k latest_double_click -q`

Expected: FAIL because `tools/package/Build-Latest-DoubleClick.ps1` does not exist.

- [ ] **Step 3: Implement orchestration and direct-launch documentation**

```powershell
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$RuntimeRoot,
    [Parameter(Mandatory = $true)][string]$IsccPath,
    [Parameter(Mandatory = $true)][string]$OutputRoot,
    [string]$FlutterPath = 'C:\workspace\tools\flutter-3.44.7\bin\flutter.bat',
    [string]$Python = 'C:\Users\OMEN\AppData\Local\Programs\Python\Python311\python.exe',
    [ValidatePattern('^\d+\.\d+\.\d+$')][string]$Version = '1.1.0'
)

# Resolve absolute paths; reject existing OutputRoot; run Flutter release build;
# create OutputRoot\portable via the Python payload builder; run the verifier
# with --launch-worker-smoke; then invoke the existing installer builder with
# PayloadRoot=OutputRoot\portable and OutputDir=OutputRoot\installer.
```

Use `Set-StrictMode -Version Latest` and `$ErrorActionPreference = 'Stop'`. Do not set `BAKERY_INFERENCE_PYTHON` or `BAKERY_REPO_ROOT`; direct launch must use the payload-relative defaults.

- [ ] **Step 4: Run automated checks and parser validation**

Run:

```powershell
python -m pytest tests/deployment/test_camera_installer_manifest.py tests/deployment/test_camera_installer_payload.py tests/prototype/test_camera_worker_snapshot.py tests/prototype/test_camera_worker.py -q
[scriptblock]::Create((Get-Content -Raw tools/package/Build-Latest-DoubleClick.ps1)) | Out-Null
```

Expected: PASS and no PowerShell parser error.

- [ ] **Step 5: Commit**

```powershell
git add tools/package/Build-Latest-DoubleClick.ps1 tools/package/README.md deployment/camera_installer/README.txt tests/deployment/test_camera_installer_payload.py
git commit -m "feat(package): 최신 더블클릭 배포 명령 추가"
```

### Task 5: 실제 휴대용·설치형 산출물 검증

**Files:**
- Create external artifact only: `artifacts/installer_payload/1.1.0-<commit>/`
- Create external artifact only: installer EXE, `.sha256`, build report
- Modify: reviewed compact release receipt only when required by the release process

**Interfaces:**
- Consumes: `tools/package/Build-Latest-DoubleClick.ps1` from Task 4.
- Produces: verified portable payload and Inno installer.

- [ ] **Step 1: Build from a clean attested checkout**

Run:

```powershell
tools\package\Build-Latest-DoubleClick.ps1 `
  -RuntimeRoot C:\path\to\approved\runtime `
  -IsccPath C:\path\to\InnoSetup\ISCC.exe `
  -OutputRoot C:\path\to\empty\BixolonBakeryEvaluator-1.1.0 `
  -Version 1.1.0
```

Expected: creates portable folder, installer EXE, matching `.sha256`, and build report.

- [ ] **Step 2: Verify payload and worker startup**

Run: `python scripts\verify_camera_installation.py --root C:\path\to\BixolonBakeryEvaluator-1.1.0\portable --launch-worker-smoke --worker-device auto --analysis-count 0`

Expected: exit `0`, all package and artifact hashes match, and `worker_smoke.ready` reports the release commit and code identity.

- [ ] **Step 3: Perform manual double-click acceptance**

1. Copy only `portable\` to a clean Windows x64 test directory.
2. Double-click `bakery_camera_prototype.exe` with no environment variables.
3. Confirm diagnostics reaches worker `ready` and reports the expected commit identity/device.
4. Install the installer, run the Start-menu shortcut, and choose the desktop shortcut during setup.
5. Confirm the installed shortcut reaches the same ready provenance.

Expected: both routes run without Git, Flutter, external Python, or developer environment variables.

- [ ] **Step 4: Record evidence without committing binaries**

Record payload manifest SHA-256, installer SHA-256, commit, runtime lock, ready provenance, device, and unavailable manual suites in the reviewed compact receipt. Keep runtime, model, installer, and raw logs external unless release-asset approval exists.

## Plan Self-Review

- Spec coverage: Task 1 preserves development snapshot behavior; Task 2 creates packaged identity; Task 3 makes verification fail closed; Task 4 builds both launch routes; Task 5 confirms real double-click behavior and records provenance.
- Placeholder scan: no deferred implementation markers or undefined interfaces remain.
- Type consistency: all code identities use `dict[str, str]` with `code_commit` and `code_identity_sha256`; disk metadata adds only integer `schema_version`.
