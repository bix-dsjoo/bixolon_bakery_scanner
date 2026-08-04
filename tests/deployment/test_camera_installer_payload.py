from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

from scripts.build_camera_installer_payload import (
    assemble_payload,
    build_worker_identity,
    load_pipeline_allowlist,
)
from scripts.camera_runtime_validation import (
    validate_python_path_file,
    validate_runtime_lock,
    validate_site_package_path_files,
)
from scripts.prune_camera_installer_runtime import (
    LICENSE_ARCHIVE,
    archive_dist_info_licenses,
    prune_bytecode,
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_payload_manifest(payload_root: Path) -> dict:
    return json.loads(
        (payload_root / "package-manifest.json").read_text(encoding="utf-8")
    )


def _write_attested_worker_tree(root: Path) -> None:
    for relative, content in {
        "pyproject.toml": "[project]\nname='snapshot'\n",
        "src/bakery_scanner/module.py": "VALUE = 'source'\n",
        "dino/dinov3/__init__.py": "VALUE = 'source'\n",
        "data/catalogs/classes.json": "[]\n",
        "configs/gpu_rfdetr_classifier_policy.yaml": "gpu: source\n",
        "configs/cpu_rfdetr_classifier_policy.yaml": "cpu: source\n",
        "policies/presentation/camera_action_state_v2.json": "{}\n",
        "policies/classification/policy_v2_manifest_rebound_cpu_smoke.json": "{}\n",
        "policies/classification/fusion_local_or_global_consensus_margin_v1.json": "{}\n",
        "models/rfdetr_large_bakery_v1/manifest.json": "{}\n",
        "scripts/run_camera_inference_worker.py": "print('worker')\n",
    }.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


def test_worker_identity_rejects_dirty_tracked_inference_source(tmp_path: Path) -> None:
    """Catch packaging an identity that does not describe committed inference code."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _write_attested_worker_tree(repo)
    subprocess.run(("git", "init", str(repo)), check=True, capture_output=True)
    subprocess.run(("git", "-C", str(repo), "config", "user.email", "test@example.com"), check=True)
    subprocess.run(("git", "-C", str(repo), "config", "user.name", "Test"), check=True)
    subprocess.run(("git", "-C", str(repo), "add", "."), check=True)
    subprocess.run(("git", "-C", str(repo), "commit", "-m", "fixture"), check=True, capture_output=True)
    pipeline = tmp_path / "pipeline"
    shutil.copytree(repo, pipeline, ignore=shutil.ignore_patterns(".git"))

    identity = build_worker_identity(repo, pipeline)

    assert identity["schema_version"] == 1
    assert identity["code_commit"] == subprocess.run(
        ("git", "-C", str(repo), "rev-parse", "HEAD"),
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    (repo / "src" / "bakery_scanner" / "module.py").write_text(
        "VALUE = 'dirty'\n", encoding="utf-8"
    )
    with pytest.raises(ValueError, match="tracked inference source must be clean"):
        build_worker_identity(repo, pipeline)


def test_latest_double_click_builder_creates_both_distribution_routes() -> None:
    """Catch release tooling that omits the portable or installer launch route."""
    repo_root = Path(__file__).parents[2]
    script = repo_root / "tools" / "package" / "Build-Latest-DoubleClick.ps1"

    assert script.is_file()
    source = script.read_text(encoding="utf-8")
    for expected in (
        "RuntimeRoot",
        "IsccPath",
        "flutter.bat",
        "verify_camera_installation.py",
        "build_camera_installer.ps1",
        "portable",
        "installer",
    ):
        assert expected in source
    for readme in (
        repo_root / "tools" / "package" / "README.md",
        repo_root / "deployment" / "camera_installer" / "README.txt",
    ):
        contents = readme.read_text(encoding="utf-8")
        assert "bakery_camera_prototype.exe" in contents
        assert "더블클릭" in contents


def test_installer_builder_accepts_absolute_command_paths(tmp_path: Path) -> None:
    """Catch the installer wrapper treating an absolute path as a child path."""
    repo_root = Path(__file__).parents[2]
    missing_payload = tmp_path / "missing-payload"
    completed = subprocess.run(
        (
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(repo_root / "scripts" / "build_camera_installer.ps1"),
            "-PayloadRoot",
            str(missing_payload),
            "-IsccPath",
            str(tmp_path / "missing-iscc.exe"),
            "-Version",
            "1.1.0",
            "-OutputDir",
            str(tmp_path / "output"),
            "-Python",
            sys.executable,
        ),
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode != 0
    assert "PayloadRoot is missing" in completed.stderr


def test_latest_builder_accepts_absolute_command_paths(tmp_path: Path) -> None:
    """Catch the latest-build wrapper corrupting an absolute runtime path."""
    repo_root = Path(__file__).parents[2]
    completed = subprocess.run(
        (
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(repo_root / "tools" / "package" / "Build-Latest-DoubleClick.ps1"),
            "-RuntimeRoot",
            str(tmp_path / "missing-runtime"),
            "-IsccPath",
            str(tmp_path / "missing-iscc.exe"),
            "-OutputRoot",
            str(tmp_path / "output"),
            "-FlutterPath",
            str(tmp_path / "missing-flutter.bat"),
            "-Python",
            sys.executable,
        ),
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode != 0
    assert "RuntimeRoot directory is missing" in completed.stderr


@pytest.fixture
def payload_root(tmp_path: Path) -> Path:
    """Build a self-contained payload from a clean, minimal source checkout."""
    source_root = Path(__file__).parents[2]
    allowlist = load_pipeline_allowlist(
        source_root,
        source_root / "deployment" / "camera_installer" / "payload-paths.json",
    )
    policy_relative = "policies/presentation/camera_action_state_v2.json"
    allowlisted_files = {
        relative for relative, _ in allowlist["pipeline_files"]
    }
    assert policy_relative in allowlisted_files
    assert "scripts/run_camera_inference_worker.py" in allowlisted_files

    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _write_attested_worker_tree(repo_root)
    runtime_lock = repo_root / "deployment" / "camera_installer" / "runtime-lock.json"
    runtime_lock.parent.mkdir(parents=True)
    runtime_lock.write_text("{}\n", encoding="utf-8")
    subprocess.run(("git", "init", str(repo_root)), check=True, capture_output=True)
    subprocess.run(("git", "-C", str(repo_root), "config", "user.email", "test@example.com"), check=True)
    subprocess.run(("git", "-C", str(repo_root), "config", "user.name", "Test"), check=True)
    subprocess.run(("git", "-C", str(repo_root), "add", "."), check=True)
    subprocess.run(("git", "-C", str(repo_root), "commit", "-m", "fixture"), check=True, capture_output=True)

    release_dir = tmp_path / "release"
    release_dir.mkdir()
    (release_dir / "bakery_camera_prototype.exe").write_bytes(b"release")
    runtime_root = tmp_path / "runtime"
    runtime_root.mkdir()
    vc_runtime_dir = tmp_path / "vc-runtime"
    vc_runtime_dir.mkdir()
    for name in ("msvcp140.dll", "vcruntime140.dll", "vcruntime140_1.dll"):
        (vc_runtime_dir / name).write_bytes(name.encode("ascii"))
    readme = tmp_path / "README.txt"
    readme.write_text("offline evaluator\n", encoding="utf-8")
    minimal_allowlist = tmp_path / "payload-paths.json"
    minimal_allowlist.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "pipeline_directories": ["src/bakery_scanner", "dino/dinov3", "configs"],
                "pipeline_files": [
                    "pyproject.toml",
                    "scripts/run_camera_inference_worker.py",
                    "data/catalogs/classes.json",
                    "models/rfdetr_large_bakery_v1/manifest.json",
                    policy_relative,
                    "policies/classification/policy_v2_manifest_rebound_cpu_smoke.json",
                    "policies/classification/fusion_local_or_global_consensus_margin_v1.json",
                ],
            }
        ),
        encoding="utf-8",
    )

    output = tmp_path / "payload"
    return assemble_payload(
        repo_root=repo_root,
        release_dir=release_dir,
        runtime_root=runtime_root,
        output=output,
        vc_runtime_dir=vc_runtime_dir,
        allowlist_path=minimal_allowlist,
        readme_path=readme,
        app_version="1.0.2",
    )


@pytest.mark.artifact
def test_camera_payload_contains_hashed_presentation_policy(
    payload_root: Path,
) -> None:
    policy = (
        payload_root
        / "pipeline"
        / "policies"
        / "presentation"
        / "camera_action_state_v2.json"
    )
    manifest = _load_payload_manifest(payload_root)

    assert policy.is_file()
    assert (
        manifest["files"][
            "pipeline/policies/presentation/camera_action_state_v2.json"
        ]
        ["sha256"]
        == _sha256(policy)
    )


def test_runtime_lock_rejects_non_pinned_python(tmp_path: Path) -> None:
    lock = {
        "schema_version": 1,
        "python": {"version": "3.12.0"},
        "packages": {},
    }
    path = tmp_path / "runtime-lock.json"
    path.write_text(json.dumps(lock), encoding="utf-8")

    with pytest.raises(ValueError, match="3.11.9"):
        validate_runtime_lock(path)


def test_embedded_python_path_requires_site_packages_and_import_site(
    tmp_path: Path,
) -> None:
    path_file = tmp_path / "python311._pth"
    path_file.write_text("python311.zip\n.\n", encoding="utf-8")

    with pytest.raises(ValueError, match="import site"):
        validate_python_path_file(path_file)

    path_file.write_text(
        "python311.zip\n.\nLib\\site-packages\nimport site\n",
        encoding="utf-8",
    )
    validate_python_path_file(path_file)


def test_site_packages_rejects_absolute_build_machine_path(
    tmp_path: Path,
) -> None:
    site_packages = tmp_path / "Lib" / "site-packages"
    site_packages.mkdir(parents=True)
    (site_packages / "unsafe.pth").write_text(
        "C:\\workspace\\private-runtime\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="absolute"):
        validate_site_package_path_files(site_packages)


def test_runtime_pruner_removes_only_regenerated_bytecode(
    tmp_path: Path,
) -> None:
    package = tmp_path / "runtime" / "python" / "Lib" / "site-packages" / "demo"
    cache = package / "__pycache__"
    cache.mkdir(parents=True)
    source = package / "module.py"
    bytecode = cache / "module.cpython-311.pyc"
    source.write_text("VALUE = 1\n", encoding="utf-8")
    bytecode.write_bytes(b"generated")

    removed_files, removed_bytes = prune_bytecode(tmp_path / "runtime")

    assert (removed_files, removed_bytes) == (1, len(b"generated"))
    assert source.read_text(encoding="utf-8") == "VALUE = 1\n"
    assert not cache.exists()


def test_runtime_pruner_requires_embedded_python_directory(
    tmp_path: Path,
) -> None:
    with pytest.raises(ValueError, match="python directory is missing"):
        prune_bytecode(tmp_path)


def test_runtime_license_archiver_preserves_nested_notice_paths(
    tmp_path: Path,
) -> None:
    site_packages = (
        tmp_path / "runtime" / "python" / "Lib" / "site-packages"
    )
    licenses = site_packages / "demo-1.0.dist-info" / "licenses" / "third_party"
    licenses.mkdir(parents=True)
    notice = licenses / "NOTICE.txt"
    notice.write_bytes(b"third-party notice\n")
    top_level_license = site_packages / "demo-1.0.dist-info" / "LICENSE"
    top_level_license.write_text("package license\n", encoding="utf-8")

    archived_files, archived_bytes = archive_dist_info_licenses(
        tmp_path / "runtime"
    )

    assert (archived_files, archived_bytes) == (
        1,
        len("third-party notice\n".encode()),
    )
    assert not (site_packages / "demo-1.0.dist-info" / "licenses").exists()
    assert top_level_license.is_file()
    with zipfile.ZipFile(tmp_path / "runtime" / LICENSE_ARCHIVE) as archive:
        assert archive.namelist() == [
            "demo-1.0.dist-info/licenses/third_party/NOTICE.txt"
        ]
        assert archive.read(archive.namelist()[0]) == b"third-party notice\n"
