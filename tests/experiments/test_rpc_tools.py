"""Subprocess contracts for the immutable RPC research-only CLIs."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from bakery_scanner.experiments.rpc_manifest import (
    RpcDatasetContract,
    RpcImage,
    RpcIndex,
    RpcObject,
)
from bakery_scanner.experiments.rpc_protocol import (
    ExperimentReceipt,
    FoldBaseArtifact,
    ScoringPlan,
    stage_one_conditions,
)
from bakery_scanner.experiments import rpc_scoring as _rpc_scoring


ROOT = Path(__file__).parents[2]
_TEST_TRUSTED_ROOT = Path("C:/rpc-test-trusted-root")
HASHES = {
    "condition_manifest_sha256": "a" * 64,
    "model_sha256": "b" * 64,
    "support_sha256": "c" * 64,
    "calibration_sha256": "d" * 64,
    "policy_sha256": "e" * 64,
    "preprocessing_sha256": "f" * 64,
    "code_sha256": "0" * 64,
}


def _full_source_images() -> list[dict[str, object]]:
    counts = RpcDatasetContract.default().image_counts
    images: list[dict[str, object]] = []
    for split, count in counts.items():
        for image_id in range(1, count + 1):
            image: dict[str, object] = {"split": split, "image_id": image_id}
            if split == "test2019":
                image["source_identity"] = (
                    "sample" if image_id == 1 else "base" if image_id == 2 else f"test:{image_id}"
                )
                image["level"] = "easy"
            images.append(image)
    return images


def _full_test_assignments() -> list[dict[str, object]]:
    return [
        {
            "split": "test2019",
            "image_id": image_id,
            "role": "locked_acceptance",
            "burst_id": "burst" if image_id < 3 else f"burst-{image_id}",
            "difficulty": "easy",
        }
        for image_id in range(1, RpcDatasetContract.default().image_counts["test2019"] + 1)
    ]


def _trusted_index() -> RpcIndex:
    """Hermetic dependency injection, independent of resolved source JSON."""
    return RpcIndex(
        RpcDatasetContract.default(),
        tuple(
            RpcImage(
                "test2019",
                image_id,
                "sample" if image_id == 1 else "base" if image_id == 2 else f"test:{image_id}",
                Path(f"C:/trusted/test-{image_id}.jpg"),
                1,
                "0" * 64,
                "easy",
            )
            for image_id in range(
                1, RpcDatasetContract.default().image_counts["test2019"] + 1
            )
        ),
        (
            RpcObject("test2019", 1, 1, 1, (0.0, 0.0, 1.0, 1.0)),
            RpcObject("test2019", 2, 2, 2, (0.0, 0.0, 1.0, 1.0)),
        ),
    )


def test_stage_ground_truth_dispatch_never_uses_locked_truth_before_stage5(monkeypatch: pytest.MonkeyPatch):
    calls: list[str] = []
    monkeypatch.setattr(
        _rpc_scoring,
        "load_development_ground_truth",
        lambda *_args, **_kwargs: calls.append("development") or object(),
    )
    monkeypatch.setattr(
        _rpc_scoring,
        "load_locked_ground_truth",
        lambda *_args, **_kwargs: calls.append("locked") or object(),
    )

    _rpc_scoring.load_stage_ground_truth(Path("dev.json"), stage="stage1", trusted_source_root=_TEST_TRUSTED_ROOT)
    _rpc_scoring.load_stage_ground_truth(Path("locked.json"), stage="locked", trusted_source_root=_TEST_TRUSTED_ROOT)

    assert calls == ["development", "locked"]


LOCKED_SOURCE_MANIFEST = {
    "schema_version": 1,
    "kind": "rpc-fewshot-resolved-inputs",
    "source": "RPC 2019",
    "annotation_sha256": dict(RpcDatasetContract.default().annotation_sha256),
    "image_counts": dict(RpcDatasetContract.default().image_counts),
    "categories": [],
    "images": _full_source_images(),
    "objects": [
        {"split": "test2019", "annotation_id": 1, "image_id": 1, "category_id": 1},
        {"split": "test2019", "annotation_id": 2, "image_id": 2, "category_id": 2},
    ],
}
LOCKED_SOURCE_MANIFEST_BYTES = json.dumps(
    LOCKED_SOURCE_MANIFEST, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False,
).encode("utf-8")
LOCKED_SOURCE_MANIFEST_SHA256 = hashlib.sha256(LOCKED_SOURCE_MANIFEST_BYTES).hexdigest()
LOCKED_SCENE_ROLE_MANIFEST = {
    "schema_version": 1,
    "kind": "rpc-fewshot-scene-roles",
    "source_manifest_sha256": LOCKED_SOURCE_MANIFEST_SHA256,
    "assignments": _full_test_assignments(),
}
LOCKED_SCENE_ROLE_MANIFEST_BYTES = json.dumps(
    LOCKED_SCENE_ROLE_MANIFEST, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False,
).encode("utf-8")
LOCKED_SCENE_ROLE_MANIFEST_SHA256 = hashlib.sha256(LOCKED_SCENE_ROLE_MANIFEST_BYTES).hexdigest()
LOCKED_GROUND_TRUTH = {
    "schema_version": 2,
    "kind": "rpc-fewshot-locked-ground-truth",
    "source_manifest_path": "locked-source.json",
    "source_manifest_sha256": LOCKED_SOURCE_MANIFEST_SHA256,
    "scene_role_manifest_path": "locked-scene-roles.json",
    "scene_role_manifest_sha256": LOCKED_SCENE_ROLE_MANIFEST_SHA256,
    "objects": [
        {
            "sample_id": "sample",
            "object_id": 1,
            "burst_id": "burst",
            "difficulty": "E",
            "truth_category_id": 1,
        },
        {
            "sample_id": "base",
            "object_id": 2,
            "burst_id": "burst",
            "difficulty": "E",
            "truth_category_id": 2,
        },
    ],
}
LOCKED_GROUND_TRUTH_BYTES = json.dumps(
    LOCKED_GROUND_TRUTH,
    ensure_ascii=False,
    sort_keys=True,
    separators=(",", ":"),
    allow_nan=False,
).encode("utf-8")
LOCKED_GROUND_TRUTH_SHA256 = hashlib.sha256(LOCKED_GROUND_TRUTH_BYTES).hexdigest()
BASE_CHECKPOINT_EVIDENCE = {
    "schema_version": 1,
    "kind": "rpc-fewshot-fold-base-checkpoint-evidence",
    "fold": 0,
    "checkpoint_sha256": "2" * 64,
    "cohort_manifest_sha256": LOCKED_GROUND_TRUTH_SHA256,
    "base_category_ids": [2],
    "sample_count": 10,
    "base_macro_final_correct_recall": 1.0,
}
BASE_CHECKPOINT_EVIDENCE_BYTES = json.dumps(
    BASE_CHECKPOINT_EVIDENCE,
    ensure_ascii=False,
    sort_keys=True,
    separators=(",", ":"),
    allow_nan=False,
).encode("utf-8")
BASE_CHECKPOINT_EVIDENCE_SHA256 = hashlib.sha256(BASE_CHECKPOINT_EVIDENCE_BYTES).hexdigest()


def _run(script: str, *args: str) -> subprocess.CompletedProcess[str]:
    environment = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
    return subprocess.run(
        [sys.executable, str(ROOT / script), *args],
        cwd=ROOT,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )


def _score_module():
    specification = importlib.util.spec_from_file_location("score_rpc_fewshot_test", ROOT / "tools/evaluate/score_rpc_fewshot.py")
    assert specification is not None and specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    sys.modules[specification.name] = module
    specification.loader.exec_module(module)
    public_score = module.score

    def score_for_test(*args, trusted_index: RpcIndex, **kwargs):
        _rpc_scoring._load_verified_default_rpc_index = lambda _root: trusted_index
        _rpc_scoring._build_canonical_scene_roles = lambda trusted: tuple(
            type(
                "Role",
                (),
                {
                    "split": image.split,
                    "image_id": image.image_id,
                    "role": "locked_acceptance",
                    "burst_id": (
                        "burst" if image.image_id < 3 else f"burst-{image.image_id}"
                    ),
                    "difficulty": image.level,
                },
            )
            for image in trusted.images
            if image.split == "test2019"
        )
        return public_score(
            *args, trusted_source_root=_TEST_TRUSTED_ROOT, **kwargs
        )

    module.score = score_for_test
    return module


def _receipt(condition_id: str) -> dict[str, object]:
    plan = ScoringPlan(
        bootstrap_seed=7,
        bootstrap_replicates=10,
        folds=(0,),
        support_seeds=(101,),
        expected_condition_ids=(condition_id,),
        cohort_id="rpc-test",
        registered_category_ids=(1, 2),
        fold_base_artifacts=(
            FoldBaseArtifact(
                fold=0,
                checkpoint_sha256="2" * 64,
                evidence_sha256=BASE_CHECKPOINT_EVIDENCE_SHA256,
            ),
        ),
    )
    return {
        "schema_version": 2,
        "kind": "rpc-fewshot-experiment-receipt",
        **HASHES,
        "condition": {"condition_id": condition_id, "fold": 0, "support_seed": 101},
        "cohort": {
            "fold": 0,
            "manifest_sha256": LOCKED_GROUND_TRUTH_SHA256,
            "novel_category_ids": [1],
            "base_category_ids": [2],
        },
        "fold_base_checkpoint": {
            "checkpoint_sha256": "2" * 64,
            "evidence_sha256": BASE_CHECKPOINT_EVIDENCE_SHA256,
            "fold": 0,
        },
        "scoring": {"registered_category_ids": [1, 2]},
        "scoring_plan": plan.to_dict(),
        "scoring_plan_sha256": plan.sha256,
        "environment_lock_digest": "sha256:environment",
        "output_uri": "file:///external/run",
        "reason": "",
        "status": "completed",
    }


def _task4_receipt(
    *,
    condition_index: int,
    output_uri: str,
    cohort_manifest_sha256: str = LOCKED_GROUND_TRUTH_SHA256,
) -> dict[str, object]:
    condition = stage_one_conditions(seeds=(101,), folds=(0,))[condition_index]
    plan = ScoringPlan(
        bootstrap_seed=7,
        bootstrap_replicates=10,
        folds=(0,),
        support_seeds=(101,),
        expected_condition_ids=(condition.condition_id,),
        cohort_id="rpc-test",
        registered_category_ids=(1, 2),
        fold_base_artifacts=(
            FoldBaseArtifact(
                fold=0,
                checkpoint_sha256="2" * 64,
                evidence_sha256=BASE_CHECKPOINT_EVIDENCE_SHA256,
            ),
        ),
    )
    return ExperimentReceipt.completed(
        condition,
        **HASHES,
        cohort_manifest_sha256=cohort_manifest_sha256,
        novel_category_ids=(1,),
        base_category_ids=(2,),
        scoring_plan=plan,
        base_checkpoint_sha256="2" * 64,
        base_checkpoint_evidence_sha256=BASE_CHECKPOINT_EVIDENCE_SHA256,
        environment_lock_digest="sha256:environment",
        output_uri=output_uri,
    ).to_dict()


def _evidence(condition_id: str, **overrides: object) -> dict[str, object]:
    overrides = dict(overrides)
    sample_id = overrides.get("sample_id", "sample")
    default_scores = [0.1, 0.9] if sample_id == "base" else [0.9, 0.1]
    return {
        "sample_id": "sample",
        "object_id": 2 if sample_id == "base" else 1,
        "condition_id": condition_id,
        "fold": 0,
        "difficulty": "E",
        "burst_id": "burst",
        "truth_category_id": 1,
        "predicted_category_id": 1,
        "score_category_ids": [1, 2],
        "repvit_global_scores": overrides.pop(
            "repvit_global_scores", default_scores
        ),
        "dinov3_global_scores": overrides.pop(
            "dinov3_global_scores", default_scores
        ),
        "dinov3_local_scores": overrides.pop("dinov3_local_scores", default_scores),
        "conditional_dino_executed": overrides.pop("conditional_dino_executed", False),
        **HASHES,
        **overrides,
    }


def _canonical(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _write_base_checkpoint_evidence(path: Path) -> None:
    path.write_bytes(BASE_CHECKPOINT_EVIDENCE_BYTES)


def _write_locked_ground_truth(path: Path) -> None:
    (path.parent / "locked-source.json").write_bytes(LOCKED_SOURCE_MANIFEST_BYTES)
    (path.parent / "locked-scene-roles.json").write_bytes(
        LOCKED_SCENE_ROLE_MANIFEST_BYTES
    )
    path.write_bytes(LOCKED_GROUND_TRUTH_BYTES)


def test_build_manifest_refuses_existing_output_before_reading_rpc_root(tmp_path: Path):
    output = tmp_path / "existing.json"
    output.write_text("{}", encoding="utf-8")
    result = _run("tools/data/build_rpc_fewshot_manifests.py", "--rpc-root", str(tmp_path), "--output", str(output))

    assert result.returncode != 0
    assert "exists" in result.stderr


def test_build_manifest_rejects_duplicate_rpc_root(tmp_path: Path):
    duplicate_root = tmp_path / "retail_product_checkout"
    duplicate_root.mkdir()
    result = _run("tools/data/build_rpc_fewshot_manifests.py", "--rpc-root", str(duplicate_root), "--output", str(tmp_path / "new.json"))

    assert result.returncode != 0
    assert "duplicate extracted RPC root" in result.stderr


def test_score_cli_refuses_existing_output(tmp_path: Path):
    evidence = tmp_path / "evidence.jsonl"
    reference = tmp_path / "reference.jsonl"
    condition = tmp_path / "condition.json"
    reference_condition = tmp_path / "reference-condition.json"
    ground_truth = tmp_path / "locked-ground-truth.json"
    base_checkpoint_evidence = tmp_path / "base-checkpoint.json"
    evidence.write_text(_canonical(_evidence("candidate")) + "\n", encoding="utf-8")
    reference.write_text(_canonical(_evidence("reference")) + "\n", encoding="utf-8")
    condition.write_text(_canonical(_receipt("candidate")), encoding="utf-8")
    reference_condition.write_text(_canonical(_receipt("reference")), encoding="utf-8")
    _write_locked_ground_truth(ground_truth)
    _write_base_checkpoint_evidence(base_checkpoint_evidence)
    output = tmp_path / "existing.json"
    output.write_text("{}", encoding="utf-8")

    result = _run("tools/evaluate/score_rpc_fewshot.py", "--evidence", str(evidence), "--reference-evidence", str(reference), "--condition", str(condition), "--reference-condition", str(reference_condition), "--ground-truth-manifest", str(ground_truth), "--base-checkpoint-evidence", str(base_checkpoint_evidence), "--output", str(output))

    assert result.returncode != 0
    assert "exists" in result.stderr


def test_score_cli_fails_closed_for_provenance_mismatch(tmp_path: Path):
    evidence = tmp_path / "evidence.jsonl"
    reference = tmp_path / "reference.jsonl"
    condition = tmp_path / "condition.json"
    reference_condition = tmp_path / "reference-condition.json"
    ground_truth = tmp_path / "locked-ground-truth.json"
    base_checkpoint_evidence = tmp_path / "base-checkpoint.json"
    candidate_receipt = _task4_receipt(
        condition_index=0, output_uri="file:///candidate"
    )
    reference_receipt = _task4_receipt(
        condition_index=0, output_uri="file:///reference"
    )
    candidate_id = candidate_receipt["condition"]["condition_id"]  # type: ignore[index]
    reference_id = reference_receipt["condition"]["condition_id"]  # type: ignore[index]
    evidence.write_text(
        _canonical(_evidence(candidate_id, policy_sha256="1" * 64))
        + "\n"
        + _canonical(
            _evidence(
                candidate_id,
                sample_id="base",
                truth_category_id=2,
                predicted_category_id=2,
                policy_sha256="1" * 64,
            )
        )
        + "\n",
        encoding="utf-8",
    )
    reference.write_text(
        _canonical(_evidence(reference_id))
        + "\n"
        + _canonical(
            _evidence(
                reference_id,
                sample_id="base",
                truth_category_id=2,
                predicted_category_id=2,
            )
        )
        + "\n",
        encoding="utf-8",
    )
    condition.write_text(_canonical(candidate_receipt), encoding="utf-8")
    reference_condition.write_text(_canonical(reference_receipt), encoding="utf-8")
    _write_locked_ground_truth(ground_truth)
    _write_base_checkpoint_evidence(base_checkpoint_evidence)
    output = tmp_path / "receipt.json"

    result = _run("tools/evaluate/score_rpc_fewshot.py", "--evidence", str(evidence), "--reference-evidence", str(reference), "--condition", str(condition), "--reference-condition", str(reference_condition), "--ground-truth-manifest", str(ground_truth), "--base-checkpoint-evidence", str(base_checkpoint_evidence), "--output", str(output))

    assert result.returncode != 0
    assert "--trusted-rpc-root" in result.stderr
    assert not output.exists()


def test_score_cli_rejects_evidence_that_omits_a_locked_ground_truth_object(
    tmp_path: Path,
):
    candidate_receipt = _task4_receipt(
        condition_index=0, output_uri="file:///candidate"
    )
    reference_receipt = _task4_receipt(
        condition_index=1, output_uri="file:///reference"
    )
    candidate_id = candidate_receipt["condition"]["condition_id"]
    reference_id = reference_receipt["condition"]["condition_id"]
    evidence = tmp_path / "incomplete-evidence.jsonl"
    reference = tmp_path / "complete-reference.jsonl"
    condition = tmp_path / "candidate-condition.json"
    reference_condition = tmp_path / "reference-condition.json"
    ground_truth = tmp_path / "locked-ground-truth.json"
    base_checkpoint_evidence = tmp_path / "base-checkpoint.json"
    output = tmp_path / "receipt.json"
    evidence.write_text(_canonical(_evidence(candidate_id)) + "\n", encoding="utf-8")
    reference.write_text(
        _canonical(_evidence(reference_id))
        + "\n"
        + _canonical(
            _evidence(
                reference_id,
                sample_id="base",
                truth_category_id=2,
                predicted_category_id=2,
            )
        )
        + "\n",
        encoding="utf-8",
    )
    condition.write_text(_canonical(candidate_receipt), encoding="utf-8")
    reference_condition.write_text(_canonical(reference_receipt), encoding="utf-8")
    _write_locked_ground_truth(ground_truth)
    _write_base_checkpoint_evidence(base_checkpoint_evidence)

    result = _run(
        "tools/evaluate/score_rpc_fewshot.py",
        "--evidence",
        str(evidence),
        "--reference-evidence",
        str(reference),
        "--condition",
        str(condition),
        "--reference-condition",
        str(reference_condition),
        "--ground-truth-manifest",
        str(ground_truth),
        "--base-checkpoint-evidence",
        str(base_checkpoint_evidence),
        "--output",
        str(output),
    )

    assert result.returncode != 0
    assert "--trusted-rpc-root" in result.stderr
    assert not output.exists()


def test_score_cli_requires_the_bound_cohort_hash_to_equal_ground_truth_bytes(
    tmp_path: Path,
):
    candidate_receipt = _task4_receipt(
        condition_index=0,
        output_uri="file:///candidate",
        cohort_manifest_sha256="9" * 64,
    )
    reference_receipt = _task4_receipt(
        condition_index=1,
        output_uri="file:///reference",
        cohort_manifest_sha256="9" * 64,
    )
    candidate_id = candidate_receipt["condition"]["condition_id"]
    reference_id = reference_receipt["condition"]["condition_id"]
    evidence = tmp_path / "candidate.jsonl"
    reference = tmp_path / "reference.jsonl"
    condition = tmp_path / "candidate-condition.json"
    reference_condition = tmp_path / "reference-condition.json"
    ground_truth = tmp_path / "locked-ground-truth.json"
    base_checkpoint_evidence = tmp_path / "base-checkpoint.json"
    output = tmp_path / "receipt.json"
    evidence.write_text(
        _canonical(_evidence(candidate_id))
        + "\n"
        + _canonical(
            _evidence(
                candidate_id,
                sample_id="base",
                truth_category_id=2,
                predicted_category_id=2,
            )
        )
        + "\n",
        encoding="utf-8",
    )
    reference.write_text(
        _canonical(_evidence(reference_id))
        + "\n"
        + _canonical(
            _evidence(
                reference_id,
                sample_id="base",
                truth_category_id=2,
                predicted_category_id=2,
            )
        )
        + "\n",
        encoding="utf-8",
    )
    condition.write_text(_canonical(candidate_receipt), encoding="utf-8")
    reference_condition.write_text(_canonical(reference_receipt), encoding="utf-8")
    _write_locked_ground_truth(ground_truth)
    _write_base_checkpoint_evidence(base_checkpoint_evidence)

    result = _run(
        "tools/evaluate/score_rpc_fewshot.py",
        "--evidence",
        str(evidence),
        "--reference-evidence",
        str(reference),
        "--condition",
        str(condition),
        "--reference-condition",
        str(reference_condition),
        "--ground-truth-manifest",
        str(ground_truth),
        "--base-checkpoint-evidence",
        str(base_checkpoint_evidence),
        "--output",
        str(output),
    )

    assert result.returncode != 0
    assert "--trusted-rpc-root" in result.stderr
    assert not output.exists()


def test_score_cli_requires_trusted_rpc_root_for_a_valid_task4_receipt(tmp_path: Path):
    candidate_receipt = _task4_receipt(condition_index=0, output_uri="file:///candidate")
    reference_receipt = _task4_receipt(condition_index=1, output_uri="file:///reference")
    candidate_id = candidate_receipt["condition"]["condition_id"]
    reference_id = reference_receipt["condition"]["condition_id"]
    evidence = tmp_path / "evidence.jsonl"
    reference = tmp_path / "reference.jsonl"
    condition = tmp_path / "condition.json"
    reference_condition = tmp_path / "reference-condition.json"
    ground_truth = tmp_path / "locked-ground-truth.json"
    base_checkpoint_evidence = tmp_path / "base-checkpoint.json"
    output = tmp_path / "receipt.json"
    evidence.write_text(
        _canonical(
            _evidence(candidate_id, dinov3_global_scores=[0.1, 0.9])
        )
        + "\n"
        + _canonical(_evidence(candidate_id, sample_id="base", truth_category_id=2, predicted_category_id=2)) + "\n",
        encoding="utf-8",
    )
    reference.write_text(
        _canonical(_evidence(reference_id)) + "\n"
        + _canonical(_evidence(reference_id, sample_id="base", truth_category_id=2, predicted_category_id=2)) + "\n",
        encoding="utf-8",
    )
    condition.write_text(_canonical(candidate_receipt), encoding="utf-8")
    reference_condition.write_text(_canonical(reference_receipt), encoding="utf-8")
    _write_locked_ground_truth(ground_truth)
    _write_base_checkpoint_evidence(base_checkpoint_evidence)

    result = _run("tools/evaluate/score_rpc_fewshot.py", "--evidence", str(evidence), "--reference-evidence", str(reference), "--condition", str(condition), "--reference-condition", str(reference_condition), "--ground-truth-manifest", str(ground_truth), "--base-checkpoint-evidence", str(base_checkpoint_evidence), "--output", str(output))

    assert result.returncode != 0
    assert "--trusted-rpc-root" in result.stderr
    assert not output.exists()


def test_score_cli_rejects_equal_cohorts_bound_to_different_manifest_hashes(tmp_path: Path):
    candidate_receipt = _task4_receipt(condition_index=0, output_uri="file:///candidate")
    reference_receipt = _task4_receipt(
        condition_index=1, output_uri="file:///reference", cohort_manifest_sha256="2" * 64
    )
    candidate_id = candidate_receipt["condition"]["condition_id"]
    reference_id = reference_receipt["condition"]["condition_id"]
    evidence = tmp_path / "evidence.jsonl"
    reference = tmp_path / "reference.jsonl"
    condition = tmp_path / "condition.json"
    reference_condition = tmp_path / "reference-condition.json"
    ground_truth = tmp_path / "locked-ground-truth.json"
    base_checkpoint_evidence = tmp_path / "base-checkpoint.json"
    output = tmp_path / "receipt.json"
    evidence.write_text(
        _canonical(_evidence(candidate_id)) + "\n"
        + _canonical(_evidence(candidate_id, sample_id="base", truth_category_id=2, predicted_category_id=2)) + "\n",
        encoding="utf-8",
    )
    reference.write_text(
        _canonical(_evidence(reference_id)) + "\n"
        + _canonical(_evidence(reference_id, sample_id="base", truth_category_id=2, predicted_category_id=2)) + "\n",
        encoding="utf-8",
    )
    condition.write_text(_canonical(candidate_receipt), encoding="utf-8")
    reference_condition.write_text(_canonical(reference_receipt), encoding="utf-8")
    _write_locked_ground_truth(ground_truth)
    _write_base_checkpoint_evidence(base_checkpoint_evidence)

    result = _run("tools/evaluate/score_rpc_fewshot.py", "--evidence", str(evidence), "--reference-evidence", str(reference), "--condition", str(condition), "--reference-condition", str(reference_condition), "--ground-truth-manifest", str(ground_truth), "--base-checkpoint-evidence", str(base_checkpoint_evidence), "--output", str(output))

    assert result.returncode != 0
    assert "--trusted-rpc-root" in result.stderr
    assert not output.exists()


def test_score_receipt_uses_evidence_digest_from_the_bytes_it_parsed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    module = _score_module()
    candidate_receipt = _task4_receipt(condition_index=0, output_uri="file:///candidate")
    reference_receipt = _task4_receipt(condition_index=1, output_uri="file:///reference")
    candidate_id = candidate_receipt["condition"]["condition_id"]
    reference_id = reference_receipt["condition"]["condition_id"]
    evidence = tmp_path / "evidence.jsonl"
    reference = tmp_path / "reference.jsonl"
    condition = tmp_path / "condition.json"
    reference_condition = tmp_path / "reference-condition.json"
    ground_truth = tmp_path / "locked-ground-truth.json"
    base_checkpoint_evidence = tmp_path / "base-checkpoint.json"
    output = tmp_path / "receipt.json"
    parsed_bytes = (
        _canonical(_evidence(candidate_id)).encode("utf-8") + b"\n"
        + _canonical(_evidence(candidate_id, sample_id="base", truth_category_id=2, predicted_category_id=2)).encode("utf-8") + b"\n"
    )
    replacement_bytes = (
        _canonical(_evidence(candidate_id, repvit_global_scores=[0.8, 0.2])).encode("utf-8") + b"\n"
        + _canonical(_evidence(candidate_id, sample_id="base", truth_category_id=2, predicted_category_id=2, repvit_global_scores=[0.2, 0.8])).encode("utf-8") + b"\n"
    )
    evidence.write_bytes(parsed_bytes)
    reference.write_text(
        _canonical(_evidence(reference_id)) + "\n"
        + _canonical(_evidence(reference_id, sample_id="base", truth_category_id=2, predicted_category_id=2)) + "\n",
        encoding="utf-8",
    )
    condition.write_text(_canonical(candidate_receipt), encoding="utf-8")
    reference_condition.write_text(_canonical(reference_receipt), encoding="utf-8")
    _write_locked_ground_truth(ground_truth)
    _write_base_checkpoint_evidence(base_checkpoint_evidence)
    real_loader = module.load_canonical_jsonl

    def replace_after_parse(path: Path):
        loaded = real_loader(path)
        if path == evidence:
            evidence.write_bytes(replacement_bytes)
        return loaded

    monkeypatch.setattr(module, "load_canonical_jsonl", replace_after_parse)
    # This regression isolates read-once evidence bytes; role routing is
    # covered separately and this legacy fixture intentionally contains only
    # test2019 lineage.
    monkeypatch.setattr(
        _rpc_scoring,
        "load_stage_ground_truth",
        lambda path, *, stage, trusted_source_root: _rpc_scoring.load_locked_ground_truth(
            path, trusted_source_root=trusted_source_root
        ),
    )
    module.score(
        evidence,
        reference,
        condition,
        reference_condition,
        ground_truth,
        base_checkpoint_evidence,
        output,
        trusted_index=_trusted_index(),
    )

    receipt = json.loads(output.read_text(encoding="utf-8"))
    assert receipt["candidate_provenance"]["evidence_sha256"] == hashlib.sha256(parsed_bytes).hexdigest()
    assert receipt["candidate_provenance"]["evidence_sha256"] != hashlib.sha256(replacement_bytes).hexdigest()
