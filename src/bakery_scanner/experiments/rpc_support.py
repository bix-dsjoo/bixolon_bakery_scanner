"""Deterministic support ordering for nested RPC few-shot experiments."""

from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass
from numbers import Real
from typing import Iterable

from bakery_scanner.experiments.rpc_manifest import canonical_json_bytes


_TRAIN_CAPTURE_NAME = re.compile(
    r"^(?P<product_identity>.+)_camera(?P<camera>[0-9]+)-(?P<side>[^_]+)\.jpg$"
)
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
CaptureStratum = tuple[int, str, str, int]


@dataclass(frozen=True, slots=True)
class SupportCandidate:
    """An externally produced, hash-identified support image and embedding."""

    category_id: int
    source_identity: str
    source_file_name: str
    image_sha256: str
    source_byte_size: int
    capture_stratum: CaptureStratum
    embedding: tuple[float, ...]

    def __post_init__(self) -> None:
        if type(self.category_id) is not int or self.category_id <= 0:
            raise ValueError("candidate category ID must be positive")
        if not isinstance(self.source_identity, str) or not self.source_identity:
            raise ValueError("candidate source identity must be non-empty")
        if not isinstance(self.source_file_name, str) or not self.source_file_name:
            raise ValueError("candidate source file name must be non-empty")
        if not isinstance(self.image_sha256, str) or _SHA256.fullmatch(self.image_sha256) is None:
            raise ValueError("candidate image SHA-256 must be lowercase SHA-256")
        if type(self.source_byte_size) is not int or self.source_byte_size <= 0:
            raise ValueError("candidate source byte size must be positive")
        _validate_capture_stratum(self.capture_stratum, self.category_id)
        if self.capture_stratum != parse_train_capture_stratum(self.source_file_name, self.category_id):
            raise ValueError("capture stratum mismatch")
        if isinstance(self.embedding, (str, bytes)):
            raise ValueError("candidate embedding must be a finite numeric 1-D sequence")
        try:
            raw_values = tuple(self.embedding)
        except (TypeError, ValueError) as exc:
            raise ValueError("candidate embedding must be a finite numeric 1-D sequence") from exc
        if not raw_values or any(isinstance(value, bool) or not isinstance(value, Real) for value in raw_values):
            raise ValueError("candidate embedding must be a finite numeric 1-D sequence")
        values = tuple(float(value) for value in raw_values)
        if not all(math.isfinite(value) for value in values):
            raise ValueError("candidate embedding must be a finite numeric 1-D sequence")
        object.__setattr__(self, "embedding", values)


@dataclass(frozen=True, slots=True)
class SupportOrder:
    """A complete immutable order from which all few-shot prefixes are drawn."""

    category_id: int
    method: str
    seed: int
    candidates: tuple[SupportCandidate, ...]
    source_identities: tuple[str, ...]
    covered_capture_stratum_count: int
    manifest_sha256: str


def parse_train_capture_stratum(file_name: str, category_id: int) -> CaptureStratum:
    """Parse the exact RPC train naming convention into its coverage stratum."""
    if type(category_id) is not int or category_id <= 0:
        raise ValueError("candidate category ID must be positive")
    if not isinstance(file_name, str):
        raise ValueError("invalid train capture filename")
    match = _TRAIN_CAPTURE_NAME.fullmatch(file_name)
    if match is None:
        raise ValueError("invalid train capture filename")
    product_identity = match["product_identity"]
    side = match["side"]
    camera = int(match["camera"])
    if not product_identity or not side:
        raise ValueError("invalid train capture filename")
    return (category_id, product_identity, side, camera)


def materialize_support_order(
    candidates: Iterable[SupportCandidate], *, method: str, seed: int
) -> SupportOrder:
    """Validate and deterministically rank every support candidate for one category."""
    if method not in {"rnd", "div"}:
        raise ValueError("unsupported support selection method")
    if type(seed) is not int:
        raise ValueError("seed must be an integer")
    rows = tuple(candidates)
    if not rows:
        raise ValueError("support candidates must not be empty")
    if not all(isinstance(row, SupportCandidate) for row in rows):
        raise ValueError("support candidates must be SupportCandidate instances")
    source_identities = tuple(row.source_identity for row in rows)
    if len(set(source_identities)) != len(source_identities):
        raise ValueError("duplicate source identity")
    category_ids = {row.category_id for row in rows}
    if len(category_ids) != 1:
        raise ValueError("support candidates must have exactly one category")
    category_id = next(iter(category_ids))
    if any(row.capture_stratum[0] != category_id for row in rows):
        raise ValueError("candidate/category mismatch")
    dimensions = {len(row.embedding) for row in rows}
    if len(dimensions) != 1:
        raise ValueError("inconsistent embedding dimensions")
    normalized = {row.source_identity: _normalized_embedding(row.embedding) for row in rows}
    if method == "rnd":
        ordered = tuple(
            sorted(rows, key=lambda row: (_seeded_digest(seed, row.source_identity), row.source_identity))
        )
    else:
        ordered = _diversity_order(rows, normalized, seed=seed)
    ordered_sources = tuple(row.source_identity for row in ordered)
    covered_count = len({row.capture_stratum for row in ordered})
    manifest_sha256 = hashlib.sha256(
        canonical_json_bytes(
            {
                "category_id": category_id,
                "method": method,
                "seed": seed,
                "candidates": [_manifest_candidate(row) for row in ordered],
                "source_identities": ordered_sources,
                "covered_capture_stratum_count": covered_count,
            }
        )
    ).hexdigest()
    return SupportOrder(
        category_id=category_id,
        method=method,
        seed=seed,
        candidates=ordered,
        source_identities=ordered_sources,
        covered_capture_stratum_count=covered_count,
        manifest_sha256=manifest_sha256,
    )


def support_prefix(order: SupportOrder, shot_count: int) -> tuple[SupportCandidate, ...]:
    """Return an already-materialized ordered support prefix without resampling."""
    if not isinstance(order, SupportOrder):
        raise ValueError("support order must be a SupportOrder")
    if type(shot_count) is not int or shot_count <= 0:
        raise ValueError("shot count must be positive")
    if shot_count > len(order.candidates):
        raise ValueError("insufficient support candidates")
    return order.candidates[:shot_count]


def _validate_capture_stratum(value: object, category_id: int) -> None:
    if not isinstance(value, tuple) or len(value) != 4:
        raise ValueError("candidate capture stratum is invalid")
    stratum_category, product_identity, side, camera = value
    if (
        type(stratum_category) is not int
        or stratum_category != category_id
        or not isinstance(product_identity, str)
        or not product_identity
        or not isinstance(side, str)
        or not side
        or type(camera) is not int
        or camera < 0
    ):
        raise ValueError("candidate/category mismatch")


def _normalized_embedding(values: tuple[float, ...]) -> tuple[float, ...]:
    norm = math.sqrt(sum(value * value for value in values))
    if norm == 0.0:
        raise ValueError("zero-norm embedding")
    return tuple(value / norm for value in values)


def _diversity_order(
    rows: tuple[SupportCandidate, ...],
    normalized: dict[str, tuple[float, ...]],
    *,
    seed: int,
) -> tuple[SupportCandidate, ...]:
    dimensions = len(rows[0].embedding)
    centroid = tuple(sum(normalized[row.source_identity][index] for row in rows) / len(rows) for index in range(dimensions))
    first = min(
        rows,
        key=lambda row: (
            _distance(normalized[row.source_identity], centroid),
            row.image_sha256,
            row.source_identity,
        ),
    )
    selected = [first]
    remaining = {row.source_identity: row for row in rows if row != first}
    stratum_counts = {first.capture_stratum: 1}
    all_strata = {row.capture_stratum for row in rows}
    while remaining:
        represented = set(stratum_counts)
        unrepresented = all_strata - represented
        pool = tuple(remaining.values())
        if unrepresented:
            # A seed must select an independent, reproducible diversity draw.
            # Pick the next unrepresented stratum by a seed-bound digest, then
            # retain farthest-first coverage inside that stratum.  This keeps
            # the one-stratum-before-repeat invariant while avoiding five
            # nominal support seeds that are actually the same support bank.
            next_stratum = min(
                unrepresented,
                key=lambda stratum: _seeded_digest(seed, repr(stratum)),
            )
            pool = tuple(row for row in pool if row.capture_stratum == next_stratum)
        else:
            least_count = min(stratum_counts.get(row.capture_stratum, 0) for row in pool)
            pool = tuple(row for row in pool if stratum_counts.get(row.capture_stratum, 0) == least_count)
        next_row = min(
            pool,
            key=lambda row: (
                -min(_distance(normalized[row.source_identity], normalized[picked.source_identity]) for picked in selected),
                row.image_sha256,
                row.source_identity,
            ),
        )
        selected.append(next_row)
        del remaining[next_row.source_identity]
        stratum_counts[next_row.capture_stratum] = stratum_counts.get(next_row.capture_stratum, 0) + 1
    return tuple(selected)


def _distance(left: tuple[float, ...], right: tuple[float, ...]) -> float:
    return math.sqrt(sum((first - second) ** 2 for first, second in zip(left, right, strict=True)))


def _seeded_digest(seed: int, source_identity: str) -> str:
    return hashlib.sha256(f"{seed}:{source_identity}".encode("utf-8")).hexdigest()


def _manifest_candidate(row: SupportCandidate) -> dict[str, object]:
    return {
        "category_id": row.category_id,
        "source_identity": row.source_identity,
        "source_file_name": row.source_file_name,
        "image_sha256": row.image_sha256,
        "source_byte_size": row.source_byte_size,
        "capture_stratum": row.capture_stratum,
        "embedding": row.embedding,
    }
