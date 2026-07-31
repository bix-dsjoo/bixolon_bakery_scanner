"""Deterministic support ordering for nested RPC few-shot experiments."""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from numbers import Real
from typing import Iterable, Mapping

from bakery_scanner.experiments.rpc_manifest import canonical_json_bytes, write_new_json


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


@dataclass(frozen=True, slots=True)
class SupportBank:
    """Hash-bound complete support orders for every declared category and seed."""

    method: str
    seeds: tuple[int, ...]
    orders: tuple[SupportOrder, ...]
    sha256: str

    def __post_init__(self) -> None:
        if self.method not in {"rnd", "div"}:
            raise ValueError("unsupported support bank method")
        if not self.seeds or len(set(self.seeds)) != len(self.seeds) or any(type(seed) is not int for seed in self.seeds):
            raise ValueError("support bank seeds must be distinct integers")
        if not self.orders or any(not isinstance(order, SupportOrder) for order in self.orders):
            raise ValueError("support bank requires materialized orders")
        coordinates = {(order.category_id, order.seed) for order in self.orders}
        categories = {order.category_id for order in self.orders}
        expected = {(category, seed) for category in categories for seed in self.seeds}
        if coordinates != expected:
            raise ValueError("support bank must cover every declared category and seed")
        if any(order.method != self.method for order in self.orders):
            raise ValueError("support bank order method mismatch")
        if self.sha256 != _support_bank_digest(self.method, self.seeds, self.orders):
            raise ValueError("support bank SHA-256 mismatch")

    def order_for(self, category_id: int, seed: int) -> SupportOrder:
        for order in self.orders:
            if order.category_id == category_id and order.seed == seed:
                return order
        raise ValueError("support bank lacks declared category/seed order")

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": 1,
            "kind": "rpc-fewshot-support-bank",
            "method": self.method,
            "seeds": list(self.seeds),
            "orders": [
                {
                    "category_id": order.category_id,
                    "method": order.method,
                    "seed": order.seed,
                    "candidates": [_manifest_candidate(row) for row in order.candidates],
                    "source_identities": list(order.source_identities),
                    "covered_capture_stratum_count": order.covered_capture_stratum_count,
                    "manifest_sha256": order.manifest_sha256,
                }
                for order in sorted(self.orders, key=lambda item: (item.category_id, item.seed))
            ],
            "sha256": self.sha256,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> "SupportBank":
        required = {"schema_version", "kind", "method", "seeds", "orders", "sha256"}
        if not isinstance(value, Mapping) or set(value) != required or value.get("schema_version") != 1 or value.get("kind") != "rpc-fewshot-support-bank":
            raise ValueError("invalid support bank manifest")
        if not isinstance(value.get("seeds"), list) or not isinstance(value.get("orders"), list):
            raise ValueError("invalid support bank manifest")
        orders: list[SupportOrder] = []
        for raw in value["orders"]:
            if not isinstance(raw, Mapping) or set(raw) != {"category_id", "method", "seed", "candidates", "source_identities", "covered_capture_stratum_count", "manifest_sha256"}:
                raise ValueError("invalid support bank order")
            candidates = raw.get("candidates")
            if not isinstance(candidates, list):
                raise ValueError("invalid support bank order")
            rows = tuple(_candidate_from_manifest(item) for item in candidates)
            rebuilt = materialize_support_order(rows, method=raw["method"], seed=raw["seed"])  # type: ignore[arg-type]
            if (
                rebuilt.category_id != raw.get("category_id")
                or list(rebuilt.source_identities) != raw.get("source_identities")
                or rebuilt.covered_capture_stratum_count != raw.get("covered_capture_stratum_count")
                or rebuilt.manifest_sha256 != raw.get("manifest_sha256")
            ):
                raise ValueError("support bank order is not reproducible")
            orders.append(rebuilt)
        bank = cls(value["method"], tuple(value["seeds"]), tuple(orders), value["sha256"])  # type: ignore[arg-type]
        if bank.method == "div":
            validate_unique_div_support_draws(bank.orders)
        return bank


def materialize_support_bank(
    candidates_by_category: Mapping[int, Iterable[SupportCandidate]], *, method: str, seeds: Iterable[int]
) -> SupportBank:
    """Materialize and validate every support draw before any condition runs."""
    frozen_seeds = tuple(seeds)
    if not isinstance(candidates_by_category, Mapping) or not candidates_by_category:
        raise ValueError("support bank requires category candidates")
    if not frozen_seeds or len(set(frozen_seeds)) != len(frozen_seeds) or any(type(seed) is not int for seed in frozen_seeds):
        raise ValueError("support bank seeds must be distinct integers")
    if any(type(category) is not int or category <= 0 for category in candidates_by_category):
        raise ValueError("support bank category IDs must be positive integers")
    orders = tuple(
        materialize_support_order(tuple(candidates), method=method, seed=seed)
        for _, candidates in sorted(candidates_by_category.items())
        for seed in frozen_seeds
    )
    if method == "div":
        validate_unique_div_support_draws(orders)
    return SupportBank(method, frozen_seeds, orders, _support_bank_digest(method, frozen_seeds, orders))


def write_support_bank(path: Path, bank: SupportBank) -> None:
    if not isinstance(bank, SupportBank):
        raise ValueError("support bank must be a SupportBank")
    write_new_json(path, bank.to_dict())


def load_support_bank(path: Path) -> SupportBank:
    try:
        content = Path(path).read_bytes()
        value = json.loads(content.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("cannot read canonical support bank") from exc
    if not isinstance(value, dict) or canonical_json_bytes(value) != content:
        raise ValueError("support bank is not canonical")
    return SupportBank.from_dict(value)


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


def validate_unique_div_support_draws(
    orders: Iterable[SupportOrder],
) -> tuple[SupportOrder, ...]:
    """Reject nominal DIV support seeds that materialize the same draw.

    A support-manifest planner must call this once it has materialized every
    declared seed for a category.  Hashes alone are insufficient here: their
    seed field changes even when constrained candidate data produces the same
    ordered bank.  The observable ordered source identities are therefore the
    equality contract.
    """
    frozen = tuple(orders)
    if not frozen or not all(isinstance(order, SupportOrder) for order in frozen):
        raise ValueError("DIV support draws must be nonempty SupportOrder instances")
    coordinates = [(order.category_id, order.seed) for order in frozen]
    if len(coordinates) != len(set(coordinates)):
        raise ValueError("duplicate DIV support category/seed draw")
    by_category: dict[int, list[SupportOrder]] = {}
    for order in frozen:
        if order.method != "div":
            raise ValueError("DIV support draw verifier accepts only div orders")
        by_category.setdefault(order.category_id, []).append(order)
    for category_orders in by_category.values():
        if len(category_orders) < 2:
            continue
        observed: dict[tuple[str, ...], int] = {}
        for order in category_orders:
            prior_seed = observed.setdefault(order.source_identities, order.seed)
            if prior_seed != order.seed:
                raise ValueError(
                    "distinct DIV support seeds produced the same ordered support draw"
                )
    return frozen


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


def _candidate_from_manifest(value: object) -> SupportCandidate:
    expected = {
        "category_id", "source_identity", "source_file_name", "image_sha256",
        "source_byte_size", "capture_stratum", "embedding",
    }
    if not isinstance(value, Mapping) or set(value) != expected:
        raise ValueError("invalid support bank candidate")
    stratum = value["capture_stratum"]
    if not isinstance(stratum, (list, tuple)):
        raise ValueError("invalid support bank candidate")
    try:
        return SupportCandidate(
            category_id=value["category_id"],  # type: ignore[arg-type]
            source_identity=value["source_identity"],  # type: ignore[arg-type]
            source_file_name=value["source_file_name"],  # type: ignore[arg-type]
            image_sha256=value["image_sha256"],  # type: ignore[arg-type]
            source_byte_size=value["source_byte_size"],  # type: ignore[arg-type]
            capture_stratum=tuple(stratum),  # type: ignore[arg-type]
            embedding=tuple(value["embedding"]),  # type: ignore[arg-type]
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("invalid support bank candidate") from exc


def _support_bank_digest(
    method: str, seeds: tuple[int, ...], orders: tuple[SupportOrder, ...]
) -> str:
    """Digest the full observable bank, not merely a selector configuration."""
    return hashlib.sha256(
        canonical_json_bytes(
            {
                "schema_version": 1,
                "method": method,
                "seeds": list(seeds),
                "orders": [
                    {
                        "category_id": order.category_id,
                        "method": order.method,
                        "seed": order.seed,
                        "source_identities": list(order.source_identities),
                        "manifest_sha256": order.manifest_sha256,
                    }
                    for order in sorted(orders, key=lambda item: (item.category_id, item.seed))
                ],
            }
        )
    ).hexdigest()
