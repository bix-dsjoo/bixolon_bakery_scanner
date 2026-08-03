"""Entrypoint for the persistent camera-inference JSON Lines worker."""

from __future__ import annotations

import argparse
import hashlib
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Sequence


_ATTESTED_TREES = ("src", "dino", "data", "configs", "policies")
_ATTESTED_FILES = (
    "pyproject.toml",
    "models/rfdetr_large_bakery_v1/manifest.json",
    "scripts/run_camera_inference_worker.py",
)


def resolve_paths(
    repo_root: Path,
    warmup_image: Path,
    *,
    allow_external_warmup: bool = False,
) -> tuple[Path, Path]:
    """Resolve CLI paths, allowing an explicit external benchmark warm-up."""
    root = Path(repo_root).resolve()
    image = Path(warmup_image).resolve()
    if not root.is_dir():
        raise ValueError(f"repository root is not a directory: {root}")
    if not image.is_file():
        raise ValueError(f"warm-up image is not a file: {image}")
    if not allow_external_warmup:
        try:
            image.relative_to(root)
        except ValueError as exc:
            raise ValueError("warm-up image must remain under the repository root") from exc
    return root, image


def resolve_import_roots(repo_root: Path) -> tuple[Path, Path]:
    root = Path(repo_root).resolve()
    source_root = root / "src"
    dino_root = root / "dino"
    if not source_root.is_dir():
        raise ValueError(f"repository source directory is missing: {source_root}")
    if not (dino_root / "dinov3" / "__init__.py").is_file():
        raise ValueError(f"bundled DINOv3 package is missing: {dino_root}")
    return source_root, dino_root


def stage_worker_snapshot(repo_root: Path, destination: Path) -> Path:
    """Copy every source/config/policy byte the child is permitted to load."""
    root = Path(repo_root).resolve()
    snapshot = Path(destination).resolve()
    if snapshot.exists():
        raise ValueError(f"worker snapshot destination already exists: {snapshot}")
    try:
        for relative in _ATTESTED_TREES:
            source = root / relative
            if not source.is_dir():
                raise ValueError(f"worker attested tree is missing: {source}")
            shutil.copytree(source, snapshot / relative, ignore=_ignore_transient)
        for relative in _ATTESTED_FILES:
            source = root / relative
            if not source.is_file():
                raise ValueError(f"worker attested file is missing: {source}")
            target = snapshot / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
    except OSError as exc:
        raise ValueError("worker source snapshot could not be created") from exc
    return snapshot


def compute_worker_code_identity(root: Path, *, commit: str) -> dict[str, str]:
    """Hash the immutable snapshot's exact selected application inputs."""
    if len(commit) not in (40, 64) or any(char not in "0123456789abcdef" for char in commit):
        raise ValueError("worker checkout commit is invalid")
    base = Path(root).resolve()
    records: list[str] = []
    try:
        for relative in _ATTESTED_TREES:
            tree = base / relative
            if not tree.is_dir():
                raise ValueError(f"worker attested tree is missing: {tree}")
            for path in sorted(
                (candidate for candidate in tree.rglob("*") if candidate.is_file()),
                key=lambda candidate: candidate.relative_to(base).as_posix(),
            ):
                records.append(_identity_record(base, path))
        for relative in _ATTESTED_FILES:
            path = base / relative
            if not path.is_file():
                raise ValueError(f"worker attested file is missing: {path}")
            records.append(_identity_record(base, path))
    except OSError as exc:
        raise ValueError("worker code identity files are unavailable") from exc
    encoded = "\n".join(records)
    return {
        "code_commit": commit,
        "code_identity_sha256": hashlib.sha256(
            f"{commit}\n{encoded}\n".encode("utf-8")
        ).hexdigest(),
    }


def _capture_child_snapshot(repo_root: Path, destination: Path) -> tuple[Path, dict[str, str]]:
    """Capture a clean checkout before importing any bakery application module."""
    root = Path(repo_root).resolve()
    try:
        status = subprocess.run(
            ("git", "-C", str(root), "status", "--porcelain"),
            text=True,
            capture_output=True,
            check=True,
        )
        if status.stdout.strip():
            raise ValueError("worker source checkout must be clean before import")
        commit = subprocess.run(
            ("git", "-C", str(root), "rev-parse", "HEAD"),
            text=True,
            capture_output=True,
            check=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError) as exc:
        raise ValueError("worker source checkout is not resolvable") from exc
    snapshot = stage_worker_snapshot(root, destination)
    return snapshot, compute_worker_code_identity(snapshot, commit=commit)


def _identity_record(root: Path, path: Path) -> str:
    relative = path.relative_to(root).as_posix()
    return f"{relative}:{hashlib.sha256(path.read_bytes()).hexdigest()}"


def _ignore_transient(_directory: str, names: list[str]) -> set[str]:
    return {
        name
        for name in names
        if name == "__pycache__" or name.endswith((".pyc", ".pyo"))
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", required=True, type=Path)
    parser.add_argument("--device", choices=("auto", "cuda", "cpu"), default="auto")
    parser.add_argument("--warmup-image", required=True, type=Path)
    parser.add_argument("--allow-external-warmup", action="store_true")
    args = parser.parse_args(argv)
    try:
        root, warmup_image = resolve_paths(
            args.repo_root,
            args.warmup_image,
            allow_external_warmup=args.allow_external_warmup,
        )
    except ValueError as exc:
        parser.error(str(exc))

    with tempfile.TemporaryDirectory(prefix="bakery-camera-worker-") as temporary:
        try:
            snapshot, code_identity = _capture_child_snapshot(
                root, Path(temporary) / "checkout"
            )
            source_root, dino_root = resolve_import_roots(snapshot)
        except ValueError as exc:
            parser.error(str(exc))
        sys.path.insert(0, str(dino_root))
        sys.path.insert(0, str(source_root))
        from bakery_scanner.prototype.camera_runtime import CameraInferenceRuntime
        from bakery_scanner.prototype.camera_worker import serve

        def runtime_factory(emit):
            return CameraInferenceRuntime.initialize(
                snapshot,
                warmup_image,
                preference=args.device,
                on_startup=emit,
                artifact_root=root,
            )

        return serve(
            sys.stdin,
            sys.stdout,
            runtime_factory=runtime_factory,
            code_identity=code_identity,
        )


if __name__ == "__main__":
    raise SystemExit(main())
