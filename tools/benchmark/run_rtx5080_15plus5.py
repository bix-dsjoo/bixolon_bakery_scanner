"""Run the admitted RTX 5080 15+5 path benchmark or record unverified state."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Sequence

from bakery_scanner.benchmarking.rtx5080_acceptance import validate_protocol


_REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
_QUALITY_PASS = "quality-passed-performance-unverified"


def write_unverified_checkpoint(
    compact_output: Path,
    summary: Path,
    *,
    status: str,
    missing_inputs: Sequence[str],
) -> dict[str, object]:
    """Write an explicit no-measurement checkpoint without latency numbers."""
    if not isinstance(status, str) or not status.startswith("unverified_"):
        raise ValueError("checkpoint status must be explicitly unverified")
    normalized = tuple(sorted(set(missing_inputs)))
    if not normalized or any(not isinstance(item, str) or not item for item in normalized):
        raise ValueError("unverified checkpoint requires exact missing inputs")
    base: dict[str, object] = {
        "schema_version": 3,
        "status": status,
        "performance_status": "unverified",
        "missing_inputs": list(normalized),
    }
    encoded = _canonical_bytes(base)
    payload = {**base, "receipt_sha256": hashlib.sha256(encoded).hexdigest()}
    compact = Path(compact_output)
    report = Path(summary)
    compact.parent.mkdir(parents=True, exist_ok=True)
    report.parent.mkdir(parents=True, exist_ok=True)
    compact.write_bytes(_canonical_bytes(payload))
    report.write_text(
        "# RTX 5080 15+5 p95 checkpoint\n\n"
        f"Status: `{status}`\n\n"
        "No warmed latency samples were admitted, so performance remains unverified.\n\n"
        "Missing or unverified inputs:\n\n"
        + "".join(f"- `{item}`\n" for item in normalized),
        encoding="utf-8",
    )
    return payload


def find_unverified_inputs(
    *,
    dataset_root: Path,
    splits: Path,
    config: Path,
    runtime_manifest: Path,
    artifact_root: Path,
    protocol: Path,
    quality_receipt: Path,
) -> tuple[str, ...]:
    """Resolve the external boundaries required before any timing can start."""
    checks = {
        "dataset_root": Path(dataset_root).is_dir(),
        "splits": Path(splits).is_dir()
        and all((Path(splits) / f"fold-{fold}.json").is_file() for fold in range(5))
        and (Path(splits) / "inventory.json").is_file(),
        "candidate_config": Path(config).is_file(),
        "runtime_manifest": Path(runtime_manifest).is_file(),
        "artifact_root": Path(artifact_root).is_dir(),
        "benchmark_protocol": _is_canonical_protocol(Path(protocol)),
        "quality_receipt": _is_accepted_quality_receipt(Path(quality_receipt)),
    }
    return tuple(sorted(label for label, valid in checks.items() if not valid))


def _is_accepted_quality_receipt(path: Path) -> bool:
    if not path.is_file():
        return False
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return False
    if not (
        isinstance(payload, dict)
        and payload.get("status") == _QUALITY_PASS
        and _is_sha256(payload.get("receipt_sha256"))
    ):
        return False
    claimed = payload.pop("receipt_sha256")
    return claimed == hashlib.sha256(_canonical_bytes(payload)).hexdigest()


def _is_canonical_protocol(path: Path) -> bool:
    if not path.is_file():
        return False
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        validate_protocol(payload)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError):
        return False
    return True


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _is_sha256(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-root", required=True, type=Path)
    parser.add_argument("--splits", required=True, type=Path)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--runtime-manifest", required=True, type=Path)
    parser.add_argument("--artifact-root", required=True, type=Path)
    parser.add_argument("--protocol", required=True, type=Path)
    parser.add_argument(
        "--quality-receipt",
        type=Path,
        default=_REPOSITORY_ROOT / "benchmarks/results/rtx5080_15plus5_oof_v1.json",
    )
    parser.add_argument("--raw-output", required=True, type=Path)
    parser.add_argument("--compact-output", required=True, type=Path)
    parser.add_argument("--summary", required=True, type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    missing = find_unverified_inputs(
        dataset_root=arguments.dataset_root,
        splits=arguments.splits,
        config=arguments.config,
        runtime_manifest=arguments.runtime_manifest,
        artifact_root=arguments.artifact_root,
        protocol=arguments.protocol,
        quality_receipt=arguments.quality_receipt,
    )
    if missing:
        write_unverified_checkpoint(
            arguments.compact_output,
            arguments.summary,
            status="unverified_missing_artifacts",
            missing_inputs=missing,
        )
        return 2

    # The concrete engine-session provider is an external release artifact.
    # This repository must never substitute PyTorch, CPU, cached, or supplied
    # timing rows when that provider is absent.
    write_unverified_checkpoint(
        arguments.compact_output,
        arguments.summary,
        status="unverified_runtime_provider_unavailable",
        missing_inputs=("admitted_rtx5080_engine_session_provider",),
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
