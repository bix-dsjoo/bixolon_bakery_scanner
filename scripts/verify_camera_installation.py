"""Verify a payload or installed BIXOLON Bakery AI Evaluator tree."""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import os
import queue
import subprocess
import sys
import threading
import time
from pathlib import Path

import yaml

from scripts.build_camera_installer_payload import _extended, _iter_files
from scripts.camera_runtime_validation import validate_runtime_tree

INSTALLER_METADATA_PATTERNS = ("unins???.exe", "unins???.dat", "unins???.msg")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(_extended(path), "rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_package_manifest(root: Path) -> dict:
    root = root.resolve()
    manifest_path = root / "package-manifest.json"
    if not manifest_path.is_file():
        raise ValueError("package-manifest.json is missing")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != 1:
        raise ValueError("package manifest schema_version must be 1")
    declared = manifest.get("files")
    if not isinstance(declared, dict):
        raise ValueError("package manifest files must be an object")
    if any(Path(relative).is_absolute() or ".." in Path(relative).parts for relative in declared):
        raise ValueError("package manifest contains a non-relative path")

    actual = {
        path.relative_to(root).as_posix()
        for path in _iter_files(root)
        if path.relative_to(root).as_posix() != "package-manifest.json"
    }
    expected = set(declared)
    missing = expected - actual
    extra = {
        relative
        for relative in actual - expected
        if not any(
            fnmatch.fnmatch(relative.lower(), pattern)
            for pattern in INSTALLER_METADATA_PATTERNS
        )
    }
    if missing:
        raise ValueError("package files missing: " + ", ".join(sorted(missing)))
    if extra:
        raise ValueError("package contains extra files: " + ", ".join(sorted(extra)))

    for relative in sorted(expected):
        entry = declared[relative]
        path = root / Path(relative)
        if Path(_extended(path)).stat().st_size != entry.get("bytes"):
            raise ValueError(f"size mismatch: {relative}")
        if _sha256(path) != entry.get("sha256"):
            raise ValueError(f"hash mismatch: {relative}")
    return manifest


def _verify_declared_artifact(
    base: Path,
    artifact: dict,
    *,
    context: str,
) -> None:
    path = (base / artifact["file"]).resolve()
    if not path.is_file():
        raise ValueError(f"{context} file is missing: {path}")
    if _sha256(path) != artifact["sha256"]:
        raise ValueError(f"{context} internal SHA-256 mismatch")


def verify_internal_artifact_hashes(root: Path) -> None:
    pipeline = root.resolve() / "pipeline"
    for config_name in (
        "gpu_rfdetr_classifier_policy.yaml",
        "cpu_rfdetr_classifier_policy.yaml",
    ):
        config_path = pipeline / "configs" / config_name
        payload = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        for section, path_key, hash_key in (
            ("repvit", "checkpoint", "checkpoint_sha256"),
            ("repvit", "manifest", "manifest_sha256"),
            ("repvit", "prototype_bank", "prototype_bank_sha256"),
            ("dinov3", "weights", "weights_sha256"),
            ("dinov3", "support", "support_sha256"),
            ("dinov3", "local_bank", "local_bank_sha256"),
            ("calibration", "artifact", "artifact_sha256"),
            ("calibration", "fusion_policy", "fusion_policy_sha256"),
        ):
            source = (config_path.parent / payload[section][path_key]).resolve()
            if not source.is_file():
                raise ValueError(f"{config_name} references missing {section} file")
            if _sha256(source) != payload[section][hash_key]:
                raise ValueError(f"{config_name} {section} SHA-256 mismatch")

    detector_manifest = (
        pipeline / "models" / "rfdetr_large_bakery_v1" / "manifest.json"
    )
    detector = json.loads(detector_manifest.read_text(encoding="utf-8"))
    for key in ("checkpoint", "calibration"):
        _verify_declared_artifact(
            detector_manifest.parent,
            detector[key],
            context=f"detector {key}",
        )


def launch_worker_smoke(
    root: Path,
    timeout_seconds: float = 900,
    *,
    device: str = "auto",
    analysis_count: int = 0,
) -> dict:
    root = root.resolve()
    pipeline = root / "pipeline"
    process = subprocess.Popen(
        [
            str(root / "runtime" / "python" / "python.exe"),
            str(pipeline / "scripts" / "run_camera_inference_worker.py"),
            "--repo-root",
            str(pipeline),
            "--device",
            device,
            "--warmup-image",
            str(
                pipeline
                / "samples"
                / "batch2_e3_m3_h3"
                / "g20_b02_e_0301.jpg"
            ),
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )
    assert process.stdout is not None
    assert process.stdin is not None
    events: queue.Queue[str] = queue.Queue()
    reader = threading.Thread(
        target=lambda: [events.put(line) for line in process.stdout],
        daemon=True,
    )
    reader.start()
    deadline = time.monotonic() + timeout_seconds
    ready: dict | None = None
    while time.monotonic() < deadline:
        try:
            line = events.get(timeout=min(1.0, deadline - time.monotonic()))
        except queue.Empty:
            if process.poll() is not None:
                break
            continue
        event = json.loads(line)
        if event.get("type") == "fatal":
            raise ValueError(f"worker startup failed: {event}")
        if event.get("type") == "ready":
            ready = event
            break
    if ready is None:
        process.kill()
        stderr = process.communicate(timeout=30)[1]
        raise ValueError(f"worker did not reach ready: {stderr[-4000:]}")

    analyses = []
    warmup_image = (
        pipeline / "samples" / "batch2_e3_m3_h3" / "g20_b02_e_0301.jpg"
    )
    for index in range(analysis_count):
        request_id = f"installer-analysis-{index + 1}"
        process.stdin.write(
            json.dumps(
                {
                    "type": "analyze",
                    "request_id": request_id,
                    "image_path": str(warmup_image),
                }
            )
            + "\n"
        )
        process.stdin.flush()
        result = None
        while time.monotonic() < deadline:
            try:
                line = events.get(timeout=min(1.0, deadline - time.monotonic()))
            except queue.Empty:
                if process.poll() is not None:
                    break
                continue
            event = json.loads(line)
            if event.get("type") in {"fatal", "error"}:
                raise ValueError(f"worker analysis failed: {event}")
            if (
                event.get("type") == "result"
                and event.get("request_id") == request_id
            ):
                result = event
                break
        if result is None:
            process.kill()
            raise ValueError(f"worker analysis timed out: {request_id}")
        analyses.append(result)

    process.stdin.write('{"type":"shutdown","request_id":"installer-smoke"}\n')
    process.stdin.flush()
    process.wait(timeout=120)
    if process.returncode != 0:
        raise ValueError(f"worker shutdown returned {process.returncode}")
    return {"ready": ready, "analyses": analyses}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--launch-worker-smoke", action="store_true")
    parser.add_argument(
        "--worker-device",
        choices=("auto", "cuda", "cpu"),
        default="auto",
    )
    parser.add_argument("--analysis-count", type=int, default=0)
    args = parser.parse_args()

    manifest = verify_package_manifest(args.root)
    verify_internal_artifact_hashes(args.root)
    runtime = validate_runtime_tree(
        args.root / "runtime",
        args.root / "runtime" / "runtime-lock.json",
        execute_cpu_check=True,
    )
    result = {"manifest_files": len(manifest["files"]), "runtime": runtime}
    if args.launch_worker_smoke:
        if args.analysis_count < 0:
            raise ValueError("analysis-count must be non-negative")
        result["worker_smoke"] = launch_worker_smoke(
            args.root,
            device=args.worker_device,
            analysis_count=args.analysis_count,
        )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
