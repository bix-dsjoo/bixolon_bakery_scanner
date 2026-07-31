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

from bakery_scanner.experiments.rpc_protocol import (
    ExperimentReceipt,
    FoldBaseArtifact,
    ScoringPlan,
    stage_one_conditions,
)


ROOT = Path(__file__).parents[2]
HASHES = {
    "condition_manifest_sha256": "a" * 64,
    "model_sha256": "b" * 64,
    "support_sha256": "c" * 64,
    "calibration_sha256": "d" * 64,
    "policy_sha256": "e" * 64,
    "preprocessing_sha256": "f" * 64,
    "code_sha256": "0" * 64,
}
LOCKED_GROUND_TRUTH = {
    "schema_version": 1,
    "kind": "rpc-fewshot-locked-ground-truth",
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
        **HASHES,
        **overrides,
    }


def _canonical(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _write_base_checkpoint_evidence(path: Path) -> None:
    path.write_bytes(BASE_CHECKPOINT_EVIDENCE_BYTES)


def _write_locked_ground_truth(path: Path) -> None:
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
    assert "provenance" in result.stderr
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
    assert "locked ground-truth identity" in result.stderr
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
    assert "locked ground-truth manifest SHA-256 mismatch" in result.stderr
    assert not output.exists()


def test_score_cli_scores_a_canonical_task4_receipt_and_records_full_provenance(tmp_path: Path):
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

    assert result.returncode == 0, result.stderr
    receipt = json.loads(output.read_text(encoding="utf-8"))
    assert receipt["candidate_provenance"]["evidence_sha256"]
    assert (
        receipt["candidate_provenance"]["cohort_manifest_sha256"]
        == LOCKED_GROUND_TRUTH_SHA256
    )
    assert receipt["locked_ground_truth"] == {
        "burst_count": 1,
        "manifest_sha256": LOCKED_GROUND_TRUTH_SHA256,
        "object_count": 2,
        "sample_count": 2,
    }
    assert receipt["candidate_provenance"]["model_sha256"] == "b" * 64
    assert set(receipt["candidate_branch_top1"]) == {
        "repvit_global",
        "dinov3_global",
        "dinov3_local",
    }
    assert (
        receipt["candidate_branch_top1"]["repvit_global"]["novel_macro_recall"]
        == 1.0
    )
    assert (
        receipt["candidate_branch_top1"]["dinov3_global"]["novel_macro_recall"]
        == 0.0
    )
    assert receipt["stage1_global_top1_agreement"] == {
        "candidate": 0.5,
        "reference": 1.0,
    }
    assert "candidate_forced_top1" not in receipt
    assert receipt["candidate_full_system"]["registered_coverage"] == 1.0
    assert receipt["paired_bootstrap_95"]["seed"] == 7
    assert receipt["paired_bootstrap_95"]["replicates"] == 10
    assert receipt["decision_status"] == "non_final"
    assert "final_pass" not in receipt


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
    assert "cohort manifest" in result.stderr
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
    module.score(
        evidence,
        reference,
        condition,
        reference_condition,
        ground_truth,
        base_checkpoint_evidence,
        output,
    )

    receipt = json.loads(output.read_text(encoding="utf-8"))
    assert receipt["candidate_provenance"]["evidence_sha256"] == hashlib.sha256(parsed_bytes).hexdigest()
    assert receipt["candidate_provenance"]["evidence_sha256"] != hashlib.sha256(replacement_bytes).hexdigest()
