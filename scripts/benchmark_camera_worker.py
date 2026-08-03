"""Benchmark one persistent camera worker after its one-time warm-up."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import queue
import shutil
import subprocess
import sys
import tempfile
import threading
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import TextIO

# Keep direct CLI execution bound to this checkout, not an ambient editable install.
_SCRIPT_ROOT = Path(__file__).resolve().parents[1]
_SOURCE_ROOT = _SCRIPT_ROOT / "src"
if str(_SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(_SOURCE_ROOT))

_ATTESTED_TREES = ("src", "dino", "data", "configs", "policies")
_ATTESTED_FILES = (
    "pyproject.toml",
    "models/rfdetr_large_bakery_v1/manifest.json",
    "scripts/run_camera_inference_worker.py",
)
_STAGED_ENTRYPOINT = "scripts/run_camera_inference_worker.py"
_STAGED_BOOTSTRAP = (
    "import hashlib,pathlib,sys;"
    "entry=pathlib.Path(sys.argv[1]);expected=sys.argv[2];payload=entry.read_bytes();"
    "(hashlib.sha256(payload).hexdigest()==expected) or (_ for _ in ()).throw(SystemExit('staged entrypoint hash mismatch'));"
    "sys.argv=[str(entry),*sys.argv[3:]];"
    "globals={'__name__':'__main__','__file__':str(entry),'__package__':None};"
    "exec(compile(payload,str(entry),'exec'),globals,globals)"
)

from bakery_scanner.benchmarking.gpu_worker_receipt import (
    STAGES as GPU_RECEIPT_STAGES,
    build_receipt,
)


MINIMUM_MEASURED_RUNS = 20
STARTUP_EVENT_TYPES = frozenset({"loading", "warming", "ready"})
EXPECTED_TIMING_STAGES = GPU_RECEIPT_STAGES
_EOF = object()


def validate_run_count(run_count: int) -> int:
    """Return a valid measured-run count, rejecting undersized samples."""
    if isinstance(run_count, bool) or not isinstance(run_count, int):
        raise ValueError("run count must be an integer")
    if run_count < MINIMUM_MEASURED_RUNS:
        raise ValueError(f"benchmark requires at least {MINIMUM_MEASURED_RUNS} runs")
    return run_count


def load_external_manifest(
    manifest_path: Path,
) -> tuple[tuple[dict[str, str], ...], str]:
    """Load and verify the fixed external E/M/H benchmark manifest."""
    path = Path(manifest_path).resolve()
    if not path.is_file():
        raise ValueError(f"benchmark manifest is missing: {path}")
    encoded = path.read_bytes()
    manifest_sha256 = hashlib.sha256(encoded).hexdigest()
    try:
        payload = json.loads(encoded)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("benchmark manifest must be valid JSON") from exc
    if not isinstance(payload, Mapping) or set(payload) != {"samples"}:
        raise ValueError("benchmark manifest schema is invalid")
    rows = payload["samples"]
    if not isinstance(rows, list) or not rows:
        raise ValueError("benchmark manifest samples must be a non-empty list")
    samples: list[dict[str, str]] = []
    image_ids: set[str] = set()
    groups: set[str] = set()
    for row in rows:
        if not isinstance(row, Mapping) or set(row) != {
            "image_id", "group", "image_path", "image_sha256"
        }:
            raise ValueError("benchmark manifest sample schema is invalid")
        image_id = _non_empty_string(row["image_id"], "manifest image_id")
        if image_id in image_ids:
            raise ValueError("benchmark manifest image_id is duplicated")
        group = row["group"]
        if group not in {"E", "M", "H"}:
            raise ValueError("benchmark manifest group is invalid")
        image_path = row["image_path"]
        if not isinstance(image_path, str) or not image_path:
            raise ValueError("benchmark manifest image_path is invalid")
        image = Path(image_path)
        if not image.is_absolute() or not image.is_file():
            raise ValueError("benchmark manifest image_path must be an existing absolute path")
        image_sha256 = _sha256(row["image_sha256"], "manifest image_sha256")
        if hashlib.sha256(image.read_bytes()).hexdigest() != image_sha256:
            raise ValueError("benchmark manifest image SHA-256 mismatch")
        image_ids.add(image_id)
        groups.add(group)
        samples.append(
            {
                "image_id": image_id,
                "group": group,
                "image_path": str(image.resolve()),
                "image_sha256": image_sha256,
            }
        )
    if groups != {"E", "M", "H"}:
        raise ValueError("benchmark manifest requires at least one E, M, and H sample")
    return tuple(samples), manifest_sha256


def load_benchmark_protocol(path: Path) -> tuple[dict[str, object], str]:
    """Load the reviewed CUDA-only worker-boundary protocol."""
    protocol_path = Path(path).resolve()
    if not protocol_path.is_file():
        raise ValueError(f"benchmark protocol is missing: {protocol_path}")
    encoded = protocol_path.read_bytes()
    protocol_sha256 = hashlib.sha256(encoded).hexdigest()
    try:
        protocol = json.loads(encoded)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("benchmark protocol must be valid JSON") from exc
    expected = {
        "device": "cuda:0",
        "groups": ["E", "M", "H"],
        "minimum_group_observations": 100,
        "minimum_warmups": 20,
        "overall_p95_limit_ms": 100.0,
        "per_group_p95_limit_ms": 100.0,
        "schema_version": 1,
        "worker_boundary": "file_read_to_in_memory_result_payload",
    }
    if protocol != expected:
        raise ValueError("benchmark protocol does not match rtx5080_worker_p95_v1")
    return expected, protocol_sha256


def resolve_code_identity(root: Path) -> dict[str, str]:
    """Bind evidence to one clean checkout and its runtime-defining files."""
    repository = _bound_repository_root(root)
    try:
        status = subprocess.run(
            ("git", "-C", str(repository), "status", "--porcelain"),
            text=True,
            capture_output=True,
            check=True,
        )
        if status.stdout.strip():
            raise ValueError("benchmark evidence requires a clean checked-out source")
        commit = subprocess.run(
            ("git", "-C", str(repository), "rev-parse", "HEAD"),
            text=True,
            capture_output=True,
            check=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError) as exc:
        raise ValueError("benchmark evidence requires a resolvable git checkout") from exc
    if len(commit) not in (40, 64) or any(character not in "0123456789abcdef" for character in commit):
        raise ValueError("benchmark checkout commit is invalid")
    return _compute_code_identity(repository, commit=commit)


def _compute_code_identity(root: Path, *, commit: str) -> dict[str, str]:
    """Hash the exact source/config/policy set staged by the child worker."""
    base = Path(root).resolve()
    records: list[str] = []
    try:
        for relative in _ATTESTED_TREES:
            tree = base / relative
            if not tree.is_dir():
                raise ValueError(f"benchmark attested tree is missing: {tree}")
            for path in sorted(
                (candidate for candidate in tree.rglob("*") if candidate.is_file()),
                key=lambda candidate: candidate.relative_to(base).as_posix(),
            ):
                if "__pycache__" in path.parts or path.suffix in {".pyc", ".pyo"}:
                    continue
                records.append(_identity_record(base, path))
        for relative in _ATTESTED_FILES:
            path = base / relative
            if not path.is_file():
                raise ValueError(f"benchmark attested file is missing: {path}")
            records.append(_identity_record(base, path))
    except OSError as exc:
        raise ValueError("benchmark code identity files are unavailable") from exc
    bound = "\n".join(records)
    return {
        "code_commit": commit,
        "code_identity_sha256": hashlib.sha256(
            f"{commit}\n{bound}\n".encode("utf-8")
        ).hexdigest(),
    }


def _identity_record(root: Path, path: Path) -> str:
    return (
        f"{path.relative_to(root).as_posix()}:"
        f"{hashlib.sha256(path.read_bytes()).hexdigest()}"
    )


def _stage_parent_snapshot(root: Path, destination: Path) -> Path:
    """Create the immutable-input bundle that the evidence child will execute."""
    snapshot = Path(destination).resolve()
    if snapshot.exists():
        raise ValueError("benchmark staged snapshot destination already exists")
    try:
        for relative in _ATTESTED_TREES:
            source = root / relative
            if not source.is_dir():
                raise ValueError(f"benchmark attested tree is missing: {source}")
            shutil.copytree(source, snapshot / relative, ignore=_ignore_transient)
        for relative in _ATTESTED_FILES:
            source = root / relative
            if not source.is_file():
                raise ValueError(f"benchmark attested file is missing: {source}")
            target = snapshot / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
    except OSError as exc:
        raise ValueError("benchmark staged snapshot could not be created") from exc
    return snapshot


def _ignore_transient(_directory: str, names: list[str]) -> set[str]:
    return {
        name
        for name in names
        if name == "__pycache__" or name.endswith((".pyc", ".pyo"))
    }


def _bound_repository_root(root: Path) -> Path:
    """Reject a repo root that differs from the source tree imported above."""
    repository = Path(root).resolve()
    if repository != _SCRIPT_ROOT:
        raise ValueError(
            "benchmark repo_root must match the source checkout used for imports"
        )
    return repository


def _require_stable_code_identity(
    root: Path,
    expected: Mapping[str, str],
) -> None:
    """Fail closed if the clean code identity changes while the worker runs."""
    observed = resolve_code_identity(root)
    if observed != dict(expected):
        raise ValueError("benchmark code identity changed during the benchmark")


def _require_child_code_identity(
    event: Mapping[str, object],
    event_name: str,
    expected: Mapping[str, str],
) -> None:
    """Require lifecycle evidence from the same exact checkout identity."""
    identity = event.get("code_identity")
    if not isinstance(identity, Mapping) or dict(identity) != dict(expected):
        raise ValueError(f"worker {event_name} code identity does not match parent")


def summarize_ms(values: Iterable[float]) -> dict[str, int | float]:
    """Summarize milliseconds with deterministic nearest-rank percentiles."""
    ordered = sorted(float(value) for value in values)
    if not ordered:
        raise ValueError("timing values must not be empty")
    if any(not math.isfinite(value) or value < 0.0 for value in ordered):
        raise ValueError("timing values must be finite and non-negative")
    count = len(ordered)
    return {
        "count": count,
        "p50": ordered[math.ceil(0.50 * count) - 1],
        "p95": ordered[math.ceil(0.95 * count) - 1],
        "max": ordered[-1],
    }


def build_benchmark_report(
    ready_event: Mapping[str, object],
    measured_events: Iterable[Mapping[str, object]],
    *,
    artifacts: Mapping[str, str] | None = None,
) -> dict[str, object]:
    """Build a deterministic report from one ready event and measured results."""
    if ready_event.get("type") != "ready":
        raise ValueError("benchmark requires exactly one ready event")
    device = _non_empty_string(ready_event.get("device"), "ready device")
    startup_metrics = ready_event.get("startup_metrics")
    if not isinstance(startup_metrics, Mapping):
        raise ValueError("ready startup_metrics must be an object")
    if startup_metrics.get("device") != device:
        raise ValueError("startup device does not match ready device")
    if device == "cuda:0" and startup_metrics.get("fallback_reason") is not None:
        raise ValueError("benchmark rejects CUDA fallback")

    results: list[Mapping[str, object]] = []
    for event in measured_events:
        event_type = event.get("type")
        if event_type in STARTUP_EVENT_TYPES:
            raise ValueError("a startup event appeared during measured runs")
        if event_type != "result":
            raise ValueError(f"unexpected measured event type: {event_type}")
        results.append(event)
    validate_run_count(len(results))

    timing_values: dict[str, list[float]] = {
        stage: [] for stage in EXPECTED_TIMING_STAGES
    }
    request_ids: set[str] = set()
    for result in results:
        if result.get("device") != device:
            raise ValueError("result device changed during benchmark")
        request_id = _non_empty_string(result.get("request_id"), "result request_id")
        if request_id in request_ids:
            raise ValueError("benchmark result request_id is duplicated")
        request_ids.add(request_id)
        timings = result.get("timings_ms")
        if not isinstance(timings, Mapping) or set(timings) != set(
            EXPECTED_TIMING_STAGES
        ):
            raise ValueError("result timings_ms stages do not match worker contract")
        for stage in EXPECTED_TIMING_STAGES:
            value = timings[stage]
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(f"{stage} timing must be numeric")
            timing_values[stage].append(float(value))

    if device == "cuda:0":
        receipt = build_receipt(
            ready_event,
            _grouped_gpu_samples(results),
            artifacts=artifacts,
        )
        payload = receipt.to_payload()
        summaries = payload["summaries"]
        assert isinstance(summaries, Mapping)
        payload["groups"] = summaries["groups"]
        payload["overall"] = summaries["overall"]
        return payload

    return {
        "schema_version": 1,
        "device": device,
        "model_ids": {
            "detector": _non_empty_string(
                startup_metrics.get("detector_id"), "detector_id"
            ),
            "repvit": _non_empty_string(
                startup_metrics.get("repvit_id"), "repvit_id"
            ),
            "dinov3": _non_empty_string(
                startup_metrics.get("dinov3_id"), "dinov3_id"
            ),
        },
        "policy_id": _non_empty_string(
            startup_metrics.get("fusion_policy_id"), "fusion_policy_id"
        ),
        "detector_threshold": _finite_non_negative(
            startup_metrics.get("detector_threshold"), "detector_threshold"
        ),
        "startup": {
            "load_ms": _finite_non_negative(
                startup_metrics.get("load_ms"), "startup load_ms"
            ),
            "warmup_ms": _finite_non_negative(
                startup_metrics.get("warmup_ms"), "startup warmup_ms"
            ),
            "fallback_reason": _optional_string(
                startup_metrics.get("fallback_reason"), "fallback_reason"
            ),
        },
        "run_count": len(results),
        "timings_ms": {
            stage: summarize_ms(timing_values[stage])
            for stage in EXPECTED_TIMING_STAGES
        },
    }


def _grouped_gpu_samples(
    results: Sequence[Mapping[str, object]],
) -> dict[str, list[dict[str, object]]]:
    grouped: dict[str, list[dict[str, object]]] = {"E": [], "M": [], "H": []}
    for result in results:
        diagnostics = result.get("diagnostics")
        if not isinstance(diagnostics, Mapping) or set(diagnostics) != {
            "object_count", "dino_object_count"
        }:
            raise ValueError("result diagnostics do not match worker contract")
        group = result.get("group")
        if group not in grouped:
            raise ValueError("GPU benchmark result group is invalid")
        grouped[group].append(
            {
                "request_id": result.get("request_id"),
                "image_id": result.get("image_id"),
                "group": group,
                "image_sha256": result.get("image_sha256"),
                "object_count": diagnostics["object_count"],
                "dino_object_count": diagnostics["dino_object_count"],
                "timings_ms": result.get("timings_ms"),
            }
        )
    return grouped


class _WorkerProcess:
    def __init__(self, command: Sequence[str], diagnostics: TextIO) -> None:
        self._process = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=diagnostics,
            text=True,
            encoding="utf-8",
            bufsize=1,
        )
        if self._process.stdin is None or self._process.stdout is None:
            self._process.kill()
            raise RuntimeError("worker pipes could not be opened")
        self._events: queue.Queue[object] = queue.Queue()
        self._reader = threading.Thread(target=self._read_stdout, daemon=True)
        self._reader.start()

    def _read_stdout(self) -> None:
        assert self._process.stdout is not None
        try:
            for line in self._process.stdout:
                self._events.put(line)
        finally:
            self._events.put(_EOF)

    def send(self, event: Mapping[str, object]) -> None:
        if self._process.poll() is not None:
            raise RuntimeError(f"worker exited with code {self._process.returncode}")
        assert self._process.stdin is not None
        self._process.stdin.write(
            json.dumps(event, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            + "\n"
        )
        self._process.stdin.flush()

    def receive(self, timeout_seconds: float) -> dict[str, object]:
        try:
            item = self._events.get(timeout=timeout_seconds)
        except queue.Empty as exc:
            raise RuntimeError("timed out waiting for worker event") from exc
        if item is _EOF:
            raise RuntimeError(
                f"worker stdout closed with exit code {self._process.poll()}"
            )
        assert isinstance(item, str)
        try:
            event = json.loads(item)
        except json.JSONDecodeError as exc:
            raise RuntimeError("worker emitted malformed JSON") from exc
        if not isinstance(event, dict) or not isinstance(event.get("type"), str):
            raise RuntimeError("worker event must be an object with a type")
        return event

    def wait(self, timeout_seconds: float) -> int:
        try:
            return self._process.wait(timeout=timeout_seconds)
        except subprocess.TimeoutExpired:
            self._process.kill()
            self._process.wait()
            raise RuntimeError("worker did not exit after shutdown")

    def abort(self) -> None:
        if self._process.poll() is None:
            self._process.kill()
            self._process.wait()


def run_grouped_benchmark(
    *,
    python_executable: Path,
    repo_root: Path,
    manifest_path: Path,
    protocol_path: Path,
    startup_timeout_seconds: float = 900.0,
    analysis_timeout_seconds: float = 600.0,
) -> dict[str, object]:
    """Run fixed warmups and 100 deterministic measurements for E, M, and H."""
    samples, manifest_sha256 = load_external_manifest(manifest_path)
    protocol, protocol_sha256 = load_benchmark_protocol(protocol_path)
    python_path = Path(python_executable).resolve()
    root = _bound_repository_root(repo_root)
    if not python_path.is_file():
        raise ValueError(f"Python executable is missing: {python_path}")
    if not root.is_dir():
        raise ValueError(f"repository root is missing: {root}")
    code_identity = resolve_code_identity(root)
    staging = tempfile.TemporaryDirectory(prefix="bakery-camera-evidence-")
    try:
        snapshot = _stage_parent_snapshot(root, Path(staging.name) / "checkout")
        if (
            _compute_code_identity(snapshot, commit=code_identity["code_commit"])
            != code_identity
        ):
            raise ValueError("benchmark source changed while creating staged snapshot")
        entrypoint = snapshot / _STAGED_ENTRYPOINT
        entrypoint_sha256 = hashlib.sha256(entrypoint.read_bytes()).hexdigest()
        command = (
            str(python_path),
            "-u",
            "-c",
            _STAGED_BOOTSTRAP,
            str(entrypoint),
            entrypoint_sha256,
            "--repo-root",
            str(root),
            "--staged-root",
            str(snapshot),
            "--code-commit",
            code_identity["code_commit"],
            "--code-identity-sha256",
            code_identity["code_identity_sha256"],
            "--device",
            "cuda",
            "--warmup-image",
            samples[0]["image_path"],
            "--allow-external-warmup",
        )
        samples_by_group = {
            group: tuple(sample for sample in samples if sample["group"] == group)
            for group in ("E", "M", "H")
        }
        with tempfile.TemporaryFile(mode="w+", encoding="utf-8") as diagnostics:
            worker = _WorkerProcess(command, diagnostics)
            try:
                ready = _wait_for_ready(worker, startup_timeout_seconds)
                if ready.get("device") != protocol["device"]:
                    raise RuntimeError("worker did not start on protocol CUDA device")
                _require_child_code_identity(ready, "ready", code_identity)
                for index in range(int(protocol["minimum_warmups"])):
                    sample = samples[index % len(samples)]
                    _analyze_sample(
                        worker, sample, f"warmup-{index + 1:04d}", analysis_timeout_seconds
                    )
                measured: list[Mapping[str, object]] = []
                for group in ("E", "M", "H"):
                    group_samples = samples_by_group[group]
                    for index in range(int(protocol["minimum_group_observations"])):
                        sample = group_samples[index % len(group_samples)]
                        measured.append(
                            _analyze_sample(
                                worker,
                                sample,
                                f"benchmark-{group}-{index + 1:04d}",
                                analysis_timeout_seconds,
                            )
                        )
                worker.send({"type": "shutdown", "request_id": "benchmark-shutdown"})
                stopped = worker.receive(analysis_timeout_seconds)
                if (
                    stopped.get("type") != "stopped"
                    or stopped.get("request_id") != "benchmark-shutdown"
                ):
                    raise RuntimeError("worker did not acknowledge shutdown")
                _require_child_code_identity(stopped, "stopped", code_identity)
                if worker.wait(30.0) != 0:
                    raise RuntimeError("worker exited with a non-zero status")
                _require_stable_code_identity(root, code_identity)
                return build_benchmark_report(
                    ready,
                    measured,
                    artifacts={
                        "benchmark_manifest_sha256": manifest_sha256,
                        "benchmark_protocol_sha256": protocol_sha256,
                        **code_identity,
                    },
                )
            except Exception as exc:
                worker.abort()
                diagnostics.seek(0)
                detail = diagnostics.read().strip()
                if detail:
                    exc.add_note(f"worker diagnostics:\n{detail[-8000:]}")
                raise
    finally:
        staging.cleanup()


def _analyze_sample(
    worker: _WorkerProcess,
    sample: Mapping[str, str],
    request_id: str,
    timeout_seconds: float,
) -> dict[str, object]:
    worker.send(
        {"type": "analyze", "request_id": request_id, "image_path": sample["image_path"]}
    )
    result = _wait_for_result(worker, request_id, timeout_seconds)
    return {
        **result,
        "image_id": sample["image_id"],
        "group": sample["group"],
        "image_sha256": sample["image_sha256"],
    }


def run_benchmark(
    *,
    python_executable: Path,
    repo_root: Path,
    device: str,
    image_path: Path,
    run_count: int,
    startup_timeout_seconds: float = 900.0,
    analysis_timeout_seconds: float = 600.0,
) -> dict[str, object]:
    """Start, warm, benchmark, and cleanly stop one persistent worker."""
    validate_run_count(run_count)
    python_path = Path(python_executable).resolve()
    root = _bound_repository_root(repo_root)
    image = Path(image_path).resolve()
    if not python_path.is_file():
        raise ValueError(f"Python executable is missing: {python_path}")
    if not root.is_dir():
        raise ValueError(f"repository root is missing: {root}")
    if not image.is_file():
        raise ValueError(f"benchmark image is missing: {image}")
    try:
        image.relative_to(root)
    except ValueError as exc:
        raise ValueError("benchmark image must remain under repository root") from exc
    worker_script = root / "scripts" / "run_camera_inference_worker.py"
    if not worker_script.is_file():
        raise ValueError(f"camera worker script is missing: {worker_script}")
    command = (
        str(python_path),
        "-u",
        str(worker_script),
        "--repo-root",
        str(root),
        "--device",
        device,
        "--warmup-image",
        str(image),
    )

    with tempfile.TemporaryFile(mode="w+", encoding="utf-8") as diagnostics:
        worker = _WorkerProcess(command, diagnostics)
        try:
            ready = _wait_for_ready(worker, startup_timeout_seconds)
            measured: list[Mapping[str, object]] = []
            for index in range(1, run_count + 1):
                request_id = f"benchmark-{index:04d}"
                worker.send(
                    {
                        "type": "analyze",
                        "request_id": request_id,
                        "image_path": str(image),
                    }
                )
                measured.append(
                    _wait_for_result(worker, request_id, analysis_timeout_seconds)
                )
            worker.send({"type": "shutdown", "request_id": "benchmark-shutdown"})
            stopped = worker.receive(analysis_timeout_seconds)
            if stopped != {"type": "stopped", "request_id": "benchmark-shutdown"}:
                raise RuntimeError("worker did not acknowledge shutdown")
            exit_code = worker.wait(30.0)
            if exit_code != 0:
                raise RuntimeError(f"worker exited with code {exit_code}")
            report = build_benchmark_report(ready, measured)
            report["image"] = str(image)
            return report
        except Exception as exc:
            worker.abort()
            diagnostics.seek(0)
            detail = diagnostics.read().strip()
            if detail:
                exc.add_note(f"worker diagnostics:\n{detail[-8000:]}")
            raise


def _wait_for_ready(worker: _WorkerProcess, timeout_seconds: float) -> dict[str, object]:
    seen: set[str] = set()
    while True:
        event = worker.receive(timeout_seconds)
        event_type = event["type"]
        if event_type == "fatal":
            raise RuntimeError(f"worker initialization failed: {event.get('message')}")
        if event_type == "ready":
            if seen != {"loading", "warming"}:
                raise RuntimeError("worker startup events were incomplete or out of order")
            return event
        if event_type not in {"loading", "warming"} or event_type in seen:
            raise RuntimeError(f"unexpected worker startup event: {event_type}")
        if event_type == "warming" and seen != {"loading"}:
            raise RuntimeError("worker warming event was out of order")
        seen.add(event_type)


def _wait_for_result(
    worker: _WorkerProcess, request_id: str, timeout_seconds: float
) -> dict[str, object]:
    phases: list[str] = []
    while True:
        event = worker.receive(timeout_seconds)
        event_type = event["type"]
        if event_type in STARTUP_EVENT_TYPES:
            raise RuntimeError("worker emitted a second startup event")
        if event.get("request_id") != request_id:
            raise RuntimeError("worker event request_id does not match active run")
        if event_type == "error":
            raise RuntimeError(f"worker analysis failed: {event.get('message')}")
        if event_type == "progress":
            phase = event.get("phase")
            if not isinstance(phase, str):
                raise RuntimeError("worker progress phase is invalid")
            phases.append(phase)
            continue
        if event_type != "result":
            raise RuntimeError(f"unexpected analysis event: {event_type}")
        legal = ["detecting", "classifying", "aggregating"]
        legal_recheck = ["detecting", "classifying", "rechecking", "aggregating"]
        if phases not in (legal, legal_recheck):
            raise RuntimeError("worker progress phases were incomplete or out of order")
        return event


def _non_empty_string(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{label} must be a non-empty string")
    return value


def _optional_string(value: object, label: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise ValueError(f"{label} must be null or a non-empty string")
    return value


def _sha256(value: object, label: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise ValueError(f"{label} must be a lowercase SHA-256")
    return value


def _finite_non_negative(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be numeric")
    number = float(value)
    if not math.isfinite(number) or number < 0.0:
        raise ValueError(f"{label} must be finite and non-negative")
    return number


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python", type=Path, default=Path(sys.executable))
    parser.add_argument("--repo-root", required=True, type=Path)
    parser.add_argument("--device", choices=("auto", "cuda", "cpu"), default="auto")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--image", type=Path)
    source.add_argument("--manifest", type=Path)
    parser.add_argument("--protocol", type=Path)
    parser.add_argument("--runs", type=int, default=MINIMUM_MEASURED_RUNS)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    if args.manifest is not None:
        if args.protocol is None:
            raise ValueError("--protocol is required with --manifest")
        if args.device != "cuda":
            raise ValueError("grouped GPU receipt requires --device cuda")
        report = run_grouped_benchmark(
            python_executable=args.python,
            repo_root=args.repo_root,
            manifest_path=args.manifest,
            protocol_path=args.protocol,
        )
    else:
        if args.protocol is not None:
            raise ValueError("--protocol requires --manifest")
        assert args.image is not None
        report = run_benchmark(
            python_executable=args.python,
            repo_root=args.repo_root,
            device=args.device,
            image_path=args.image,
            run_count=args.runs,
        )
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, ensure_ascii=False, allow_nan=False, indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
