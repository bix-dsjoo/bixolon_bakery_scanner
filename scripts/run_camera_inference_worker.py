"""Entrypoint for the persistent camera-inference JSON Lines worker."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Callable, Sequence, TextIO


_ATTESTED_TREES = ("src", "dino", "data", "configs", "policies")
_ATTESTED_FILES = (
    "pyproject.toml",
    "models/rfdetr_large_bakery_v1/manifest.json",
    "scripts/run_camera_inference_worker.py",
)
_DEPLOYED_ATTESTED_TREES = ("src/bakery_scanner", "dino/dinov3")
_DEPLOYED_ATTESTED_FILES = (
    "pyproject.toml",
    "scripts/run_camera_inference_worker.py",
    "data/catalogs/classes.json",
    "configs/gpu_rfdetr_classifier_policy.yaml",
    "configs/cpu_rfdetr_classifier_policy.yaml",
    "models/rfdetr_large_bakery_v1/manifest.json",
    "policies/presentation/camera_action_state_v2.json",
    "policies/classification/policy_v2_manifest_rebound_cpu_smoke.json",
    "policies/classification/fusion_local_or_global_consensus_margin_v1.json",
)
_DEPLOYED_IDENTITY_FILE = "worker-identity.json"
_DEPLOYED_IDENTITY_KEYS = {
    "schema_version",
    "code_commit",
    "code_identity_sha256",
}
_CANDIDATE_PROFILE = "rtx5080_15plus5_single_frame_v1"
_LEGACY_PROFILE = "legacy"


def serve_selected_runtime(
    *,
    stdin: TextIO,
    stdout: TextIO,
    runtime_factory: Callable[[Callable[[str, str | None], None]], object],
    code_identity: dict[str, str],
    runtime_profile: str,
    candidate_provider_factory: Callable[[], object],
    serve_fn: Callable[..., int],
) -> int:
    """Forward one explicit launch selection to the worker without fallback."""
    if runtime_profile == _CANDIDATE_PROFILE:
        candidate_provider = candidate_provider_factory()
    elif runtime_profile == _LEGACY_PROFILE:
        candidate_provider = None
    else:
        raise ValueError("unsupported camera runtime profile")
    return serve_fn(
        stdin,
        stdout,
        runtime_factory=runtime_factory,
        code_identity=code_identity,
        runtime_profile_id=runtime_profile,
        candidate_runtime_provider=candidate_provider,
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
    return _compute_code_identity(
        root,
        commit=commit,
        trees=_ATTESTED_TREES,
        files=_ATTESTED_FILES,
    )


def compute_deployed_worker_code_identity(root: Path, *, commit: str) -> dict[str, str]:
    """Hash the exact source/config/policy bytes included in a portable payload."""
    return _compute_code_identity(
        root,
        commit=commit,
        trees=_DEPLOYED_ATTESTED_TREES,
        files=_DEPLOYED_ATTESTED_FILES,
    )


def deployed_worker_identity_paths() -> tuple[str, ...]:
    """Return the committed paths whose bytes define a deployed worker."""
    return _DEPLOYED_ATTESTED_TREES + _DEPLOYED_ATTESTED_FILES


def _compute_code_identity(
    root: Path,
    *,
    commit: str,
    trees: Sequence[str],
    files: Sequence[str],
) -> dict[str, str]:
    if len(commit) not in (40, 64) or any(char not in "0123456789abcdef" for char in commit):
        raise ValueError("worker checkout commit is invalid")
    base = Path(root).resolve()
    records: list[str] = []
    try:
        for relative in trees:
            tree = base / relative
            if not tree.is_dir():
                raise ValueError(f"worker attested tree is missing: {tree}")
            for path in sorted(
                (candidate for candidate in tree.rglob("*") if candidate.is_file()),
                key=lambda candidate: candidate.relative_to(base).as_posix(),
            ):
                records.append(_identity_record(base, path))
        for relative in files:
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


def load_deployed_worker_identity(root: Path) -> dict[str, str] | None:
    """Load the package-only worker identity, if this is a deployed pipeline."""
    identity_path = Path(root).resolve() / _DEPLOYED_IDENTITY_FILE
    if not identity_path.exists():
        return None
    if not identity_path.is_file():
        raise ValueError("deployed worker identity is not a file")
    try:
        payload = json.loads(identity_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("deployed worker identity is invalid") from exc
    if not isinstance(payload, dict) or set(payload) != _DEPLOYED_IDENTITY_KEYS:
        raise ValueError("deployed worker identity has invalid fields")
    if payload.get("schema_version") != 1:
        raise ValueError("deployed worker identity schema_version must be 1")
    commit = payload.get("code_commit")
    identity = payload.get("code_identity_sha256")
    if not isinstance(commit, str) or not isinstance(identity, str):
        raise ValueError("deployed worker identity values are invalid")
    if len(identity) != 64 or any(char not in "0123456789abcdef" for char in identity):
        raise ValueError("deployed worker identity SHA-256 is invalid")
    return {
        "code_commit": commit,
        "code_identity_sha256": identity,
    }


def resolve_worker_execution_root(
    repo_root: Path,
    temporary_root: Path,
) -> tuple[Path, dict[str, str]]:
    """Use a verified deployed pipeline or preserve the clean-checkout snapshot."""
    root = Path(repo_root).resolve()
    deployed_identity = load_deployed_worker_identity(root)
    if deployed_identity is None:
        return _capture_child_snapshot(root, temporary_root / "checkout")
    actual_identity = compute_deployed_worker_code_identity(
        root,
        commit=deployed_identity["code_commit"],
    )
    if actual_identity != deployed_identity:
        raise ValueError("deployed worker code identity does not match package")
    return root, actual_identity


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
    parser.add_argument(
        "--runtime-profile",
        choices=(_CANDIDATE_PROFILE, _LEGACY_PROFILE),
        default=_CANDIDATE_PROFILE,
    )
    parser.add_argument("--warmup-image", required=True, type=Path)
    parser.add_argument("--allow-external-warmup", action="store_true")
    parser.add_argument("--staged-root", type=Path)
    parser.add_argument("--code-commit")
    parser.add_argument("--code-identity-sha256")
    args = parser.parse_args(argv)
    try:
        root, warmup_image = resolve_paths(
            args.repo_root,
            args.warmup_image,
            allow_external_warmup=args.allow_external_warmup,
        )
    except ValueError as exc:
        parser.error(str(exc))

    has_staged_root = args.staged_root is not None
    has_complete_identity = (
        args.code_commit is not None and args.code_identity_sha256 is not None
    )
    if has_staged_root != has_complete_identity:
        parser.error(
            "--staged-root requires --code-commit and --code-identity-sha256"
        )
    with tempfile.TemporaryDirectory(prefix="bakery-camera-worker-") as temporary:
        try:
            if args.staged_root is None:
                snapshot, code_identity = resolve_worker_execution_root(
                    root, Path(temporary)
                )
            else:
                snapshot = Path(args.staged_root).resolve()
                expected = {
                    "code_commit": args.code_commit,
                    "code_identity_sha256": args.code_identity_sha256,
                }
                code_identity = compute_worker_code_identity(
                    snapshot, commit=args.code_commit
                )
                if code_identity != expected:
                    raise ValueError("staged worker code identity does not match parent")
            source_root, dino_root = resolve_import_roots(snapshot)
        except ValueError as exc:
            parser.error(str(exc))
        sys.path.insert(0, str(dino_root))
        sys.path.insert(0, str(source_root))
        from bakery_scanner.prototype.camera_runtime import CameraInferenceRuntime
        from bakery_scanner.prototype.camera_runtime import CandidateAdmissionFailed
        from bakery_scanner.prototype.camera_worker import serve

        def runtime_factory(emit):
            return CameraInferenceRuntime.initialize(
                snapshot,
                warmup_image,
                preference=args.device,
                on_startup=emit,
                artifact_root=root,
            )

        class CandidateAdmissionProvider:
            """Fail closed until the externally admitted engine runtime is staged."""

            def admit(self):
                manifest = (
                    root
                    / "artifacts"
                    / "rtx5080_15plus5_single_frame_v1"
                    / "admission.json"
                )
                if not manifest.is_file():
                    raise CandidateAdmissionFailed(
                        "admission_failed: candidate admission manifest is unavailable; "
                        "no fallback"
                    )
                raise CandidateAdmissionFailed(
                    "admission_failed: candidate engine-session provider is unavailable; "
                    "no fallback"
                )

            def load(self, receipt):
                del receipt
                raise CandidateAdmissionFailed(
                    "admission_failed: candidate runtime was not admitted; no fallback"
                )

        return serve_selected_runtime(
            stdin=sys.stdin,
            stdout=sys.stdout,
            runtime_factory=runtime_factory,
            code_identity=code_identity,
            runtime_profile=args.runtime_profile,
            candidate_provider_factory=CandidateAdmissionProvider,
            serve_fn=serve,
        )


if __name__ == "__main__":
    raise SystemExit(main())
