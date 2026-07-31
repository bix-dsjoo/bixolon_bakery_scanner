"""Contract tests for the preregistered RPC few-shot protocol."""

from __future__ import annotations

import json
import hashlib
import importlib.util
import sys
from dataclasses import replace
from pathlib import Path

import pytest

from bakery_scanner.experiments.rpc_protocol import (
    ExperimentCondition,
    ExperimentReceipt,
    FoldBaseArtifact,
    ScoringPlan,
    StageFourConfirmationReceipt,
    StageFourSelection,
    ascending_conditions,
    confirmation_conditions,
    locked_conditions,
    refinement_shots,
    stage_one_conditions,
    write_experiment_receipt,
)
from bakery_scanner.experiments.rpc_manifest import canonical_json_bytes


_HASH = "a" * 64
_COHORT = {
    "cohort_manifest_sha256": "1" * 64,
    "novel_category_ids": (1,),
    "base_category_ids": (2,),
}


def _condition() -> ExperimentCondition:
    return stage_one_conditions(seeds=(101,), folds=(0,))[0]


def _scoring_bindings() -> dict[str, object]:
    condition = _condition()
    return {
        "scoring_plan": ScoringPlan(
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
                    evidence_sha256="3" * 64,
                ),
            ),
        ),
        "base_checkpoint_sha256": "2" * 64,
        "base_checkpoint_evidence_sha256": "3" * 64,
    }


def test_stage_one_has_exactly_twelve_cells_before_fold_seed_expansion():
    cells = stage_one_conditions(seeds=(101,), folds=range(5))
    assert len(cells) == 60
    assert {(row.method, row.selector, row.shot_count) for row in cells} == {
        (method, selector, shot)
        for method, selector in (("m0", "div"), ("m1", "div"), ("m2", "div"), ("m2", "rnd"))
        for shot in (1, 3, 5)
    }


def test_conditions_have_deterministic_ids():
    first = stage_one_conditions(seeds=(101,), folds=(0,))[0]
    second = stage_one_conditions(seeds=(101,), folds=(0,))[0]
    assert first.condition_id == second.condition_id
    assert first.condition_id.startswith("rpc-")


def test_stage_one_rejects_an_unregistered_method_selector_shot_cell():
    with pytest.raises(ValueError, match="unsupported Stage-1 condition"):
        replace(_condition(), shot_count=10)


def test_ascending_extended_shots_require_explicit_opt_in():
    basic = ascending_conditions((("m0", "div"),), seeds=(101,), folds=(0,))
    extended = ascending_conditions(
        (("m0", "div"),), seeds=(101,), folds=(0,), extended=True
    )
    assert {item.shot_count for item in basic} == {1, 3, 5, 10, 20}
    assert {item.shot_count for item in extended} == {1, 3, 5, 10, 20, 40, 80, 150}


def test_confirmation_and_locked_conditions_bind_the_150_shot_reference(tmp_path: Path):
    confirmation = confirmation_conditions(
        ("m0", "div"),
        shot_counts=(3, 5, 10, 150),
        seeds=(101,),
        folds=(0,),
    )
    selected, paths = _stage_four_selection_artifacts(tmp_path)
    locked = locked_conditions(
        selected, confirmation_score_receipt_paths=paths
    )

    assert {condition.stage for condition in confirmation} == {"confirmation"}
    assert {condition.shot_count for condition in confirmation} == {3, 5, 10, 150}
    assert {condition.stage for condition in locked} == {"locked"}
    assert {condition.shot_count for condition in locked} == {5, 150}


def _stage_four_selection() -> StageFourSelection:
    conditions = confirmation_conditions(
        ("m0", "div"),
        shot_counts=(3, 5, 10, 150),
        seeds=(101,),
        folds=(0,),
    )
    return StageFourSelection(
        confirmation_receipts=tuple(
            StageFourConfirmationReceipt(
                condition=condition,
                score_receipt_sha256=f"{index + 1:x}" * 64,
                provisional_pass=condition.shot_count != 3,
            )
            for index, condition in enumerate(conditions)
        )
    )


def _stage_four_selection_artifacts(
    tmp_path: Path,
) -> tuple[StageFourSelection, tuple[Path, ...]]:
    """Copy genuine scorer aggregates; never hand-author schedulable Stage-4 JSON."""
    specification = importlib.util.spec_from_file_location(
        "rpc_scoring_plan_stage_four_fixture",
        Path(__file__).with_name("test_rpc_scoring_plan.py"),
    )
    assert specification is not None and specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    sys.modules[specification.name] = module
    specification.loader.exec_module(module)
    selection, source_paths = module._locked_selection_artifacts(0, 101)
    paths: list[Path] = []
    claims: list[StageFourConfirmationReceipt] = []
    for index, (claim, source_path) in enumerate(
        zip(selection.confirmation_receipts, source_paths, strict=True)
    ):
        path = tmp_path / f"confirmation-{index}.json"
        content = source_path.read_bytes()
        path.write_bytes(content)
        paths.append(path)
        claims.append(
            StageFourConfirmationReceipt(
                condition=claim.condition,
                score_receipt_sha256=hashlib.sha256(content).hexdigest(),
                provisional_pass=claim.provisional_pass,
            )
        )
    return StageFourSelection(tuple(claims)), tuple(paths)


def _branch_summaries() -> dict[str, object]:
    return {
        branch: {
            "sample_count": 2,
            "novel_macro_recall": 1.0,
            "base_macro_recall": 1.0,
            "per_category_recall": {"1": 1.0, "2": 1.0},
        }
        for branch in ("repvit_global", "dinov3_global", "dinov3_local")
    }


def _full_system_summary() -> dict[str, object]:
    return {
        "sample_count": 2,
        "wrong_registered_sku_rate": 0.0,
        "novel_wrong_registered_sku_rate": 0.0,
        "base_wrong_registered_sku_rate": 0.0,
        "unknown_rate": 0.0,
        "registered_coverage": 1.0,
        "novel_macro_final_correct_recall": 1.0,
        "base_macro_final_correct_recall": 1.0,
        "per_category_final_correct_recall": {"1": 1.0, "2": 1.0},
        "novel_loss_over_10pp_fraction": 0.0,
        "by_difficulty": {
            "E": {
                "sample_count": 2,
                "unknown_rate": 0.0,
                "registered_coverage": 1.0,
                "wrong_registered_sku_rate": 0.0,
                "novel_macro_final_correct_recall": 1.0,
                "base_macro_final_correct_recall": 1.0,
            }
        },
    }


def _confirmation_plan(condition: ExperimentCondition) -> ScoringPlan:
    return ScoringPlan(
        bootstrap_seed=7,
        bootstrap_replicates=10,
        folds=(condition.fold,),
        support_seeds=(condition.support_seed,),
        expected_condition_ids=(condition.condition_id,),
        cohort_id="rpc-test",
        registered_category_ids=(1, 2),
        fold_base_artifacts=(
            FoldBaseArtifact(
                fold=condition.fold,
                checkpoint_sha256="2" * 64,
                evidence_sha256="3" * 64,
            ),
        ),
    )


def test_locked_scheduler_requires_four_hash_bound_stage_four_receipts(tmp_path: Path):
    selection, paths = _stage_four_selection_artifacts(tmp_path)
    assert selection.provisional_minimum_shot_count == 5
    assert {(cell.method, cell.selector) for cell in locked_conditions(
        selection, confirmation_score_receipt_paths=paths
    )} == {
        ("m0", "div")
    }

    with pytest.raises(TypeError):
        locked_conditions(("m0", "div"), candidate_shot_count=5, seeds=(101,), folds=(0,))  # type: ignore[call-arg]


def test_locked_scheduler_rejects_unresolved_stage_four_receipt_hashes(
    tmp_path: Path,
):
    """Four plausible hex strings cannot authorize a Stage-5 schedule."""
    selection = _stage_four_selection()

    with pytest.raises(ValueError, match="Stage-4 confirmation score receipt"):
        locked_conditions(
            selection,
            confirmation_score_receipt_paths=tuple(
                tmp_path / f"confirmation-{index}.json" for index in range(4)
            ),
        )


def test_locked_scheduler_rejects_tampered_stage_four_confirmation_receipt(
    tmp_path: Path,
):
    """Even a re-hashed file is rejected when its decision contradicts the claim."""
    selection, paths = _stage_four_selection_artifacts(tmp_path)
    value = json.loads(paths[1].read_text(encoding="utf-8"))
    value["provisional_pass"] = False
    content = canonical_json_bytes(value)
    paths[1].write_bytes(content)
    tampered = StageFourSelection(
        tuple(
            replace(
                claim,
                score_receipt_sha256=hashlib.sha256(content).hexdigest(),
            )
            if index == 1
            else claim
            for index, claim in enumerate(selection.confirmation_receipts)
        )
    )

    with pytest.raises(ValueError, match="invalid Stage-4 confirmation score receipt decision"):
        locked_conditions(
            tampered, confirmation_score_receipt_paths=paths
        )


def test_locked_scheduler_rejects_mismatched_stage_four_cohort(
    tmp_path: Path,
):
    selection, paths = _stage_four_selection_artifacts(tmp_path)
    value = json.loads(paths[0].read_text(encoding="utf-8"))
    value["cohort"] = {"base_category_ids": [1], "novel_category_ids": [2]}
    content = canonical_json_bytes(value)
    paths[0].write_bytes(content)
    mismatched = StageFourSelection(
        tuple(
            replace(
                claim,
                score_receipt_sha256=hashlib.sha256(content).hexdigest(),
            )
            if index == 0
            else claim
            for index, claim in enumerate(selection.confirmation_receipts)
        )
    )

    with pytest.raises(ValueError, match="not derivable from upstream artifacts"):
        locked_conditions(
            mismatched, confirmation_score_receipt_paths=paths
        )


def test_locked_scheduler_rejects_a_minimal_forged_stage_four_receipt(
    tmp_path: Path,
):
    """A hand-authored decision subset is not a Stage-4 aggregate artifact."""
    selection, paths = _stage_four_selection_artifacts(tmp_path)
    forged = json.loads(paths[0].read_text(encoding="utf-8"))
    del forged["raw_evidence"]
    content = canonical_json_bytes(forged)
    paths[0].write_bytes(content)
    selection = StageFourSelection(
        tuple(
            replace(claim, score_receipt_sha256=hashlib.sha256(content).hexdigest())
            if index == 0
            else claim
            for index, claim in enumerate(selection.confirmation_receipts)
        )
    )

    with pytest.raises(ValueError, match="strict aggregate schema"):
        locked_conditions(selection, confirmation_score_receipt_paths=paths)


def test_locked_experiment_receipt_rejects_foreign_stage_four_cohort_binding(
    tmp_path: Path,
):
    """A valid Stage-4 quartet cannot authorize a different locked cohort."""
    selection, paths = _stage_four_selection_artifacts(tmp_path)
    condition = next(
        item
        for item in locked_conditions(selection, confirmation_score_receipt_paths=paths)
        if item.shot_count == 5
    )
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
                evidence_sha256="3" * 64,
            ),
        ),
    )

    with pytest.raises(ValueError, match="Stage-4.*cohort"):
        ExperimentReceipt.completed(
            condition,
            condition_manifest_sha256=_HASH,
            model_sha256="b" * 64,
            support_sha256="c" * 64,
            calibration_sha256="d" * 64,
            policy_sha256="e" * 64,
            preprocessing_sha256="f" * 64,
            code_sha256="0" * 64,
            cohort_manifest_sha256="9" * 64,
            novel_category_ids=(1,),
            base_category_ids=(2,),
            scoring_plan=plan,
            base_checkpoint_sha256="2" * 64,
            base_checkpoint_evidence_sha256="3" * 64,
            environment_lock_digest="sha256:environment",
            output_uri="file:///external/run",
            stage_four_selection=selection,
            stage_four_confirmation_score_receipt_paths=tuple(
                str(path) for path in paths
            ),
        )


@pytest.mark.parametrize("last_failure, first_pass, expected", [(3, 5, (4,)), (5, 10, (6, 8)), (10, 20, (12, 15, 18))])
def test_refinement_shots_are_preregistered(last_failure: int, first_pass: int, expected: tuple[int, ...]):
    assert refinement_shots(last_failure, first_pass) == expected


def test_refinement_shots_reject_unregistered_interval():
    with pytest.raises(ValueError, match="preregistered"):
        refinement_shots(1, 3)


@pytest.mark.parametrize("methods", [(("m1", "rnd"),), (("m0", "div"), ("m0", "div")), (("m0", "div"), ("m1", "div"), ("m2", "div"))])
def test_ascending_rejects_unsupported_or_non_preregistered_methods(methods: tuple[tuple[str, str], ...]):
    with pytest.raises(ValueError):
        ascending_conditions(methods, seeds=(101,), folds=(0,))


def test_receipt_rejects_missing_policy_hash(tmp_path: Path):
    with pytest.raises(ValueError, match="policy_sha256"):
        ExperimentReceipt.completed(_condition(), policy_sha256="", output_uri="file:///external/run", **_COHORT)


def test_completed_receipt_binds_nonempty_disjoint_rpc_cohorts():
    receipt = ExperimentReceipt.completed(
        _condition(),
        condition_manifest_sha256=_HASH,
        model_sha256="b" * 64,
        support_sha256="c" * 64,
        calibration_sha256="d" * 64,
        policy_sha256="e" * 64,
        preprocessing_sha256="f" * 64,
        code_sha256="0" * 64,
        **_COHORT,
        **_scoring_bindings(),
        environment_lock_digest="sha256:environment",
        output_uri="file:///external/run",
    )

    assert receipt.to_dict()["cohort"]["novel_category_ids"] == [1]


def test_receipt_rejects_mutable_or_overlapping_cohorts():
    values = {
        "condition_manifest_sha256": _HASH,
        "model_sha256": "b" * 64,
        "support_sha256": "c" * 64,
        "calibration_sha256": "d" * 64,
        "policy_sha256": "e" * 64,
        "preprocessing_sha256": "f" * 64,
        "code_sha256": "0" * 64,
        "cohort_manifest_sha256": "1" * 64,
        "novel_category_ids": [1],
        "base_category_ids": (2,),
        "environment_lock_digest": "sha256:environment",
        "output_uri": "file:///external/run",
        **_scoring_bindings(),
    }
    with pytest.raises(ValueError, match="tuple"):
        ExperimentReceipt.completed(_condition(), **values)


def test_unavailable_receipt_is_never_reported_as_passed():
    receipt = ExperimentReceipt.unavailable(
        _condition(),
        reason="runtime image unavailable",
        condition_manifest_sha256=_HASH,
        model_sha256="b" * 64,
        support_sha256="c" * 64,
        calibration_sha256="d" * 64,
        policy_sha256="e" * 64,
        preprocessing_sha256="f" * 64,
        code_sha256="0" * 64,
        **_COHORT,
        **_scoring_bindings(),
        environment_lock_digest="sha256:environment",
        output_uri="file:///external/run",
    )
    assert receipt.status == "unavailable"
    assert receipt.to_dict()["status"] == "unavailable"


def test_receipt_serializes_canonical_json_and_refuses_replacement(tmp_path: Path):
    receipt = ExperimentReceipt.completed(
        _condition(),
        condition_manifest_sha256=_HASH,
        model_sha256="b" * 64,
        support_sha256="c" * 64,
        calibration_sha256="d" * 64,
        policy_sha256="e" * 64,
        preprocessing_sha256="f" * 64,
        code_sha256="0" * 64,
        **_COHORT,
        **_scoring_bindings(),
        environment_lock_digest="sha256:environment",
        output_uri="file:///external/run",
    )
    output = tmp_path / "receipt.json"
    write_experiment_receipt(output, receipt)
    content = output.read_bytes()
    assert content == json.dumps(receipt.to_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    with pytest.raises(FileExistsError):
        write_experiment_receipt(output, receipt)
