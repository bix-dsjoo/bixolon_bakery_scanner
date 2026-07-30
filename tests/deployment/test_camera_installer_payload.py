from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

import pytest

from scripts.build_camera_installer_payload import (
    assemble_payload,
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


@pytest.fixture
def payload_root(tmp_path: Path) -> Path:
    """Build a minimal payload using the production policy allowlist entry."""
    repo_root = Path(__file__).parents[2]
    allowlist = load_pipeline_allowlist(
        repo_root,
        repo_root / "deployment" / "camera_installer" / "payload-paths.json",
    )
    policy_relative = "configs/camera_presentation_policy.json"
    assert policy_relative in {
        relative for relative, _ in allowlist["pipeline_files"]
    }

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
                "pipeline_directories": [],
                "pipeline_files": [policy_relative],
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
    policy = payload_root / "pipeline" / "configs" / "camera_presentation_policy.json"
    manifest = _load_payload_manifest(payload_root)

    assert policy.is_file()
    assert (
        manifest["files"]["pipeline/configs/camera_presentation_policy.json"]
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
