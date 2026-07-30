"""Read and verify the repository-wide external artifact lock."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
from typing import Literal


_SHA256 = re.compile(r"^[0-9a-f]{64}$")
Storage = Literal["external", "git", "git-lfs", "github-release"]


class ArtifactIntegrityError(ValueError):
    """Raised when a declared artifact is missing or fails integrity checks."""


@dataclass(frozen=True, slots=True)
class ArtifactRecord:
    artifact_id: str
    kind: str
    local_path: PurePosixPath
    sha256: str
    bytes: int
    storage: Storage
    uri_env: str | None = None


@dataclass(frozen=True, slots=True)
class ArtifactVerification:
    artifact_id: str
    path: Path
    status: Literal["verified", "missing"]


@dataclass(frozen=True, slots=True)
class ArtifactVerificationReport:
    items: tuple[ArtifactVerification, ...]

    @property
    def complete(self) -> bool:
        return all(item.status == "verified" for item in self.items)


@dataclass(frozen=True, slots=True)
class ArtifactLock:
    schema_version: int
    canonical_pipeline: str
    artifacts: tuple[ArtifactRecord, ...]

    @classmethod
    def load(cls, path: str | Path) -> "ArtifactLock":
        lock_path = Path(path)
        payload = json.loads(lock_path.read_text(encoding="utf-8"))
        if payload.get("schema_version") != 1:
            raise ValueError("artifact lock schema_version must be 1")
        pipeline = payload.get("canonical_pipeline")
        if not isinstance(pipeline, str) or not pipeline:
            raise ValueError("canonical_pipeline must be a non-empty string")
        raw_artifacts = payload.get("artifacts")
        if not isinstance(raw_artifacts, list) or not raw_artifacts:
            raise ValueError("artifacts must be a non-empty list")

        records: list[ArtifactRecord] = []
        seen: set[str] = set()
        for raw in raw_artifacts:
            if not isinstance(raw, dict):
                raise ValueError("artifact entries must be objects")
            artifact_id = raw.get("id")
            if not isinstance(artifact_id, str) or not artifact_id or artifact_id in seen:
                raise ValueError("artifact ids must be unique non-empty strings")
            seen.add(artifact_id)
            kind = raw.get("kind")
            if not isinstance(kind, str) or not kind:
                raise ValueError(f"{artifact_id}: kind must be a non-empty string")
            local_path = _relative_path(raw.get("local_path"), artifact_id)
            sha256 = raw.get("sha256")
            if not isinstance(sha256, str) or not _SHA256.fullmatch(sha256):
                raise ValueError(f"{artifact_id}: sha256 must be lowercase SHA-256")
            size = raw.get("bytes")
            if not isinstance(size, int) or isinstance(size, bool) or size < 0:
                raise ValueError(f"{artifact_id}: bytes must be a non-negative integer")
            storage = raw.get("storage")
            if storage not in {"external", "git", "git-lfs", "github-release"}:
                raise ValueError(f"{artifact_id}: unsupported storage")
            uri_env = raw.get("uri_env")
            if uri_env is not None and (not isinstance(uri_env, str) or not uri_env):
                raise ValueError(f"{artifact_id}: uri_env must be a non-empty string")
            if storage == "git" and uri_env is not None:
                raise ValueError(f"{artifact_id}: Git-owned artifacts cannot use uri_env")
            records.append(
                ArtifactRecord(
                    artifact_id=artifact_id,
                    kind=kind,
                    local_path=local_path,
                    sha256=sha256,
                    bytes=size,
                    storage=storage,
                    uri_env=uri_env,
                )
            )
        return cls(1, pipeline, tuple(records))

    def verify(
        self,
        root: str | Path,
        *,
        require_all: bool = True,
    ) -> ArtifactVerificationReport:
        repository = Path(root).resolve()
        results: list[ArtifactVerification] = []
        for artifact in self.artifacts:
            path = repository.joinpath(*artifact.local_path.parts)
            if not path.is_file():
                if require_all:
                    raise ArtifactIntegrityError(
                        f"{artifact.artifact_id}: artifact is missing: {artifact.local_path}"
                    )
                results.append(
                    ArtifactVerification(artifact.artifact_id, path, "missing")
                )
                continue
            actual_size = path.stat().st_size
            if actual_size != artifact.bytes:
                raise ArtifactIntegrityError(
                    f"{artifact.artifact_id}: byte size mismatch "
                    f"(expected {artifact.bytes}, got {actual_size})"
                )
            actual_hash = _sha256(path)
            if actual_hash != artifact.sha256:
                raise ArtifactIntegrityError(
                    f"{artifact.artifact_id}: SHA-256 mismatch "
                    f"(expected {artifact.sha256}, got {actual_hash})"
                )
            results.append(
                ArtifactVerification(artifact.artifact_id, path, "verified")
            )
        return ArtifactVerificationReport(tuple(results))


def _relative_path(value: object, artifact_id: str) -> PurePosixPath:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{artifact_id}: local_path must be a non-empty string")
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or "\\" in value:
        raise ValueError(f"{artifact_id}: local_path must be repository-relative POSIX")
    return path


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
