"""Command-line verification for repository artifacts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .lock import ArtifactIntegrityError, ArtifactLock


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Verify Bakery AI external artifacts against artifacts.lock.json."
    )
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--lock", type=Path, default=Path("artifacts.lock.json"))
    parser.add_argument(
        "--manifest-only",
        action="store_true",
        help="report missing artifacts without failing",
    )
    arguments = parser.parse_args(argv)
    root = arguments.root.resolve()
    lock_path = arguments.lock
    if not lock_path.is_absolute():
        lock_path = root / lock_path
    try:
        report = ArtifactLock.load(lock_path).verify(
            root,
            require_all=not arguments.manifest_only,
        )
    except (ArtifactIntegrityError, OSError, ValueError) as error:
        print(json.dumps({"ok": False, "error": str(error)}, ensure_ascii=False))
        return 2
    print(
        json.dumps(
            {
                "ok": report.complete,
                "items": [
                    {
                        "id": item.artifact_id,
                        "path": str(item.path),
                        "status": item.status,
                    }
                    for item in report.items
                ],
            },
            ensure_ascii=False,
        )
    )
    return 0 if report.complete or arguments.manifest_only else 2


if __name__ == "__main__":
    raise SystemExit(main())
