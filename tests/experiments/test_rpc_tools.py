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

from bakery_scanner.experiments.rpc_protocol import ExperimentReceipt, stage_one_conditions


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
    return {
        **HASHES,
        "condition": {"condition_id": condition_id, "fold": 0},
        "cohort": {
            "fold": 0,
            "manifest_sha256": "1" * 64,
            "novel_category_ids": [1],
            "base_category_ids": [2],
        },
        "scoring": {"registered_category_ids": [1, 2]},
        "environment_lock_digest": "sha256:environment",
        "output_uri": "file:///external/run",
        "reason": "",
        "status": "completed",
    }


def _task4_receipt(*, condition_index: int, output_uri: str, cohort_manifest_sha256: str = "1" * 64) -> dict[str, object]:
    condition = stage_one_conditions(seeds=(101,), folds=(0,))[condition_index]
    return ExperimentReceipt.completed(
        condition,
        **HASHES,
        cohort_manifest_sha256=cohort_manifest_sha256,
        novel_category_ids=(1,),
        base_category_ids=(2,),
        environment_lock_digest="sha256:environment",
        output_uri=output_uri,
    ).to_dict()


def _evidence(condition_id: str, **overrides: object) -> dict[str, object]:
    return {
        "sample_id": "sample",
        "condition_id": condition_id,
        "fold": 0,
        "difficulty": "E",
        "burst_id": "burst",
        "truth_category_id": 1,
        "predicted_category_id": 1,
        "score_category_ids": [1, 2],
        "scores": [0.9, 0.1],
        **HASHES,
        **overrides,
    }


def _canonical(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


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
    evidence.write_text(_canonical(_evidence("candidate")) + "\n", encoding="utf-8")
    reference.write_text(_canonical(_evidence("reference")) + "\n", encoding="utf-8")
    condition.write_text(_canonical(_receipt("candidate")), encoding="utf-8")
    reference_condition.write_text(_canonical(_receipt("reference")), encoding="utf-8")
    output = tmp_path / "existing.json"
    output.write_text("{}", encoding="utf-8")

    result = _run("tools/evaluate/score_rpc_fewshot.py", "--evidence", str(evidence), "--reference-evidence", str(reference), "--condition", str(condition), "--reference-condition", str(reference_condition), "--output", str(output), "--bootstrap-seed", "7")

    assert result.returncode != 0
    assert "exists" in result.stderr


def test_score_cli_fails_closed_for_provenance_mismatch(tmp_path: Path):
    evidence = tmp_path / "evidence.jsonl"
    reference = tmp_path / "reference.jsonl"
    condition = tmp_path / "condition.json"
    reference_condition = tmp_path / "reference-condition.json"
    evidence.write_text(_canonical(_evidence("candidate", policy_sha256="1" * 64)) + "\n", encoding="utf-8")
    reference.write_text(_canonical(_evidence("reference")) + "\n", encoding="utf-8")
    condition.write_text(_canonical(_receipt("candidate")), encoding="utf-8")
    reference_condition.write_text(_canonical(_receipt("reference")), encoding="utf-8")
    output = tmp_path / "receipt.json"

    result = _run("tools/evaluate/score_rpc_fewshot.py", "--evidence", str(evidence), "--reference-evidence", str(reference), "--condition", str(condition), "--reference-condition", str(reference_condition), "--output", str(output), "--bootstrap-seed", "7")

    assert result.returncode != 0
    assert "provenance" in result.stderr
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
    output = tmp_path / "receipt.json"
    evidence.write_text(
        _canonical(_evidence(candidate_id)) + "\n"
        + _canonical(_evidence(candidate_id, sample_id="base", truth_category_id=2, predicted_category_id=2, scores=[0.1, 0.9])) + "\n",
        encoding="utf-8",
    )
    reference.write_text(
        _canonical(_evidence(reference_id)) + "\n"
        + _canonical(_evidence(reference_id, sample_id="base", truth_category_id=2, predicted_category_id=2, scores=[0.1, 0.9])) + "\n",
        encoding="utf-8",
    )
    condition.write_text(_canonical(candidate_receipt), encoding="utf-8")
    reference_condition.write_text(_canonical(reference_receipt), encoding="utf-8")

    result = _run("tools/evaluate/score_rpc_fewshot.py", "--evidence", str(evidence), "--reference-evidence", str(reference), "--condition", str(condition), "--reference-condition", str(reference_condition), "--output", str(output), "--bootstrap-seed", "7", "--bootstrap-replicates", "10")

    assert result.returncode == 0, result.stderr
    receipt = json.loads(output.read_text(encoding="utf-8"))
    assert receipt["candidate_provenance"]["evidence_sha256"]
    assert receipt["candidate_provenance"]["cohort_manifest_sha256"] == "1" * 64
    assert receipt["candidate_provenance"]["model_sha256"] == "b" * 64
    assert receipt["candidate_forced_top1"]["top1_agreement"] == 1.0
    assert receipt["candidate_full_system"]["registered_coverage"] == 1.0


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
    output = tmp_path / "receipt.json"
    evidence.write_text(
        _canonical(_evidence(candidate_id)) + "\n"
        + _canonical(_evidence(candidate_id, sample_id="base", truth_category_id=2, predicted_category_id=2, scores=[0.1, 0.9])) + "\n",
        encoding="utf-8",
    )
    reference.write_text(
        _canonical(_evidence(reference_id)) + "\n"
        + _canonical(_evidence(reference_id, sample_id="base", truth_category_id=2, predicted_category_id=2, scores=[0.1, 0.9])) + "\n",
        encoding="utf-8",
    )
    condition.write_text(_canonical(candidate_receipt), encoding="utf-8")
    reference_condition.write_text(_canonical(reference_receipt), encoding="utf-8")

    result = _run("tools/evaluate/score_rpc_fewshot.py", "--evidence", str(evidence), "--reference-evidence", str(reference), "--condition", str(condition), "--reference-condition", str(reference_condition), "--output", str(output), "--bootstrap-seed", "7")

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
    output = tmp_path / "receipt.json"
    parsed_bytes = (
        _canonical(_evidence(candidate_id)).encode("utf-8") + b"\n"
        + _canonical(_evidence(candidate_id, sample_id="base", truth_category_id=2, predicted_category_id=2, scores=[0.1, 0.9])).encode("utf-8") + b"\n"
    )
    replacement_bytes = (
        _canonical(_evidence(candidate_id, scores=[0.8, 0.2])).encode("utf-8") + b"\n"
        + _canonical(_evidence(candidate_id, sample_id="base", truth_category_id=2, predicted_category_id=2, scores=[0.2, 0.8])).encode("utf-8") + b"\n"
    )
    evidence.write_bytes(parsed_bytes)
    reference.write_text(
        _canonical(_evidence(reference_id)) + "\n"
        + _canonical(_evidence(reference_id, sample_id="base", truth_category_id=2, predicted_category_id=2, scores=[0.1, 0.9])) + "\n",
        encoding="utf-8",
    )
    condition.write_text(_canonical(candidate_receipt), encoding="utf-8")
    reference_condition.write_text(_canonical(reference_receipt), encoding="utf-8")
    real_loader = module.load_canonical_jsonl

    def replace_after_parse(path: Path):
        loaded = real_loader(path)
        if path == evidence:
            evidence.write_bytes(replacement_bytes)
        return loaded

    monkeypatch.setattr(module, "load_canonical_jsonl", replace_after_parse)
    module.score(evidence, reference, condition, reference_condition, output, bootstrap_seed=7, bootstrap_replicates=10)

    receipt = json.loads(output.read_text(encoding="utf-8"))
    assert receipt["candidate_provenance"]["evidence_sha256"] == hashlib.sha256(parsed_bytes).hexdigest()
    assert receipt["candidate_provenance"]["evidence_sha256"] != hashlib.sha256(replacement_bytes).hexdigest()
