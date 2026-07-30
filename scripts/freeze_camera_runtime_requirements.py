"""Freeze the installed Windows camera runtime dependency closure."""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import platform
import sys
from collections import deque
from pathlib import Path

from packaging.markers import default_environment
from packaging.requirements import InvalidRequirement, Requirement
from packaging.utils import canonicalize_name


ROOTS = {
    "torch",
    "torchvision",
    "timm",
    "rfdetr",
    "numpy",
    "Pillow",
    "PyYAML",
    "pydantic",
    "scipy",
    "scikit-learn",
    "opencv-python",
    "supervision",
    "pycocotools",
}


def _load_lock(path: Path) -> dict:
    lock = json.loads(path.read_text(encoding="utf-8"))
    if lock.get("schema_version") != 1:
        raise ValueError("runtime lock schema_version must be 1")
    if set(lock.get("packages", {})) != ROOTS:
        raise ValueError("runtime lock package roots do not match ROOTS")
    return lock


def _marker_environment() -> dict[str, str]:
    environment = default_environment()
    environment.update(
        {
            "implementation_name": "cpython",
            "platform_machine": "AMD64",
            "platform_system": "Windows",
            "python_version": "3.11",
            "python_full_version": "3.11.9",
            "sys_platform": "win32",
            "extra": "",
        }
    )
    return environment


def freeze(runtime_lock: Path) -> list[str]:
    lock = _load_lock(runtime_lock)
    if platform.python_implementation() != "CPython":
        raise RuntimeError("CPython is required")
    if platform.python_version() != lock["python"]["version"]:
        raise RuntimeError(
            f"Python {lock['python']['version']} required; got "
            f"{platform.python_version()}"
        )

    for name, expected in lock["packages"].items():
        actual = importlib.metadata.version(name)
        if actual != expected:
            raise RuntimeError(f"{name} expected {expected}; got {actual}")

    environment = _marker_environment()
    queue = deque(sorted(ROOTS, key=canonicalize_name))
    pinned: dict[str, tuple[str, str]] = {}

    while queue:
        requested_name = queue.popleft()
        normalized = canonicalize_name(requested_name)
        if normalized in pinned:
            continue
        distribution = importlib.metadata.distribution(requested_name)
        project_name = distribution.metadata["Name"] or requested_name
        version = distribution.version
        pinned[normalized] = (project_name, version)

        for raw_requirement in distribution.requires or []:
            try:
                requirement = Requirement(raw_requirement)
            except InvalidRequirement as error:
                raise RuntimeError(
                    f"invalid requirement from {project_name}: {raw_requirement}"
                ) from error
            if requirement.marker and not requirement.marker.evaluate(environment):
                continue
            if requirement.url:
                raise RuntimeError(
                    f"URL/VCS/local dependency is not allowed: {raw_requirement}"
                )
            queue.append(requirement.name)

    return [
        f"{project_name}=={version}"
        for _, (project_name, version) in sorted(pinned.items())
    ]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime-lock", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    lines = freeze(args.runtime_lock)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {len(lines)} exact requirements to {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
