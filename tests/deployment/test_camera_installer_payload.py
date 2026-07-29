from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.camera_runtime_validation import (
    validate_python_path_file,
    validate_runtime_lock,
    validate_site_package_path_files,
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
