"""Entrypoint for the persistent camera-inference JSON Lines worker."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence


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

    try:
        source_root, dino_root = resolve_import_roots(root)
    except ValueError as exc:
        parser.error(str(exc))
    sys.path.insert(0, str(dino_root))
    sys.path.insert(0, str(source_root))
    from bakery_scanner.prototype.camera_runtime import CameraInferenceRuntime
    from bakery_scanner.prototype.camera_worker import serve

    def runtime_factory(emit):
        return CameraInferenceRuntime.initialize(
            root,
            warmup_image,
            preference=args.device,
            on_startup=emit,
        )

    return serve(sys.stdin, sys.stdout, runtime_factory=runtime_factory)


if __name__ == "__main__":
    raise SystemExit(main())
