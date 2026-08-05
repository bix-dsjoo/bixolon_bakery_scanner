"""Validation shared by bundled camera runtime build and tests."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import subprocess
from pathlib import Path, PureWindowsPath

REQUIRED_PYTHON_VERSION = "3.11.9"


def validate_runtime_lock(path: Path) -> dict:
    lock = json.loads(path.read_text(encoding="utf-8"))
    if lock.get("schema_version") != 1:
        raise ValueError("runtime lock schema_version must be 1")
    if lock.get("cpu_fallback") is not True:
        raise ValueError("runtime lock must declare cpu_fallback true")
    actual = lock.get("python", {}).get("version")
    if actual != REQUIRED_PYTHON_VERSION:
        raise ValueError(
            f"runtime lock must pin Python {REQUIRED_PYTHON_VERSION}; got {actual}"
        )
    packages = lock.get("packages")
    if not isinstance(packages, dict) or not packages:
        raise ValueError("runtime lock must contain package versions")
    return lock


def validate_python_path_file(path_file: Path) -> None:
    lines = {
        line.strip()
        for line in path_file.read_text(encoding="utf-8-sig").splitlines()
        if line.strip()
    }
    if "import site" not in lines:
        raise ValueError("python311._pth must enable import site")
    normalized = {line.replace("/", "\\").lower() for line in lines}
    if "lib\\site-packages" not in normalized:
        raise ValueError("python311._pth must include Lib\\site-packages")


def validate_site_package_path_files(site_packages: Path) -> None:
    for path_file in sorted(site_packages.glob("*.pth")):
        for raw_line in path_file.read_text(
            encoding="utf-8-sig", errors="strict"
        ).splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or line.startswith("import "):
                continue
            if PureWindowsPath(line).is_absolute() or Path(line).is_absolute():
                raise ValueError(
                    f"absolute build-machine path is forbidden in {path_file.name}"
                )


def _installed_versions(site_packages: Path) -> dict[str, str]:
    return {
        distribution.metadata["Name"].lower(): distribution.version
        for distribution in importlib.metadata.distributions(path=[str(site_packages)])
        if distribution.metadata["Name"]
    }


def validate_runtime_tree(
    runtime_root: Path,
    runtime_lock_path: Path,
    *,
    execute_cpu_check: bool,
) -> dict:
    lock = validate_runtime_lock(runtime_lock_path)
    python_root = runtime_root / "python"
    python_exe = python_root / "python.exe"
    if not python_exe.is_file():
        raise ValueError(f"missing bundled interpreter: {python_exe}")
    validate_python_path_file(python_root / "python311._pth")
    site_packages = python_root / "Lib" / "site-packages"
    validate_site_package_path_files(site_packages)

    installed = _installed_versions(site_packages)
    for name, expected in lock["packages"].items():
        actual = installed.get(name.lower())
        if actual != expected:
            raise ValueError(f"{name} expected {expected}; got {actual}")
    if installed.get("bixolon-bakery-scanner") != "0.1.0":
        raise ValueError("missing bixolon-bakery-scanner 0.1.0 wheel metadata")

    cpu_output = None
    if execute_cpu_check:
        command = [
            str(python_exe),
            "-c",
            (
                "import torch, torchvision, timm, rfdetr, bakery_scanner, "
                "PIL, numpy, yaml, pydantic; "
                "value=torch.ones(1, device='cpu').item(); "
                "print(torch.__version__, torch.version.cuda, value)"
            ),
        ]
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=120,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        )
        if completed.returncode != 0:
            raise ValueError(
                "bundled Python import/CPU tensor check failed:\n"
                f"{completed.stderr.strip()}"
            )
        cpu_output = completed.stdout.strip()

    return {
        "python": REQUIRED_PYTHON_VERSION,
        "packages": lock["packages"],
        "cpu_check": cpu_output,
    }


def write_runtime_manifest(runtime_root: Path) -> Path:
    files = {}
    resolved_root = runtime_root.resolve()
    scan_root = resolved_root
    if str(resolved_root).startswith("\\\\") is False:
        scan_root = Path("\\\\?\\" + str(resolved_root))
    for file_path in sorted(
        (path for path in scan_root.rglob("*") if path.is_file()),
        key=lambda path: str(path).lower(),
    ):
        ordinary_path = Path(str(file_path).removeprefix("\\\\?\\"))
        relative = ordinary_path.relative_to(resolved_root).as_posix()
        digest = hashlib.sha256()
        with file_path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        files[relative] = {
            "bytes": file_path.stat().st_size,
            "sha256": digest.hexdigest(),
        }
    output = runtime_root / "runtime-manifest.json"
    output.write_text(
        json.dumps(
            {"schema_version": 1, "files": files},
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return output


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime-root", required=True, type=Path)
    parser.add_argument("--runtime-lock", required=True, type=Path)
    parser.add_argument("--execute-cpu-check", action="store_true")
    parser.add_argument("--write-manifest", action="store_true")
    args = parser.parse_args()

    result = validate_runtime_tree(
        args.runtime_root,
        args.runtime_lock,
        execute_cpu_check=args.execute_cpu_check,
    )
    if args.write_manifest:
        result["manifest"] = str(write_runtime_manifest(args.runtime_root))
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
