"""Deterministic, leakage-safe class and checkout-scene splits for RPC 2019."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path
from typing import Iterable

from bakery_scanner.experiments.rpc_manifest import (
    RpcImage,
    RpcIndex,
    RpcObject,
    canonical_json_bytes,
    write_new_json,
)


_CHECKOUT_NAME = re.compile(r"^(?P<date>\d{8})-(?P<hour>\d{2})-(?P<minute>\d{2})-(?P<second>\d{2})-(?P<suffix>.+)\.jpg$")
_ROLE_NAMES = ("calibration", "development_selection")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True, slots=True)
class ClassFoldAssignment:
    fold_number: int
    split_version: str
    seed: int
    novel_category_ids: tuple[int, ...]
    base_category_ids: tuple[int, ...]
    manifest_sha256: str


@dataclass(frozen=True, slots=True)
class SceneRoleAssignment:
    split: str
    image_id: int
    category_ids: tuple[int, ...]
    role: str
    burst_id: str
    timestamp: datetime
    date: str
    suffix: str
    difficulty: str
    split_version: str
    manifest_sha256: str


@dataclass(frozen=True, slots=True)
class _CheckoutName:
    timestamp: datetime
    date: str
    suffix: str


@dataclass(frozen=True, slots=True)
class _Burst:
    burst_id: str
    split: str
    date: str
    suffix: str
    difficulty: str
    images: tuple[tuple[RpcImage, _CheckoutName, frozenset[int]], ...]

    @property
    def category_ids(self) -> frozenset[int]:
        return frozenset(category_id for _, _, categories in self.images for category_id in categories)

    @property
    def image_count(self) -> int:
        return len(self.images)


def build_class_folds(index: RpcIndex, *, split_version: str, seed: int) -> tuple[ClassFoldAssignment, ...]:
    """Assign every RPC category to exactly one balanced novel fold."""
    categories = _categories(index)
    if not isinstance(split_version, str) or not split_version:
        raise ValueError("split_version must be a non-empty string")
    if type(seed) is not int:
        raise ValueError("seed must be an integer")

    novel_by_fold: list[list[int]] = [[] for _ in range(5)]
    by_supercategory: dict[str, list[int]] = {}
    for category_id, category in categories.items():
        by_supercategory.setdefault(category.supercategory, []).append(category_id)
    for supercategory in sorted(by_supercategory):
        ordered = sorted(
            by_supercategory[supercategory],
            key=lambda category_id: _digest((split_version, category_id, seed)),
        )
        fold_order = sorted(range(5), key=lambda fold: (len(novel_by_fold[fold]), fold))
        for position, category_id in enumerate(ordered):
            novel_by_fold[fold_order[position % 5]].append(category_id)
    if any(len(items) != 40 for items in novel_by_fold):
        raise ValueError("RPC categories cannot form five 40-category novel folds")

    all_ids = tuple(sorted(categories))
    provisional = tuple(
        ClassFoldAssignment(
            fold_number=number,
            split_version=split_version,
            seed=seed,
            novel_category_ids=tuple(sorted(novel)),
            base_category_ids=tuple(category_id for category_id in all_ids if category_id not in novel),
            manifest_sha256="",
        )
        for number, novel in enumerate(novel_by_fold, start=1)
    )
    digest = _manifest_digest(provisional)
    return tuple(replace(item, manifest_sha256=digest) for item in provisional)


def build_scene_roles(index: RpcIndex, *, split_version: str) -> tuple[SceneRoleAssignment, ...]:
    """Keep checkout bursts atomic while making validation roles category-complete."""
    categories = _categories(index)
    if not isinstance(split_version, str) or not split_version:
        raise ValueError("split_version must be a non-empty string")
    bursts = _build_bursts(
        (image for image in index.images if image.split in {"val2019", "test2019"}), index.objects
    )
    val_bursts = tuple(item for item in bursts if item.split == "val2019")
    test_bursts = tuple(item for item in bursts if item.split == "test2019")
    roles = _assign_val_roles(val_bursts, tuple(categories), split_version)
    roles.update({burst.burst_id: "locked_acceptance" for burst in test_bursts})

    provisional = tuple(
        SceneRoleAssignment(
            split=burst.split,
            image_id=image.image_id,
            category_ids=tuple(sorted(category_ids)),
            role=roles[burst.burst_id],
            burst_id=burst.burst_id,
            timestamp=name.timestamp,
            date=name.date,
            suffix=name.suffix,
            difficulty=image.level,
            split_version=split_version,
            manifest_sha256="",
        )
        for burst in bursts
        for image, name, category_ids in burst.images
    )
    validate_val_difficulty_balance(provisional)
    digest = _manifest_digest(provisional)
    return tuple(replace(item, manifest_sha256=digest) for item in provisional)


def validate_val_difficulty_balance(
    rows: Iterable[SceneRoleAssignment],
) -> None:
    """Require each validation difficulty to be balanced within one burst."""
    validation = tuple(row for row in rows if row.split == "val2019")
    for difficulty in ("easy", "medium", "hard"):
        subset = tuple(row for row in validation if row.difficulty == difficulty)
        if not subset:
            continue
        counts = {
            role: sum(row.role == role for row in subset)
            for role in _ROLE_NAMES
        }
        burst_sizes: dict[str, int] = {}
        for row in subset:
            burst_sizes[row.burst_id] = burst_sizes.get(row.burst_id, 0) + 1
        if abs(counts[_ROLE_NAMES[0]] - counts[_ROLE_NAMES[1]]) > max(
            burst_sizes.values()
        ):
            raise ValueError("validation role difficulty balance exceeds largest burst")


def write_scene_role_manifest(
    output: Path,
    roles: Iterable[SceneRoleAssignment],
    *,
    source_manifest_sha256: str,
) -> None:
    """Materialize one canonical scene-role artifact bound to resolved RPC input."""
    if _SHA256.fullmatch(source_manifest_sha256) is None:
        raise ValueError("source manifest SHA-256 must be lowercase")
    frozen = tuple(roles)
    if not frozen or not all(isinstance(row, SceneRoleAssignment) for row in frozen):
        raise ValueError("scene roles must be nonempty assignments")
    identities = [(row.split, row.image_id) for row in frozen]
    if len(identities) != len(set(identities)):
        raise ValueError("scene roles contain duplicate source images")
    write_new_json(
        output,
        {
            "schema_version": 1,
            "kind": "rpc-fewshot-scene-roles",
            "source_manifest_sha256": source_manifest_sha256,
            "assignments": [
                {
                    "split": row.split,
                    "image_id": row.image_id,
                    "role": row.role,
                    "burst_id": row.burst_id,
                    "difficulty": row.difficulty,
                }
                for row in sorted(frozen, key=lambda item: (item.split, item.image_id))
            ],
        },
    )


def _categories(index: RpcIndex) -> dict[int, object]:
    categories = {item.category_id: item for item in index.categories}
    if len(categories) != 200 or set(categories) != set(range(1, 201)):
        raise ValueError("RPC split building requires exactly categories 1 through 200")
    if any(not item.name or not item.supercategory for item in categories.values()):
        raise ValueError("RPC category metadata must include name and supercategory")
    return categories


def _build_bursts(images: Iterable[RpcImage], objects: Iterable[RpcObject]) -> tuple[_Burst, ...]:
    image_categories: dict[tuple[str, int], set[int]] = {}
    for item in objects:
        if item.split in {"val2019", "test2019"}:
            image_categories.setdefault((item.split, item.image_id), set()).add(item.category_id)
    grouped: dict[tuple[str, str, str, str], list[tuple[RpcImage, _CheckoutName, frozenset[int]]]] = {}
    for image in images:
        name = _parse_checkout_name(image.source_path.name)
        if image.level not in {"easy", "medium", "hard"}:
            raise ValueError("validation and test images require a valid COCO level")
        categories = frozenset(image_categories.get((image.split, image.image_id), set()))
        if not categories:
            raise ValueError("impossible validation category coverage: source image is missing incidence")
        grouped.setdefault((image.split, name.date, name.suffix, image.level), []).append((image, name, categories))
    bursts: list[_Burst] = []
    for key in sorted(grouped):
        records = sorted(grouped[key], key=lambda item: (item[1].timestamp, item[0].image_id, item[0].source_identity))
        current: list[tuple[RpcImage, _CheckoutName, frozenset[int]]] = []
        for record in records:
            if current and (record[1].timestamp - current[-1][1].timestamp).total_seconds() > 120:
                bursts.append(_make_burst(key, len(bursts), current))
                current = []
            current.append(record)
        if current:
            bursts.append(_make_burst(key, len(bursts), current))
    return tuple(bursts)


def _make_burst(key: tuple[str, str, str, str], position: int, records: list[tuple[RpcImage, _CheckoutName, frozenset[int]]]) -> _Burst:
    split, date, suffix, difficulty = key
    identity = f"{split}:{date}:{suffix}:{difficulty}:{position:05d}"
    return _Burst(identity, split, date, suffix, difficulty, tuple(records))


def _parse_checkout_name(value: str) -> _CheckoutName:
    match = _CHECKOUT_NAME.fullmatch(value)
    if match is None:
        raise ValueError("invalid checkout name")
    try:
        timestamp = datetime.strptime(
            f"{match['date']}-{match['hour']}-{match['minute']}-{match['second']}", "%Y%m%d-%H-%M-%S"
        )
    except ValueError as exc:
        raise ValueError("invalid checkout name") from exc
    suffix = match["suffix"]
    if not suffix:
        raise ValueError("invalid checkout name")
    return _CheckoutName(timestamp, match["date"], suffix)


def _assign_val_roles(bursts: tuple[_Burst, ...], category_ids: tuple[int, ...], split_version: str) -> dict[str, str]:
    candidates = {category_id: tuple(item for item in bursts if category_id in item.category_ids) for category_id in category_ids}
    if any(len(items) < 2 for items in candidates.values()):
        raise ValueError("impossible validation category coverage")
    assigned: dict[str, str] = {}
    role_sizes = {role: 0 for role in _ROLE_NAMES}
    role_difficulties: dict[str, dict[str, int]] = {role: {} for role in _ROLE_NAMES}
    role_categories: dict[str, dict[int, int]] = {role: {} for role in _ROLE_NAMES}

    def assign(burst: _Burst, role: str) -> None:
        prior = assigned.get(burst.burst_id)
        if prior is not None:
            if prior != role:
                raise ValueError("validation burst role overlap")
            return
        assigned[burst.burst_id] = role
        role_sizes[role] += burst.image_count
        role_difficulties[role][burst.difficulty] = role_difficulties[role].get(burst.difficulty, 0) + burst.image_count
        for category_id in burst.category_ids:
            role_categories[role][category_id] = role_categories[role].get(category_id, 0) + 1

    for category_id in sorted(category_ids, key=lambda item: (len(candidates[item]), item)):
        for role in _ROLE_NAMES:
            if category_id in role_categories[role]:
                continue
            choices = [item for item in candidates[category_id] if assigned.get(item.burst_id) in (None, role)]
            if not choices:
                raise ValueError("impossible validation category coverage")
            other = _ROLE_NAMES[1] if role == _ROLE_NAMES[0] else _ROLE_NAMES[0]
            assign(min(choices, key=lambda item: (role_sizes[role] + item.image_count, role_difficulties[role].get(item.difficulty, 0), -len(item.category_ids - set(role_categories[other])), _digest((split_version, item.burst_id)))), role)

    for burst in sorted(bursts, key=lambda item: _digest((split_version, item.burst_id))):
        if burst.burst_id in assigned:
            continue
        first, second = _ROLE_NAMES
        role = min(
            _ROLE_NAMES,
            key=lambda candidate: (
                abs((role_sizes[candidate] + burst.image_count) - 3000),
                abs((role_difficulties[candidate].get(burst.difficulty, 0) + burst.image_count) - role_difficulties[second if candidate == first else first].get(burst.difficulty, 0)),
                sum(abs((role_categories[candidate].get(category_id, 0) + (category_id in burst.category_ids)) - role_categories[second if candidate == first else first].get(category_id, 0)) for category_id in category_ids),
                _digest((split_version, burst.burst_id)),
            ),
        )
        assign(burst, role)
    if any(set(role_categories[role]) != set(category_ids) for role in _ROLE_NAMES):
        raise ValueError("impossible validation category coverage")
    _refine_val_roles(assigned, bursts, category_ids, split_version)
    _refine_val_difficulty_balance(assigned, bursts, category_ids, split_version)
    final_sizes = {
        role: sum(burst.image_count for burst in bursts if assigned[burst.burst_id] == role)
        for role in _ROLE_NAMES
    }
    if abs(final_sizes[_ROLE_NAMES[0]] - final_sizes[_ROLE_NAMES[1]]) > max(
        burst.image_count for burst in bursts
    ):
        raise ValueError("validation role size imbalance exceeds largest burst")
    return assigned


def _refine_val_roles(
    assigned: dict[str, str], bursts: tuple[_Burst, ...], category_ids: tuple[int, ...], split_version: str
) -> None:
    """Move only coverage-safe atomic bursts while strictly improving size balance."""
    by_id = {burst.burst_id: burst for burst in bursts}
    while True:
        sizes = {role: sum(by_id[burst_id].image_count for burst_id, value in assigned.items() if value == role) for role in _ROLE_NAMES}
        category_counts = {
            role: {category_id: sum(category_id in by_id[burst_id].category_ids for burst_id, value in assigned.items() if value == role) for category_id in category_ids}
            for role in _ROLE_NAMES
        }
        current_difference = abs(sizes[_ROLE_NAMES[0]] - sizes[_ROLE_NAMES[1]])
        candidates: list[tuple[str, _Burst, str]] = []
        for burst in sorted(bursts, key=lambda item: _digest((split_version, item.burst_id))):
            source = assigned[burst.burst_id]
            target = _ROLE_NAMES[1] if source == _ROLE_NAMES[0] else _ROLE_NAMES[0]
            if any(category_counts[source][category_id] <= 1 for category_id in burst.category_ids):
                continue
            difference = abs((sizes[source] - burst.image_count) - (sizes[target] + burst.image_count))
            if difference < current_difference:
                candidates.append((burst.burst_id, burst, target))
        if not candidates:
            return
        _, burst, target = candidates[0]
        assigned[burst.burst_id] = target


def _refine_val_difficulty_balance(
    assigned: dict[str, str], bursts: tuple[_Burst, ...], category_ids: tuple[int, ...], split_version: str
) -> None:
    """Swap equally sized, coverage-safe bursts to reduce difficulty imbalance."""
    by_id = {burst.burst_id: burst for burst in bursts}
    while True:
        category_counts = {
            role: {
                category_id: sum(
                    category_id in by_id[burst_id].category_ids
                    for burst_id, value in assigned.items()
                    if value == role
                )
                for category_id in category_ids
            }
            for role in _ROLE_NAMES
        }
        difficulty_counts = _difficulty_role_counts(assigned, bursts)
        maximums = {
            difficulty: max(burst.image_count for burst in bursts if burst.difficulty == difficulty)
            for difficulty in ("easy", "medium", "hard")
            if any(burst.difficulty == difficulty for burst in bursts)
        }
        current = _difficulty_balance_score(difficulty_counts, maximums)
        best: tuple[tuple[int, int, int], _Burst, _Burst] | None = None
        by_role_difficulty_size: dict[tuple[str, str, int], list[_Burst]] = {}
        for burst in bursts:
            by_role_difficulty_size.setdefault(
                (assigned[burst.burst_id], burst.difficulty, burst.image_count), []
            ).append(burst)
        deltas = {
            difficulty: difficulty_counts[_ROLE_NAMES[0]][difficulty]
            - difficulty_counts[_ROLE_NAMES[1]][difficulty]
            for difficulty in maximums
        }
        positive = tuple(difficulty for difficulty, delta in deltas.items() if delta > 0)
        negative = tuple(difficulty for difficulty, delta in deltas.items() if delta < 0)
        for first_difficulty in positive:
            for second_difficulty in negative:
                sizes = sorted(
                    {
                        key[2]
                        for key in by_role_difficulty_size
                        if key[:2] == (_ROLE_NAMES[0], first_difficulty)
                    }
                    & {
                        key[2]
                        for key in by_role_difficulty_size
                        if key[:2] == (_ROLE_NAMES[1], second_difficulty)
                    }
                )
                for size in sizes:
                    candidate_counts = {role: dict(values) for role, values in difficulty_counts.items()}
                    candidate_counts[_ROLE_NAMES[0]][first_difficulty] -= size
                    candidate_counts[_ROLE_NAMES[1]][first_difficulty] += size
                    candidate_counts[_ROLE_NAMES[0]][second_difficulty] += size
                    candidate_counts[_ROLE_NAMES[1]][second_difficulty] -= size
                    score = _difficulty_balance_score(candidate_counts, maximums)
                    if score >= current:
                        continue
                    firsts = sorted(
                        by_role_difficulty_size[(_ROLE_NAMES[0], first_difficulty, size)],
                        key=lambda item: _digest((split_version, item.burst_id)),
                    )
                    seconds = sorted(
                        by_role_difficulty_size[(_ROLE_NAMES[1], second_difficulty, size)],
                        key=lambda item: _digest((split_version, item.burst_id)),
                    )
                    pair = next(
                        (
                            (first, second)
                            for first in firsts
                            for second in seconds
                            if _swap_preserves_coverage(first, second, category_counts)
                        ),
                        None,
                    )
                    if pair is None:
                        continue
                    candidate = (score, *pair)
                    if best is None or (
                        candidate[0], _digest((split_version, candidate[1].burst_id, candidate[2].burst_id))
                    ) < (
                        best[0], _digest((split_version, best[1].burst_id, best[2].burst_id))
                    ):
                        best = candidate
        if best is None:
            return
        _, first, second = best
        assigned[first.burst_id], assigned[second.burst_id] = _ROLE_NAMES[1], _ROLE_NAMES[0]


def _swap_preserves_coverage(
    first: _Burst,
    second: _Burst,
    category_counts: dict[str, dict[int, int]],
) -> bool:
    for category_id in first.category_ids | second.category_ids:
        if (
            category_counts[_ROLE_NAMES[0]].get(category_id, 0)
            - (category_id in first.category_ids)
            + (category_id in second.category_ids)
            < 1
            or category_counts[_ROLE_NAMES[1]].get(category_id, 0)
            - (category_id in second.category_ids)
            + (category_id in first.category_ids)
            < 1
        ):
            return False
    return True


def _difficulty_role_counts(
    assigned: dict[str, str], bursts: tuple[_Burst, ...]
) -> dict[str, dict[str, int]]:
    return {
        role: {
            difficulty: sum(
                burst.image_count
                for burst in bursts
                if burst.difficulty == difficulty and assigned[burst.burst_id] == role
            )
            for difficulty in ("easy", "medium", "hard")
        }
        for role in _ROLE_NAMES
    }


def _difficulty_balance_score(
    counts: dict[str, dict[str, int]], maximums: dict[str, int]
) -> tuple[int, int, int]:
    deltas: list[int] = []
    excesses: list[int] = []
    for difficulty, maximum in maximums.items():
        delta = abs(counts[_ROLE_NAMES[0]][difficulty] - counts[_ROLE_NAMES[1]][difficulty])
        deltas.append(delta)
        excesses.append(max(0, delta - maximum))
    return (sum(excesses), sum(deltas), max(deltas, default=0))


def _digest(value: tuple[object, ...]) -> str:
    return hashlib.sha256(repr(value).encode("utf-8")).hexdigest()


def _manifest_digest(rows: tuple[object, ...]) -> str:
    return hashlib.sha256(canonical_json_bytes([_as_manifest_row(row) for row in rows])).hexdigest()


def _as_manifest_row(row: object) -> dict[str, object]:
    values = row.__dict__ if hasattr(row, "__dict__") else {field: getattr(row, field) for field in row.__dataclass_fields__}  # type: ignore[attr-defined]
    return {key: (value.isoformat() if isinstance(value, datetime) else value) for key, value in values.items() if key != "manifest_sha256"}
