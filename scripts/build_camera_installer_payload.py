"""Assemble the exact Windows evaluator payload and write its SHA-256 manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
import uuid
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Iterable

import yaml

from scripts.run_camera_inference_worker import (
    compute_deployed_worker_code_identity,
    deployed_worker_identity_paths,
)

APP_VERSION = "1.1.0"
RUNTIME_PROFILE = "python311-torch213-cu130-cpu-fallback"
VC_RUNTIME_FILES = ("msvcp140.dll", "vcruntime140.dll", "vcruntime140_1.dll")
CONFIG_FILES = (
    "configs/gpu_rfdetr_classifier_policy.yaml",
    "configs/cpu_rfdetr_classifier_policy.yaml",
)
APPROVED_MODEL_JUNCTION = PurePosixPath("models/rfdetr_large_bakery_v1")


def _extended(path: Path) -> str:
    resolved = str(path.resolve())
    if os.name == "nt" and not resolved.startswith("\\\\"):
        return "\\\\?\\" + resolved
    return resolved


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(_extended(path), "rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _is_reparse(path: Path) -> bool:
    if path.is_symlink():
        return True
    attributes = getattr(os.lstat(_extended(path)), "st_file_attributes", 0)
    return bool(attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT)


def _validate_relative(raw: str) -> PurePosixPath:
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError("allowlist paths must be non-empty strings")
    normalized = raw.replace("\\", "/")
    relative = PurePosixPath(normalized)
    if (
        relative.is_absolute()
        or PureWindowsPath(raw).is_absolute()
        or ".." in relative.parts
    ):
        raise ValueError(f"allowlist path must be repository-relative: {raw}")
    return relative


def _assert_inside_repo(
    repo_root: Path,
    source: Path,
    relative: PurePosixPath,
) -> None:
    lexical_root = Path(os.path.abspath(repo_root))
    lexical_source = Path(os.path.abspath(source))
    try:
        lexical_source.relative_to(lexical_root)
    except ValueError as error:
        raise ValueError(f"source path escapes repository root: {source}") from error
    try:
        source.resolve().relative_to(repo_root.resolve())
    except ValueError as error:
        if relative.parts[: len(APPROVED_MODEL_JUNCTION.parts)] != (
            APPROVED_MODEL_JUNCTION.parts
        ):
            raise ValueError(f"source path escapes repository root: {source}") from error


def _repository_relative(repo_root: Path, source: Path) -> str:
    return (
        Path(os.path.abspath(source))
        .relative_to(Path(os.path.abspath(repo_root)))
        .as_posix()
    )


def _artifact_references(repo_root: Path) -> set[str]:
    referenced: set[str] = set()
    for config_relative in CONFIG_FILES:
        config_path = repo_root / config_relative
        payload = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        for section, key in (
            ("repvit", "checkpoint"),
            ("repvit", "manifest"),
            ("repvit", "prototype_bank"),
            ("dinov3", "weights"),
            ("dinov3", "support"),
            ("dinov3", "local_bank"),
            ("calibration", "artifact"),
            ("calibration", "fusion_policy"),
        ):
            source = config_path.parent / payload[section][key]
            referenced.add(_repository_relative(repo_root, source))

    detector_manifest = (
        repo_root / "models" / "rfdetr_large_bakery_v1" / "manifest.json"
    )
    detector = json.loads(detector_manifest.read_text(encoding="utf-8"))
    for key in ("checkpoint", "calibration"):
        source = detector_manifest.parent / detector[key]["file"]
        referenced.add(_repository_relative(repo_root, source))
    return referenced


def load_pipeline_allowlist(
    repo_root: Path,
    allowlist_path: Path,
) -> dict[str, list[tuple[str, Path]]]:
    repo_root = repo_root.resolve()
    payload = json.loads(allowlist_path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != 1:
        raise ValueError("payload allowlist schema_version must be 1")

    resolved: dict[str, list[tuple[str, Path]]] = {
        "pipeline_files": [],
        "pipeline_directories": [],
    }
    for key, require_file in (
        ("pipeline_files", True),
        ("pipeline_directories", False),
    ):
        values = payload.get(key)
        if not isinstance(values, list):
            raise ValueError(f"{key} must be a list")
        seen: set[str] = set()
        for raw in values:
            relative = _validate_relative(raw)
            canonical = relative.as_posix()
            if canonical in seen:
                raise ValueError(f"duplicate allowlist path: {canonical}")
            seen.add(canonical)
            source = repo_root.joinpath(*relative.parts)
            _assert_inside_repo(repo_root, source, relative)
            if not source.exists():
                raise ValueError(f"allowlisted source is missing: {canonical}")
            if _is_reparse(source):
                raise ValueError(
                    f"allowlisted source may not be a symlink/reparse point: {canonical}"
                )
            if require_file and not source.is_file():
                raise ValueError(f"allowlisted source is not a file: {canonical}")
            if not require_file and not source.is_dir():
                raise ValueError(f"allowlisted source is not a directory: {canonical}")
            resolved[key].append((canonical, source))

    listed_files = {relative for relative, _ in resolved["pipeline_files"]}
    if set(CONFIG_FILES).issubset(listed_files):
        missing_references = _artifact_references(repo_root) - listed_files
        if missing_references:
            raise ValueError(
                "allowlist is missing referenced model/policy files: "
                + ", ".join(sorted(missing_references))
            )
    return resolved


def _iter_files(root: Path) -> Iterable[Path]:
    resolved = root.resolve()
    scan = str(resolved)
    if os.name == "nt" and not scan.startswith("\\\\"):
        scan = "\\\\?\\" + scan
    for directory, names, files in os.walk(scan):
        directory_path = Path(directory)
        names.sort()
        files.sort()
        for name in files:
            extended = directory_path / name
            yield Path(str(extended).removeprefix("\\\\?\\"))


def _copy_tree(source: Path, destination: Path) -> None:
    if destination.exists():
        raise ValueError(f"copy destination already exists: {destination}")
    shutil.copytree(
        _extended(source),
        _extended(destination),
        symlinks=False,
        ignore=lambda _directory, names: {
            name
            for name in names
            if name == "__pycache__" or name.casefold().endswith((".pyc", ".pyo"))
        },
    )


def _copy_file(source: Path, destination: Path) -> None:
    os.makedirs(_extended(destination.parent), exist_ok=True)
    shutil.copy2(_extended(source), _extended(destination))


def _remove_tree(path: Path) -> None:
    shutil.rmtree(_extended(path))


def build_package_manifest(payload_root: Path, *, app_version: str) -> dict:
    payload_root = payload_root.resolve()
    files: dict[str, dict[str, int | str]] = {}
    for file_path in sorted(_iter_files(payload_root), key=lambda value: str(value).lower()):
        relative = file_path.relative_to(payload_root).as_posix()
        if relative == "package-manifest.json":
            continue
        if _is_reparse(file_path):
            raise ValueError(f"payload contains a symlink/reparse point: {relative}")
        files[relative] = {
            "bytes": os.stat(_extended(file_path)).st_size,
            "sha256": _sha256(file_path),
        }
    return {
        "schema_version": 1,
        "app_version": app_version,
        "architecture": "windows-x64",
        "runtime_profile": RUNTIME_PROFILE,
        "files": files,
    }


def build_worker_identity(repo_root: Path, pipeline_root: Path) -> dict[str, int | str]:
    """Record committed source provenance for the self-contained worker tree."""
    root = Path(repo_root).resolve()
    try:
        dirty = subprocess.run(
            ("git", "-C", str(root), "diff", "--quiet", "HEAD", "--", *deployed_worker_identity_paths()),
            check=False,
        )
        if dirty.returncode == 1:
            raise ValueError("tracked inference source must be clean before packaging")
        if dirty.returncode != 0:
            raise OSError("could not inspect tracked inference source")
        commit = subprocess.run(
            ("git", "-C", str(root), "rev-parse", "HEAD"),
            text=True,
            capture_output=True,
            check=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError) as exc:
        raise ValueError("packaging source checkout is not resolvable") from exc
    return {
        "schema_version": 1,
        **compute_deployed_worker_code_identity(pipeline_root, commit=commit),
    }


def assemble_payload(
    *,
    repo_root: Path,
    release_dir: Path,
    runtime_root: Path,
    output: Path,
    vc_runtime_dir: Path,
    allowlist_path: Path,
    readme_path: Path,
    app_version: str,
) -> Path:
    repo_root = repo_root.resolve()
    output = output.resolve()
    if output.exists():
        raise ValueError(f"output already exists: {output}")
    staging = output.with_name(f"{output.name}.staging-{uuid.uuid4().hex}")
    if staging.exists():
        raise ValueError(f"staging already exists: {staging}")
    allowlist = load_pipeline_allowlist(repo_root, allowlist_path)

    try:
        output.parent.mkdir(parents=True, exist_ok=True)
        _copy_tree(release_dir, staging)
        _copy_tree(runtime_root, staging / "runtime")
        _copy_file(
            repo_root / "deployment" / "camera_installer" / "runtime-lock.json",
            staging / "runtime" / "runtime-lock.json",
        )
        for relative, source in allowlist["pipeline_files"]:
            destination = staging / "pipeline" / Path(relative)
            _copy_file(source, destination)
        for relative, source in allowlist["pipeline_directories"]:
            _copy_tree(source, staging / "pipeline" / Path(relative))
        worker_identity = build_worker_identity(repo_root, staging / "pipeline")
        (staging / "pipeline" / "worker-identity.json").write_text(
            json.dumps(worker_identity, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        for dll_name in VC_RUNTIME_FILES:
            source = vc_runtime_dir / dll_name
            if not source.is_file():
                raise ValueError(f"missing application-local VC runtime: {source}")
            _copy_file(source, staging / dll_name)
        _copy_file(readme_path, staging / "README.txt")

        manifest = build_package_manifest(staging, app_version=app_version)
        (staging / "package-manifest.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        staging.rename(output)
        return output
    except Exception:
        if staging.exists() and staging.parent == output.parent:
            _remove_tree(staging)
        raise


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).parents[1])
    parser.add_argument("--release-dir", required=True, type=Path)
    parser.add_argument("--runtime-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--vc-runtime-dir", required=True, type=Path)
    parser.add_argument(
        "--allowlist",
        type=Path,
        default=Path(__file__).parents[1]
        / "deployment"
        / "camera_installer"
        / "payload-paths.json",
    )
    parser.add_argument(
        "--readme",
        type=Path,
        default=Path(__file__).parents[1]
        / "deployment"
        / "camera_installer"
        / "README.txt",
    )
    parser.add_argument("--app-version", default=APP_VERSION)
    args = parser.parse_args()

    result = assemble_payload(
        repo_root=args.repo_root,
        release_dir=args.release_dir,
        runtime_root=args.runtime_root,
        output=args.output,
        vc_runtime_dir=args.vc_runtime_dir,
        allowlist_path=args.allowlist,
        readme_path=args.readme,
        app_version=args.app_version,
    )
    print(result)
    return 0


if __name__ == "__main__":
    sys.exit(main())
