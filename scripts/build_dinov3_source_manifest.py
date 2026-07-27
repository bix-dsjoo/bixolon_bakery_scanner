"""Build the canonical DINO support source-identity manifest.

The two classifier training roots are deliberately the defaults.  Evidence tools
still require this generated artifact explicitly and compare its SHA-256 to the
support metadata before accepting calibration or locked evaluation.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from bakery_scanner.classification.evidence import (
    atomic_write_bytes,
    canonical_json_bytes,
    sha256_file,
)

DEFAULT_ROOTS = (
    Path("datasets/classification/base_15class"),
    Path("datasets/classification/incremental_5class_crop"),
)


def build_manifest(roots: tuple[Path, ...]) -> bytes:
    sources = []
    for root in roots:
        checked = root.resolve()
        if not checked.is_dir():
            raise ValueError(f"DINO source root does not exist: {checked}")
        for path in sorted(item for item in checked.rglob("*") if item.is_file()):
            sources.append(
                {
                    "identity": str(path.relative_to(checked)).replace("\\", "/"),
                    "sha256": sha256_file(path),
                }
            )
    if not sources or len({row["sha256"] for row in sources}) != len(sources):
        raise ValueError("DINO source roots must contain unique image identities")
    return canonical_json_bytes({"sources": sources})


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build canonical DINOv3 support source manifest."
    )
    parser.add_argument("--source-root", type=Path, action="append", default=None)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    roots = tuple(args.source_root) if args.source_root else DEFAULT_ROOTS
    atomic_write_bytes(args.output, build_manifest(roots))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
