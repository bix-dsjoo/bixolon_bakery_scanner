"""Final-decision controls for immutable RPC few-shot scoring plans."""

from __future__ import annotations

from dataclasses import replace
from functools import lru_cache
import hashlib
import importlib.util
import sys
import tempfile
from pathlib import Path

import pytest
import yaml

from bakery_scanner.experiments.rpc_manifest import canonical_json_bytes
from bakery_scanner.experiments.rpc_protocol import (
    ExperimentReceipt,
    FoldBaseArtifact,
    ScoringPlan,
    StageFourConfirmationReceipt,
    StageFourSelection,
    confirmation_conditions,
    locked_conditions,
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
            "burst_id": "burst",
            "difficulty": "E",
            "object_id": 1,
            "sample_id": "novel",
            "truth_category_id": 1,
        },
        {
            "burst_id": "burst",
            "difficulty": "E",
            "object_id": 2,
            "sample_id": "base",
            "truth_category_id": 2,
        },
    ],
}
LOCKED_GROUND_TRUTH_BYTES = canonical_json_bytes(LOCKED_GROUND_TRUTH)
LOCKED_GROUND_TRUTH_SHA256 = hashlib.sha256(LOCKED_GROUND_TRUTH_BYTES).hexdigest()
_STAGE_FOUR_TEMPORARY_DIRECTORY = tempfile.TemporaryDirectory(
    prefix="rpc-stage-four-test-"
)
_STAGE_FOUR_ARTIFACT_ROOT = Path(_STAGE_FOUR_TEMPORARY_DIRECTORY.name)


def _score_module():
    specification = importlib.util.spec_from_file_location(
        "score_rpc_fewshot_scoring_plan_test",
        ROOT / "tools/evaluate/score_rpc_fewshot.py",
    )
    assert specification is not None and specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    sys.modules[specification.name] = module
    specification.loader.exec_module(module)
    return module


def _cell_conditions(*, seeds: tuple[int, ...] = (101,), folds: tuple[int, ...] = (0,)):
    return tuple(
        condition
        for condition in stage_one_conditions(seeds=seeds, folds=folds)
        if (condition.method, condition.selector, condition.shot_count) == ("m0", "div", 1)
    )


def _locked_candidate_cells(
    *, seeds: tuple[int, ...] = (101,), folds: tuple[int, ...] = (0,)
):
    return tuple(
        condition
        for fold in folds
        for seed in seeds
        for condition in locked_conditions(
            _locked_selection(fold=fold, seed=seed),
            confirmation_score_receipt_paths=_locked_selection_artifacts(
                fold, seed
            )[1],
        )
        if condition.shot_count == 5
    )


def _locked_reference_cells(
    *, seeds: tuple[int, ...] = (101,), folds: tuple[int, ...] = (0,)
):
    return tuple(
        condition
        for fold in folds
        for seed in seeds
        for condition in locked_conditions(
            _locked_selection(fold=fold, seed=seed),
            confirmation_score_receipt_paths=_locked_selection_artifacts(
                fold, seed
            )[1],
        )
        if condition.shot_count == 150
    )


def _locked_selection(*, fold: int, seed: int) -> StageFourSelection:
    return _locked_selection_artifacts(fold, seed)[0]


@lru_cache(maxsize=None)
def _locked_selection_artifacts(
    fold: int, seed: int
) -> tuple[StageFourSelection, tuple[Path, ...]]:
    confirmations = confirmation_conditions(
        ("m0", "div"),
        shot_counts=(3, 5, 10, 150),
        seeds=(seed,),
        folds=(fold,),
    )
    paths: list[Path] = []
    claims: list[StageFourConfirmationReceipt] = []
    reference = next(item for item in confirmations if item.shot_count == 150)
    for index, condition in enumerate(confirmations):
        candidate_plan = _plan(
            (condition.condition_id,), folds=(fold,), seeds=(seed,)
        )
        reference_plan = _plan(
            (reference.condition_id,), folds=(fold,), seeds=(seed,)
        )
        value = {
            "schema_version": 2,
            "kind": "rpc-fewshot-confirmation-score-receipt",
            "status": "completed",
            "decision_status": "provisional",
            "aggregate_stage": "confirmation",
            "decision_scope": "complete_confirmation_fold_seed_aggregate",
            "provisional_pass": condition.shot_count != 3,
            "condition_count": 1,
            "candidate_conditions": [condition.to_dict()],
            "reference_conditions": [reference.to_dict()],
            "candidate_condition_ids": [condition.condition_id],
            "reference_condition_ids": [reference.condition_id],
            "candidate_scoring_plan": candidate_plan.to_dict(),
            "reference_scoring_plan": reference_plan.to_dict(),
            "cohort": {"base_category_ids": [2], "novel_category_ids": [1]},
        }
        path = _STAGE_FOUR_ARTIFACT_ROOT / f"confirmation-{fold}-{seed}-{index}.json"
        content = canonical_json_bytes(value)
        path.write_bytes(content)
        paths.append(path)
        claims.append(
            StageFourConfirmationReceipt(
                condition=condition,
                score_receipt_sha256=hashlib.sha256(content).hexdigest(),
                provisional_pass=condition.shot_count != 3,
            )
        )
    return StageFourSelection(tuple(claims)), tuple(paths)


def _confirmation_cells(
    method: tuple[str, str],
    shot_count: int,
    *,
    seeds: tuple[int, ...] = (101,),
    folds: tuple[int, ...] = (0,),
):
    return tuple(
        condition
        for condition in confirmation_conditions(
            method,
            shot_counts=(1, 3, 5, 150),
            seeds=seeds,
            folds=folds,
        )
        if condition.shot_count == shot_count
    )


def _plan(condition_ids: tuple[str, ...], *, folds=(0,), seeds=(101,)) -> ScoringPlan:
    return ScoringPlan(
        bootstrap_seed=20260731,
        bootstrap_replicates=1000,
        folds=folds,
        support_seeds=seeds,
        expected_condition_ids=condition_ids,
        cohort_id="rpc-2019-200-category-five-fold-v1",
        registered_category_ids=(1, 2),
        fold_base_artifacts=tuple(
            FoldBaseArtifact(
                fold=fold,
                checkpoint_sha256=f"{fold + 2:x}" * 64,
                evidence_sha256=f"{fold + 3:x}" * 64,
            )
            for fold in folds
        ),
    )


def _receipt(plan: ScoringPlan) -> ExperimentReceipt:
    condition = _cell_conditions()[0]
    base = next(item for item in plan.fold_base_artifacts if item.fold == condition.fold)
    return ExperimentReceipt.completed(
        condition,
        **HASHES,
        cohort_manifest_sha256=LOCKED_GROUND_TRUTH_SHA256,
        novel_category_ids=(1,),
        base_category_ids=(2,),
        scoring_plan=plan,
        base_checkpoint_sha256=base.checkpoint_sha256,
        base_checkpoint_evidence_sha256=base.evidence_sha256,
        environment_lock_digest="sha256:environment",
        output_uri="file:///external/run",
    )


def _write_canonical(path: Path, value: object) -> None:
    path.write_bytes(canonical_json_bytes(value))


def _write_evidence(
    path: Path,
    condition,
    *,
    novel_prediction: int | None = 1,
    base_prediction: int | None = 2,
) -> str:
    rows = (
        {
            "sample_id": "novel",
            "object_id": 1,
            "condition_id": condition.condition_id,
            "fold": condition.fold,
            "difficulty": "E",
            "burst_id": "burst",
            "truth_category_id": 1,
            "predicted_category_id": novel_prediction,
            "score_category_ids": [1, 2],
            "repvit_global_scores": [0.9, 0.1],
            "dinov3_global_scores": [0.9, 0.1],
            "dinov3_local_scores": [0.9, 0.1],
            **HASHES,
        },
        {
            "sample_id": "base",
            "object_id": 2,
            "condition_id": condition.condition_id,
            "fold": condition.fold,
            "difficulty": "E",
            "burst_id": "burst",
            "truth_category_id": 2,
            "predicted_category_id": base_prediction,
            "score_category_ids": [1, 2],
            "repvit_global_scores": [0.1, 0.9],
            "dinov3_global_scores": [0.1, 0.9],
            "dinov3_local_scores": [0.1, 0.9],
            **HASHES,
        },
    )
    content = b"".join(canonical_json_bytes(row) + b"\n" for row in rows)
    path.write_bytes(content)
    return hashlib.sha256(content).hexdigest()


def _write_ground_truth(path: Path) -> None:
    path.write_bytes(LOCKED_GROUND_TRUTH_BYTES)


def _non_final_score(
    candidate,
    reference,
    candidate_plan: ScoringPlan,
    reference_plan: ScoringPlan,
    *,
    candidate_evidence_sha256: str,
    reference_evidence_sha256: str,
) -> dict[str, object]:
    candidate_base = next(
        item for item in candidate_plan.fold_base_artifacts if item.fold == candidate.fold
    )
    reference_base = next(
        item for item in reference_plan.fold_base_artifacts if item.fold == reference.fold
    )
    result = {
        "schema_version": 2,
        "kind": "rpc-fewshot-score-receipt",
        "status": "completed",
        "decision_status": "non_final",
        "candidate_condition_id": candidate.condition_id,
        "reference_condition_id": reference.condition_id,
        "candidate_condition": candidate.to_dict(),
        "reference_condition": reference.to_dict(),
        "candidate_scoring_plan": candidate_plan.to_dict(),
        "reference_scoring_plan": reference_plan.to_dict(),
        "cohort": {
            "base_category_ids": [2],
            "novel_category_ids": [1],
        },
        "candidate_provenance": {
            "condition_id": candidate.condition_id,
            "evidence_sha256": candidate_evidence_sha256,
            "cohort_manifest_sha256": LOCKED_GROUND_TRUTH_SHA256,
            "base_checkpoint_sha256": candidate_base.checkpoint_sha256,
            "base_checkpoint_evidence_sha256": candidate_base.evidence_sha256,
            "scoring_plan_sha256": candidate_plan.sha256,
            **HASHES,
        },
        "reference_provenance": {
            "condition_id": reference.condition_id,
            "evidence_sha256": reference_evidence_sha256,
            "cohort_manifest_sha256": LOCKED_GROUND_TRUTH_SHA256,
            "base_checkpoint_sha256": reference_base.checkpoint_sha256,
            "base_checkpoint_evidence_sha256": reference_base.evidence_sha256,
            "scoring_plan_sha256": reference_plan.sha256,
            **HASHES,
        },
        "fold_base_checkpoint": {
            "base_macro_final_correct_recall": 1.0,
            "checkpoint_sha256": candidate_base.checkpoint_sha256,
            "evidence_sha256": candidate_base.evidence_sha256,
            "fold": candidate.fold,
        },
        "locked_ground_truth": {
            "burst_count": 1,
            "manifest_sha256": LOCKED_GROUND_TRUTH_SHA256,
            "object_count": 2,
            "sample_count": 2,
        },
        # Deliberately contradictory cached inputs prove the final decision is
        # recomputed from the bound raw evidence rather than receipt booleans.
        "minimum_rule_inputs": {
            "registered_coverage": 0.0,
            "novel_macro_recall_lower_delta": -0.01,
            "novel_wrong_registered_sku_rate_upper_delta": 0.0,
            "novel_loss_over_10pp_fraction": 0.0,
            "candidate_base_macro_final_correct_recall": 0.99,
            "fold_base_checkpoint_macro_final_correct_recall": 1.0,
        },
    }
    if candidate.stage == reference.stage == "locked":
        selection, paths = _locked_selection_artifacts(
            candidate.fold, candidate.support_seed
        )
        result["stage_four_selection"] = selection.to_dict()
        result["stage_four_confirmation_score_receipt_paths"] = [
            str(path) for path in paths
        ]
    return result


def test_scoring_plan_is_immutable_and_receipt_binds_all_decision_inputs():
    condition = _cell_conditions()[0]
    plan = _plan((condition.condition_id,))
    payload = _receipt(plan).to_dict()

    assert payload["schema_version"] == 2
    assert payload["kind"] == "rpc-fewshot-experiment-receipt"
    assert payload["scoring_plan"]["schema_version"] == 1
    assert payload["scoring_plan"]["bootstrap_seed"] == 20260731
    assert payload["scoring_plan"]["bootstrap_replicates"] == 1000
    assert payload["scoring_plan"]["expected_condition_ids"] == [condition.condition_id]
    assert payload["scoring_plan"]["registered_category_ids"] == [1, 2]
    assert payload["scoring_plan"]["fold_base_artifacts"] == [
        {
            "checkpoint_sha256": "2" * 64,
            "evidence_sha256": "3" * 64,
            "fold": 0,
        }
    ]
    assert payload["fold_base_checkpoint"] == {
        "checkpoint_sha256": "2" * 64,
        "evidence_sha256": "3" * 64,
        "fold": 0,
    }

    with pytest.raises(ValueError, match="expected condition"):
        _receipt(replace(plan, expected_condition_ids=("rpc-other",)))
    with pytest.raises(ValueError, match="exactly cover"):
        replace(
            plan,
            fold_base_artifacts=(
                plan.fold_base_artifacts[0],
                FoldBaseArtifact(
                    fold=0,
                    checkpoint_sha256="4" * 64,
                    evidence_sha256="5" * 64,
                ),
            ),
        )
    with pytest.raises(ValueError, match="tuple"):
        ScoringPlan(
            bootstrap_seed=1,
            bootstrap_replicates=10,
            folds=[0],  # type: ignore[arg-type]
            support_seeds=(101,),
            expected_condition_ids=(condition.condition_id,),
            cohort_id="rpc",
            registered_category_ids=(1, 2),
            fold_base_artifacts=(
                FoldBaseArtifact(
                    fold=0,
                    checkpoint_sha256="2" * 64,
                    evidence_sha256="3" * 64,
                ),
            ),
        )
    with pytest.raises(ValueError, match="complete fold/seed matrix"):
        ScoringPlan(
            bootstrap_seed=1,
            bootstrap_replicates=10,
            folds=(0, 1),
            support_seeds=(101, 102),
            expected_condition_ids=(condition.condition_id,),
            cohort_id="rpc",
            registered_category_ids=(1, 2),
            fold_base_artifacts=(
                FoldBaseArtifact(
                    fold=0,
                    checkpoint_sha256="2" * 64,
                    evidence_sha256="3" * 64,
                ),
                FoldBaseArtifact(
                    fold=1,
                    checkpoint_sha256="4" * 64,
                    evidence_sha256="5" * 64,
                ),
            ),
        )


def test_yaml_scoring_plan_declares_bootstrap_matrix_ids_and_cohort():
    payload = yaml.safe_load(
        (ROOT / "experiments/20260731-rpc-fewshot/experiment.yaml").read_text(encoding="utf-8")
    )
    plan = payload["scoring_plan"]
    expected = _cell_conditions(
        seeds=tuple(payload["support_seeds"]),
        folds=tuple(payload["folds"]),
    )

    assert payload["schema_version"] == 1
    assert payload["status"] == "planned"
    assert plan["bootstrap_seed"] == 20260731
    assert plan["bootstrap_replicates"] == 10000
    assert set(plan["expected_condition_ids"]) == {
        condition.condition_id for condition in expected
    }
    assert plan["registered_category_ids"] == list(range(1, 201))
    assert [item["fold"] for item in plan["fold_base_artifacts"]] == payload["folds"]
    assert all(
        item["checkpoint_sha256"] is None and item["evidence_sha256"] is None
        for item in plan["fold_base_artifacts"]
    )
    with pytest.raises(ValueError, match="invalid scoring plan"):
        ScoringPlan.from_dict(plan)


def test_fold_base_checkpoint_evidence_must_match_receipt_binding():
    module = _score_module()
    condition = _cell_conditions()[0]
    plan = _plan((condition.condition_id,))
    receipt = _receipt(plan).to_dict()
    evidence = {
        "schema_version": 1,
        "kind": "rpc-fewshot-fold-base-checkpoint-evidence",
        "fold": 0,
        "checkpoint_sha256": "2" * 64,
        "cohort_manifest_sha256": LOCKED_GROUND_TRUTH_SHA256,
        "base_category_ids": [2],
        "sample_count": 10,
        "base_macro_final_correct_recall": 0.98,
    }

    assert (
        module.validate_fold_base_checkpoint_evidence(
            receipt,
            evidence,
            evidence_sha256="3" * 64,
        )
        == 0.98
    )
    with pytest.raises(ValueError, match="base checkpoint"):
        module.validate_fold_base_checkpoint_evidence(
            receipt,
            {**evidence, "checkpoint_sha256": "4" * 64},
            evidence_sha256="3" * 64,
        )


def test_scorer_rejects_an_unversioned_condition_receipt():
    module = _score_module()
    condition = _cell_conditions()[0]
    receipt = _receipt(_plan((condition.condition_id,))).to_dict()

    with pytest.raises(ValueError, match="experiment receipt schema"):
        module._condition_scoring_plan({**receipt, "schema_version": 1})


def test_condition_receipt_rejects_nested_condition_fields_that_do_not_match_its_id():
    module = _score_module()
    condition = _cell_conditions()[0]
    receipt = _receipt(_plan((condition.condition_id,))).to_dict()
    receipt["condition"]["method"] = "m1"  # type: ignore[index]

    with pytest.raises(ValueError, match="deterministic"):
        module._condition_scoring_plan(receipt)


def test_score_receipt_rejects_nested_condition_fields_that_do_not_match_its_id():
    module = _score_module()
    candidate = _cell_conditions()[0]
    score_receipt = _non_final_score(
        candidate,
        candidate,
        _plan((candidate.condition_id,)),
        _plan((candidate.condition_id,)),
        candidate_evidence_sha256="1" * 64,
        reference_evidence_sha256="2" * 64,
    )
    score_receipt["candidate_condition"]["stage"] = "locked"  # type: ignore[index]

    with pytest.raises(ValueError, match="deterministic"):
        module._score_receipt_condition(score_receipt, "candidate_condition")


def test_incomplete_fold_seed_aggregate_cannot_emit_final_pass(tmp_path: Path):
    module = _score_module()
    candidates = _locked_candidate_cells(seeds=(101, 102), folds=(0,))
    references = _locked_reference_cells(seeds=(101, 102), folds=(0,))
    candidate_plan = _plan(tuple(row.condition_id for row in candidates), seeds=(101, 102))
    reference_plan = _plan(tuple(row.condition_id for row in references), seeds=(101, 102))
    receipt_path = tmp_path / "one.json"
    evidence_path = tmp_path / "one-candidate.jsonl"
    reference_evidence_path = tmp_path / "one-reference.jsonl"
    output = tmp_path / "aggregate.json"
    candidate_evidence_sha256 = _write_evidence(evidence_path, candidates[0])
    reference_evidence_sha256 = _write_evidence(reference_evidence_path, references[0])
    _write_canonical(
        receipt_path,
        _non_final_score(
            candidates[0],
            references[0],
            candidate_plan,
            reference_plan,
            candidate_evidence_sha256=candidate_evidence_sha256,
            reference_evidence_sha256=reference_evidence_sha256,
        ),
    )
    ground_truth_path = tmp_path / "locked-ground-truth.json"
    _write_ground_truth(ground_truth_path)

    with pytest.raises(ValueError, match="complete declared fold/seed"):
        module.aggregate_score_receipts(
            (receipt_path,),
            output,
            evidence_paths=(evidence_path,),
            reference_evidence_paths=(reference_evidence_path,),
            ground_truth_manifest_path=ground_truth_path,
        )
    assert not output.exists()


def test_stage_one_aggregate_cannot_establish_a_final_minimum(tmp_path: Path):
    module = _score_module()
    candidates = _cell_conditions(seeds=(101, 102), folds=(0,))
    references = tuple(
        condition
        for condition in stage_one_conditions(seeds=(101, 102), folds=(0,))
        if (condition.method, condition.selector, condition.shot_count) == ("m0", "div", 1)
    )
    candidate_plan = _plan(tuple(row.condition_id for row in candidates), seeds=(101, 102))
    reference_plan = _plan(tuple(row.condition_id for row in references), seeds=(101, 102))
    paths = []
    evidence_paths = []
    reference_evidence_paths = []
    for index, (candidate, reference) in enumerate(zip(candidates, references, strict=True)):
        path = tmp_path / f"score-{index}.json"
        evidence_path = tmp_path / f"candidate-{index}.jsonl"
        reference_evidence_path = tmp_path / f"reference-{index}.jsonl"
        candidate_evidence_sha256 = _write_evidence(evidence_path, candidate)
        reference_evidence_sha256 = _write_evidence(reference_evidence_path, reference)
        _write_canonical(
            path,
            _non_final_score(
                candidate,
                reference,
                candidate_plan,
                reference_plan,
                candidate_evidence_sha256=candidate_evidence_sha256,
                reference_evidence_sha256=reference_evidence_sha256,
            ),
        )
        paths.append(path)
        evidence_paths.append(evidence_path)
        reference_evidence_paths.append(reference_evidence_path)
    ground_truth_path = tmp_path / "locked-ground-truth.json"
    _write_ground_truth(ground_truth_path)
    output = tmp_path / "aggregate.json"

    with pytest.raises(ValueError, match="confirmation or locked"):
        module.aggregate_score_receipts(
            tuple(paths),
            output,
            evidence_paths=tuple(evidence_paths),
            reference_evidence_paths=tuple(reference_evidence_paths),
            ground_truth_manifest_path=ground_truth_path,
        )
    assert not output.exists()


def test_complete_locked_aggregate_is_the_only_final_boolean(tmp_path: Path):
    module = _score_module()
    candidates = _locked_candidate_cells(seeds=(101, 102), folds=(0,))
    references = _locked_reference_cells(seeds=(101, 102), folds=(0,))
    candidate_plan = _plan(
        tuple(row.condition_id for row in candidates), seeds=(101, 102)
    )
    reference_plan = _plan(
        tuple(row.condition_id for row in references), seeds=(101, 102)
    )
    paths = []
    evidence_paths = []
    reference_evidence_paths = []
    for index, (candidate, reference) in enumerate(
        zip(candidates, references, strict=True)
    ):
        path = tmp_path / f"locked-score-{index}.json"
        evidence_path = tmp_path / f"locked-candidate-{index}.jsonl"
        reference_evidence_path = tmp_path / f"locked-reference-{index}.jsonl"
        _write_canonical(
            path,
            _non_final_score(
                candidate,
                reference,
                candidate_plan,
                reference_plan,
                candidate_evidence_sha256=_write_evidence(evidence_path, candidate),
                reference_evidence_sha256=_write_evidence(
                    reference_evidence_path, reference
                ),
            ),
        )
        paths.append(path)
        evidence_paths.append(evidence_path)
        reference_evidence_paths.append(reference_evidence_path)
    ground_truth_path = tmp_path / "locked-ground-truth.json"
    _write_ground_truth(ground_truth_path)
    output = tmp_path / "locked-aggregate.json"

    module.aggregate_score_receipts(
        tuple(paths),
        output,
        evidence_paths=tuple(evidence_paths),
        reference_evidence_paths=tuple(reference_evidence_paths),
        ground_truth_manifest_path=ground_truth_path,
    )

    aggregate = module.load_canonical_json(output)
    assert aggregate["aggregate_stage"] == "locked"
    assert aggregate["kind"] == "rpc-fewshot-final-score-receipt"
    assert aggregate["decision_scope"] == "complete_locked_fold_seed_aggregate"
    assert aggregate["decision_status"] == "final"
    assert aggregate["final_pass"] is True
    assert "provisional_pass" not in aggregate


def test_locked_aggregate_rejects_receipts_without_stage_four_confirmation_binding(
    tmp_path: Path,
):
    module = _score_module()
    candidates = _locked_candidate_cells(seeds=(101, 102), folds=(0,))
    references = _locked_reference_cells(seeds=(101, 102), folds=(0,))
    candidate_plan = _plan(tuple(row.condition_id for row in candidates), seeds=(101, 102))
    reference_plan = _plan(tuple(row.condition_id for row in references), seeds=(101, 102))
    paths = []
    evidence_paths = []
    reference_evidence_paths = []
    for index, (candidate, reference) in enumerate(zip(candidates, references, strict=True)):
        path = tmp_path / f"unbound-score-{index}.json"
        evidence_path = tmp_path / f"unbound-candidate-{index}.jsonl"
        reference_evidence_path = tmp_path / f"unbound-reference-{index}.jsonl"
        score = _non_final_score(
            candidate,
            reference,
            candidate_plan,
            reference_plan,
            candidate_evidence_sha256=_write_evidence(evidence_path, candidate),
            reference_evidence_sha256=_write_evidence(reference_evidence_path, reference),
        )
        if index == 0:
            del score["stage_four_selection"]
        _write_canonical(path, score)
        paths.append(path)
        evidence_paths.append(evidence_path)
        reference_evidence_paths.append(reference_evidence_path)
    ground_truth_path = tmp_path / "locked-ground-truth.json"
    _write_ground_truth(ground_truth_path)

    with pytest.raises(ValueError, match="Stage-4 selection"):
        module.aggregate_score_receipts(
            tuple(paths),
            tmp_path / "aggregate.json",
            evidence_paths=tuple(evidence_paths),
            reference_evidence_paths=tuple(reference_evidence_paths),
            ground_truth_manifest_path=ground_truth_path,
        )


def test_locked_aggregate_rejects_unresolvable_stage_four_confirmation_artifact(
    tmp_path: Path,
):
    """A forged path cannot bypass aggregate-time Stage-4 byte verification."""
    module = _score_module()
    candidates = _locked_candidate_cells(seeds=(101, 102), folds=(0,))
    references = _locked_reference_cells(seeds=(101, 102), folds=(0,))
    candidate_plan = _plan(tuple(row.condition_id for row in candidates), seeds=(101, 102))
    reference_plan = _plan(tuple(row.condition_id for row in references), seeds=(101, 102))
    paths = []
    evidence_paths = []
    reference_evidence_paths = []
    for index, (candidate, reference) in enumerate(zip(candidates, references, strict=True)):
        path = tmp_path / f"unresolvable-stage-four-{index}.json"
        evidence_path = tmp_path / f"unresolvable-candidate-{index}.jsonl"
        reference_evidence_path = tmp_path / f"unresolvable-reference-{index}.jsonl"
        score = _non_final_score(
            candidate,
            reference,
            candidate_plan,
            reference_plan,
            candidate_evidence_sha256=_write_evidence(evidence_path, candidate),
            reference_evidence_sha256=_write_evidence(reference_evidence_path, reference),
        )
        if index == 0:
            score["stage_four_confirmation_score_receipt_paths"] = [  # type: ignore[index]
                str(tmp_path / f"does-not-exist-{number}.json")
                for number in range(4)
            ]
        _write_canonical(path, score)
        paths.append(path)
        evidence_paths.append(evidence_path)
        reference_evidence_paths.append(reference_evidence_path)
    ground_truth_path = tmp_path / "locked-ground-truth.json"
    _write_ground_truth(ground_truth_path)

    with pytest.raises(ValueError, match="cannot read Stage-4 confirmation score receipt"):
        module.aggregate_score_receipts(
            tuple(paths),
            tmp_path / "aggregate.json",
            evidence_paths=tuple(evidence_paths),
            reference_evidence_paths=tuple(reference_evidence_paths),
            ground_truth_manifest_path=ground_truth_path,
        )


def test_confirmation_aggregate_is_provisional_and_never_final(tmp_path: Path):
    module = _score_module()
    candidates = _confirmation_cells(
        ("m0", "div"), 5, seeds=(101, 102), folds=(0,)
    )
    references = _confirmation_cells(
        ("m0", "div"), 150, seeds=(101, 102), folds=(0,)
    )
    candidate_plan = _plan(
        tuple(row.condition_id for row in candidates), seeds=(101, 102)
    )
    reference_plan = _plan(
        tuple(row.condition_id for row in references), seeds=(101, 102)
    )
    paths = []
    evidence_paths = []
    reference_evidence_paths = []
    for index, (candidate, reference) in enumerate(
        zip(candidates, references, strict=True)
    ):
        path = tmp_path / f"confirmation-score-{index}.json"
        evidence_path = tmp_path / f"confirmation-candidate-{index}.jsonl"
        reference_evidence_path = tmp_path / f"confirmation-reference-{index}.jsonl"
        _write_canonical(
            path,
            _non_final_score(
                candidate,
                reference,
                candidate_plan,
                reference_plan,
                candidate_evidence_sha256=_write_evidence(evidence_path, candidate),
                reference_evidence_sha256=_write_evidence(
                    reference_evidence_path, reference
                ),
            ),
        )
        paths.append(path)
        evidence_paths.append(evidence_path)
        reference_evidence_paths.append(reference_evidence_path)
    ground_truth_path = tmp_path / "locked-ground-truth.json"
    _write_ground_truth(ground_truth_path)
    output = tmp_path / "confirmation-aggregate.json"

    module.aggregate_score_receipts(
        tuple(paths),
        output,
        evidence_paths=tuple(evidence_paths),
        reference_evidence_paths=tuple(reference_evidence_paths),
        ground_truth_manifest_path=ground_truth_path,
    )

    aggregate = module.load_canonical_json(output)
    assert aggregate["aggregate_stage"] == "confirmation"
    assert aggregate["kind"] == "rpc-fewshot-confirmation-score-receipt"
    assert aggregate["decision_scope"] == "complete_confirmation_fold_seed_aggregate"
    assert aggregate["decision_status"] == "provisional"
    assert aggregate["provisional_pass"] is True
    assert "final_pass" not in aggregate


def test_aggregate_rejects_a_non_150_shot_locked_reference(tmp_path: Path):
    module = _score_module()
    candidates = _locked_candidate_cells(seeds=(101, 102), folds=(0,))
    references = candidates
    candidate_plan = _plan(
        tuple(row.condition_id for row in candidates), seeds=(101, 102)
    )
    reference_plan = _plan(
        tuple(row.condition_id for row in references), seeds=(101, 102)
    )
    paths = []
    evidence_paths = []
    reference_evidence_paths = []
    for index, (candidate, reference) in enumerate(
        zip(candidates, references, strict=True)
    ):
        path = tmp_path / f"bad-reference-score-{index}.json"
        evidence_path = tmp_path / f"bad-reference-candidate-{index}.jsonl"
        reference_evidence_path = tmp_path / f"bad-reference-reference-{index}.jsonl"
        _write_canonical(
            path,
            _non_final_score(
                candidate,
                reference,
                candidate_plan,
                reference_plan,
                candidate_evidence_sha256=_write_evidence(evidence_path, candidate),
                reference_evidence_sha256=_write_evidence(
                    reference_evidence_path, reference
                ),
            ),
        )
        paths.append(path)
        evidence_paths.append(evidence_path)
        reference_evidence_paths.append(reference_evidence_path)
    ground_truth_path = tmp_path / "locked-ground-truth.json"
    _write_ground_truth(ground_truth_path)
    output = tmp_path / "bad-reference-aggregate.json"

    with pytest.raises(ValueError, match="exact 150-shot reference"):
        module.aggregate_score_receipts(
            tuple(paths),
            output,
            evidence_paths=tuple(evidence_paths),
            reference_evidence_paths=tuple(reference_evidence_paths),
            ground_truth_manifest_path=ground_truth_path,
        )
    assert not output.exists()


def test_aggregate_rejects_a_receipt_without_locked_ground_truth_provenance(
    tmp_path: Path,
):
    module = _score_module()
    candidates = _locked_candidate_cells(seeds=(101, 102), folds=(0,))
    references = _locked_reference_cells(seeds=(101, 102), folds=(0,))
    candidate_plan = _plan(
        tuple(row.condition_id for row in candidates), seeds=(101, 102)
    )
    reference_plan = _plan(
        tuple(row.condition_id for row in references), seeds=(101, 102)
    )
    score_paths = []
    evidence_paths = []
    reference_evidence_paths = []
    for index, (candidate, reference) in enumerate(
        zip(candidates, references, strict=True)
    ):
        score_path = tmp_path / f"provenance-score-{index}.json"
        evidence_path = tmp_path / f"provenance-candidate-{index}.jsonl"
        reference_evidence_path = tmp_path / f"provenance-reference-{index}.jsonl"
        score = _non_final_score(
            candidate,
            reference,
            candidate_plan,
            reference_plan,
            candidate_evidence_sha256=_write_evidence(evidence_path, candidate),
            reference_evidence_sha256=_write_evidence(
                reference_evidence_path, reference
            ),
        )
        if index == 0:
            del score["locked_ground_truth"]
        _write_canonical(score_path, score)
        score_paths.append(score_path)
        evidence_paths.append(evidence_path)
        reference_evidence_paths.append(reference_evidence_path)
    ground_truth_path = tmp_path / "locked-ground-truth.json"
    _write_ground_truth(ground_truth_path)

    with pytest.raises(ValueError, match="locked ground-truth provenance"):
        module.aggregate_score_receipts(
            tuple(score_paths),
            tmp_path / "aggregate.json",
            evidence_paths=tuple(evidence_paths),
            reference_evidence_paths=tuple(reference_evidence_paths),
            ground_truth_manifest_path=ground_truth_path,
        )


def test_aggregate_combines_per_sku_loss_across_declared_support_seeds(
    tmp_path: Path,
):
    module = _score_module()
    candidates = _locked_candidate_cells(seeds=(101, 102), folds=(0,))
    references = _locked_reference_cells(seeds=(101, 102), folds=(0,))
    candidate_plan = _plan(tuple(row.condition_id for row in candidates), seeds=(101, 102))
    reference_plan = _plan(tuple(row.condition_id for row in references), seeds=(101, 102))
    score_paths = []
    evidence_paths = []
    reference_evidence_paths = []
    for index, (candidate, reference) in enumerate(zip(candidates, references, strict=True)):
        score_path = tmp_path / f"seed-score-{index}.json"
        evidence_path = tmp_path / f"seed-candidate-{index}.jsonl"
        reference_evidence_path = tmp_path / f"seed-reference-{index}.jsonl"
        candidate_digest = _write_evidence(
            evidence_path,
            candidate,
            novel_prediction=2 if index == 0 else 1,
        )
        reference_digest = _write_evidence(
            reference_evidence_path,
            reference,
            novel_prediction=1 if index == 0 else 2,
        )
        _write_canonical(
            score_path,
            _non_final_score(
                candidate,
                reference,
                candidate_plan,
                reference_plan,
                candidate_evidence_sha256=candidate_digest,
                reference_evidence_sha256=reference_digest,
            ),
        )
        score_paths.append(score_path)
        evidence_paths.append(evidence_path)
        reference_evidence_paths.append(reference_evidence_path)
    ground_truth_path = tmp_path / "locked-ground-truth.json"
    _write_ground_truth(ground_truth_path)
    output = tmp_path / "seed-aggregate.json"

    module.aggregate_score_receipts(
        tuple(score_paths),
        output,
        evidence_paths=tuple(evidence_paths),
        reference_evidence_paths=tuple(reference_evidence_paths),
        ground_truth_manifest_path=ground_truth_path,
    )

    aggregate = module.load_canonical_json(output)
    assert aggregate["minimum_rule_inputs"]["novel_loss_over_10pp_fraction"] == 0.0
    assert aggregate["final_pass"] is True


def test_aggregate_rejects_candidate_reference_cross_seed_pairing(tmp_path: Path):
    module = _score_module()
    candidates = _locked_candidate_cells(seeds=(101, 102), folds=(0,))
    references = _locked_reference_cells(seeds=(101, 102), folds=(0,))
    candidate_plan = _plan(tuple(row.condition_id for row in candidates), seeds=(101, 102))
    reference_plan = _plan(tuple(row.condition_id for row in references), seeds=(101, 102))
    paths = []
    evidence_paths = []
    reference_evidence_paths = []
    for index, (candidate, reference) in enumerate(
        zip(candidates, reversed(references), strict=True)
    ):
        path = tmp_path / f"cross-seed-{index}.json"
        evidence_path = tmp_path / f"cross-candidate-{index}.jsonl"
        reference_evidence_path = tmp_path / f"cross-reference-{index}.jsonl"
        candidate_evidence_sha256 = _write_evidence(evidence_path, candidate)
        reference_evidence_sha256 = _write_evidence(reference_evidence_path, reference)
        _write_canonical(
            path,
            _non_final_score(
                candidate,
                reference,
                candidate_plan,
                reference_plan,
                candidate_evidence_sha256=candidate_evidence_sha256,
                reference_evidence_sha256=reference_evidence_sha256,
            ),
        )
        paths.append(path)
        evidence_paths.append(evidence_path)
        reference_evidence_paths.append(reference_evidence_path)
    ground_truth_path = tmp_path / "locked-ground-truth.json"
    _write_ground_truth(ground_truth_path)

    with pytest.raises(ValueError, match="paired fold/seed"):
        module.aggregate_score_receipts(
            tuple(paths),
            tmp_path / "aggregate.json",
            evidence_paths=tuple(evidence_paths),
            reference_evidence_paths=tuple(reference_evidence_paths),
            ground_truth_manifest_path=ground_truth_path,
        )


def test_aggregate_rejects_raw_evidence_that_does_not_match_receipt_digest(
    tmp_path: Path,
):
    module = _score_module()
    candidates = _locked_candidate_cells(seeds=(101, 102), folds=(0,))
    references = _locked_reference_cells(seeds=(101, 102), folds=(0,))
    candidate_plan = _plan(tuple(row.condition_id for row in candidates), seeds=(101, 102))
    reference_plan = _plan(tuple(row.condition_id for row in references), seeds=(101, 102))
    score_paths = []
    evidence_paths = []
    reference_evidence_paths = []
    for index, (candidate, reference) in enumerate(zip(candidates, references, strict=True)):
        score_path = tmp_path / f"digest-score-{index}.json"
        evidence_path = tmp_path / f"digest-candidate-{index}.jsonl"
        reference_evidence_path = tmp_path / f"digest-reference-{index}.jsonl"
        candidate_digest = _write_evidence(evidence_path, candidate)
        reference_digest = _write_evidence(reference_evidence_path, reference)
        if index == 1:
            candidate_digest = "9" * 64
        _write_canonical(
            score_path,
            _non_final_score(
                candidate,
                reference,
                candidate_plan,
                reference_plan,
                candidate_evidence_sha256=candidate_digest,
                reference_evidence_sha256=reference_digest,
            ),
        )
        score_paths.append(score_path)
        evidence_paths.append(evidence_path)
        reference_evidence_paths.append(reference_evidence_path)
    ground_truth_path = tmp_path / "locked-ground-truth.json"
    _write_ground_truth(ground_truth_path)

    with pytest.raises(ValueError, match="candidate evidence SHA-256"):
        module.aggregate_score_receipts(
            tuple(score_paths),
            tmp_path / "digest-aggregate.json",
            evidence_paths=tuple(evidence_paths),
            reference_evidence_paths=tuple(reference_evidence_paths),
            ground_truth_manifest_path=ground_truth_path,
        )


def test_aggregate_rejects_inconsistent_same_fold_base_artifacts(tmp_path: Path):
    module = _score_module()
    candidates = _locked_candidate_cells(seeds=(101, 102), folds=(0,))
    references = _locked_reference_cells(seeds=(101, 102), folds=(0,))
    candidate_plan = _plan(tuple(row.condition_id for row in candidates), seeds=(101, 102))
    reference_plan = _plan(tuple(row.condition_id for row in references), seeds=(101, 102))
    score_paths = []
    evidence_paths = []
    reference_evidence_paths = []
    for index, (candidate, reference) in enumerate(zip(candidates, references, strict=True)):
        score_path = tmp_path / f"base-score-{index}.json"
        evidence_path = tmp_path / f"base-candidate-{index}.jsonl"
        reference_evidence_path = tmp_path / f"base-reference-{index}.jsonl"
        score = _non_final_score(
            candidate,
            reference,
            candidate_plan,
            reference_plan,
            candidate_evidence_sha256=_write_evidence(evidence_path, candidate),
            reference_evidence_sha256=_write_evidence(reference_evidence_path, reference),
        )
        if index == 1:
            score["fold_base_checkpoint"]["evidence_sha256"] = "9" * 64  # type: ignore[index]
        _write_canonical(score_path, score)
        score_paths.append(score_path)
        evidence_paths.append(evidence_path)
        reference_evidence_paths.append(reference_evidence_path)
    ground_truth_path = tmp_path / "locked-ground-truth.json"
    _write_ground_truth(ground_truth_path)

    with pytest.raises(ValueError, match="fold base checkpoint"):
        module.aggregate_score_receipts(
            tuple(score_paths),
            tmp_path / "base-aggregate.json",
            evidence_paths=tuple(evidence_paths),
            reference_evidence_paths=tuple(reference_evidence_paths),
            ground_truth_manifest_path=ground_truth_path,
        )
