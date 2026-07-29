"""Benchmark one persistent camera worker after its one-time warm-up."""

from __future__ import annotations

import argparse
import json
import math
import queue
import subprocess
import sys
import tempfile
import threading
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import TextIO


MINIMUM_MEASURED_RUNS = 20
STARTUP_EVENT_TYPES = frozenset({"loading", "warming", "ready"})
EXPECTED_TIMING_STAGES = (
    "decode_preprocess",
    "detector",
    "repvit",
    "dinov3",
    "postprocess",
    "total",
)
_EOF = object()


def validate_run_count(run_count: int) -> int:
    """Return a valid measured-run count, rejecting undersized samples."""
    if isinstance(run_count, bool) or not isinstance(run_count, int):
        raise ValueError("run count must be an integer")
    if run_count < MINIMUM_MEASURED_RUNS:
        raise ValueError(f"benchmark requires at least {MINIMUM_MEASURED_RUNS} runs")
    return run_count


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
    root = Path(repo_root).resolve()
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
    parser.add_argument("--image", required=True, type=Path)
    parser.add_argument("--runs", type=int, default=MINIMUM_MEASURED_RUNS)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
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
