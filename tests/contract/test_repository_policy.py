from __future__ import annotations

import json
from pathlib import Path
import subprocess
import tomllib


ROOT = Path(__file__).resolve().parents[2]


def _tracked_files() -> tuple[str, ...]:
    completed = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    )
    return tuple(
        value.decode("utf-8")
        for value in completed.stdout.split(b"\0")
        if value
    )


def test_repository_exposes_long_lived_rd_responsibilities():
    required = (
        "apps",
        "benchmarks",
        "configs/data",
        "configs/deployment",
        "configs/evaluation",
        "configs/pipelines",
        "configs/training",
        "data/catalogs",
        "data/fixtures",
        "data/manifests",
        "data/splits",
        "deployment",
        "docs/adr",
        "docs/architecture",
        "docs/research",
        "docs/runbooks",
        "docs/workflows",
        "experiments",
        "models",
        "policies",
        "src/bakery_scanner/artifacts",
        "src/bakery_scanner/benchmarking",
        "src/bakery_scanner/detection",
        "src/bakery_scanner/pipelines",
        "tests/contract",
        "tools/artifacts",
        "tools/benchmark",
        "tools/data",
        "tools/evaluate",
        "tools/migrate",
        "tools/package",
        "tools/train",
    )

    assert not [path for path in required if not (ROOT / path).is_dir()]


def test_pytest_defaults_to_first_party_tests_and_registers_suites():
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    pytest_options = pyproject["tool"]["pytest"]["ini_options"]

    assert pytest_options["testpaths"] == ["tests"]
    assert {"artifact", "contract", "gpu", "integration", "slow", "unit"} <= {
        marker.split(":", 1)[0] for marker in pytest_options["markers"]
    }


def test_artifact_lock_is_versioned_and_uses_lowercase_sha256():
    payload = json.loads((ROOT / "artifacts.lock.json").read_text(encoding="utf-8"))

    assert payload["schema_version"] == 1
    assert payload["canonical_pipeline"] == "rfdetr_l_repvit_m1_dinov3_vits16_cpu"
    assert payload["artifacts"]
    for artifact in payload["artifacts"]:
        assert len(artifact["sha256"]) == 64
        assert artifact["sha256"] == artifact["sha256"].lower()
        int(artifact["sha256"], 16)
        assert artifact["storage"] in {"external", "git-lfs", "github-release"}


def test_lfs_rules_are_scoped_to_redistribution_cleared_release_assets():
    attributes = (ROOT / ".gitattributes").read_text(encoding="utf-8")

    assert "release-assets/models/**" in attributes
    assert "release-assets/prototype-banks/**" in attributes
    assert "\n*.pt filter=lfs" not in f"\n{attributes}"
    assert "\n*.pth filter=lfs" not in f"\n{attributes}"


def test_git_contains_no_oversized_or_runtime_generated_payloads():
    tracked = _tracked_files()
    forbidden_prefixes = (
        "artifacts/",
        "datasets/detection/",
        "dist/",
        "weight/",
    )
    forbidden_suffixes = (".pth", ".pt", ".onnx", ".whl")

    assert not [
        path
        for path in tracked
        if path.startswith(forbidden_prefixes) or path.endswith(forbidden_suffixes)
    ]
    assert not [
        path
        for path in tracked
        if (ROOT / path).is_file() and (ROOT / path).stat().st_size > 100 * 1024 * 1024
    ]
