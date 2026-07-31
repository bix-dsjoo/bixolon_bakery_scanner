"""Final-decision controls for immutable RPC few-shot scoring plans."""

from __future__ import annotations

from dataclasses import replace
import hashlib
import importlib.util
import sys
from pathlib import Path

import pytest
import yaml

from bakery_scanner.experiments.rpc_manifest import canonical_json_bytes
from bakery_scanner.experiments.rpc_protocol import (
    ExperimentReceipt,
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


def _plan(condition_ids: tuple[str, ...], *, folds=(0,), seeds=(101,)) -> ScoringPlan:
    return ScoringPlan(
        bootstrap_seed=20260731,
        bootstrap_replicates=1000,
        folds=folds,
        support_seeds=seeds,
        expected_condition_ids=condition_ids,
        cohort_id="rpc-2019-200-category-five-fold-v1",
        registered_category_ids=(1, 2),
    )


def _receipt(plan: ScoringPlan) -> ExperimentReceipt:
    condition = _cell_conditions()[0]
    return ExperimentReceipt.completed(
        condition,
        **HASHES,
        cohort_manifest_sha256="1" * 64,
        novel_category_ids=(1,),
        base_category_ids=(2,),
        scoring_plan=plan,
        base_checkpoint_sha256="2" * 64,
        base_checkpoint_evidence_sha256="3" * 64,
        environment_lock_digest="sha256:environment",
        output_uri="file:///external/run",
    )


def _write_canonical(path: Path, value: object) -> None:
    path.write_bytes(canonical_json_bytes(value))


def _non_final_score(
    candidate,
    reference,
    candidate_plan: ScoringPlan,
    reference_plan: ScoringPlan,
) -> dict[str, object]:
    return {
        "schema_version": 2,
        "kind": "rpc-fewshot-score-receipt",
        "status": "completed",
        "decision_status": "non_final",
        "candidate_condition": candidate.to_dict(),
        "reference_condition": reference.to_dict(),
        "candidate_scoring_plan": candidate_plan.to_dict(),
        "reference_scoring_plan": reference_plan.to_dict(),
        "minimum_rule_inputs": {
            "registered_coverage": 1.0,
            "novel_macro_recall_lower_delta": -0.01,
            "wrong_registered_sku_rate_upper_delta": 0.0,
            "novel_loss_over_10pp_fraction": 0.0,
            "candidate_base_macro_final_correct_recall": 0.99,
            "fold_base_checkpoint_macro_final_correct_recall": 1.0,
        },
    }


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
    assert payload["fold_base_checkpoint"] == {
        "checkpoint_sha256": "2" * 64,
        "evidence_sha256": "3" * 64,
        "fold": 0,
    }

    with pytest.raises(ValueError, match="expected condition"):
        _receipt(replace(plan, expected_condition_ids=("rpc-other",)))
    with pytest.raises(ValueError, match="tuple"):
        ScoringPlan(
            bootstrap_seed=1,
            bootstrap_replicates=10,
            folds=[0],  # type: ignore[arg-type]
            support_seeds=(101,),
            expected_condition_ids=(condition.condition_id,),
            cohort_id="rpc",
            registered_category_ids=(1, 2),
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
        )


def test_yaml_scoring_plan_declares_bootstrap_matrix_ids_and_cohort():
    payload = yaml.safe_load(
        (ROOT / "experiments/20260731-rpc-fewshot/experiment.yaml").read_text(encoding="utf-8")
    )
    plan = ScoringPlan.from_dict(payload["scoring_plan"])
    expected = _cell_conditions(
        seeds=tuple(payload["support_seeds"]),
        folds=tuple(payload["folds"]),
    )

    assert payload["schema_version"] == 1
    assert plan.bootstrap_seed == 20260731
    assert plan.bootstrap_replicates == 10000
    assert set(plan.expected_condition_ids) == {condition.condition_id for condition in expected}
    assert plan.registered_category_ids == tuple(range(1, 201))


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
        "cohort_manifest_sha256": "1" * 64,
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


def test_incomplete_fold_seed_aggregate_cannot_emit_final_pass(tmp_path: Path):
    module = _score_module()
    candidates = _cell_conditions(seeds=(101, 102), folds=(0,))
    references = tuple(
        condition
        for condition in stage_one_conditions(seeds=(101, 102), folds=(0,))
        if (condition.method, condition.selector, condition.shot_count) == ("m1", "div", 1)
    )
    candidate_plan = _plan(tuple(row.condition_id for row in candidates), seeds=(101, 102))
    reference_plan = _plan(tuple(row.condition_id for row in references), seeds=(101, 102))
    receipt_path = tmp_path / "one.json"
    output = tmp_path / "aggregate.json"
    _write_canonical(
        receipt_path,
        _non_final_score(candidates[0], references[0], candidate_plan, reference_plan),
    )

    with pytest.raises(ValueError, match="complete declared fold/seed"):
        module.aggregate_score_receipts((receipt_path,), output)
    assert not output.exists()


def test_complete_fold_seed_aggregate_is_the_only_final_boolean(tmp_path: Path):
    module = _score_module()
    candidates = _cell_conditions(seeds=(101, 102), folds=(0,))
    references = tuple(
        condition
        for condition in stage_one_conditions(seeds=(101, 102), folds=(0,))
        if (condition.method, condition.selector, condition.shot_count) == ("m1", "div", 1)
    )
    candidate_plan = _plan(tuple(row.condition_id for row in candidates), seeds=(101, 102))
    reference_plan = _plan(tuple(row.condition_id for row in references), seeds=(101, 102))
    paths = []
    for index, (candidate, reference) in enumerate(zip(candidates, references, strict=True)):
        path = tmp_path / f"score-{index}.json"
        _write_canonical(path, _non_final_score(candidate, reference, candidate_plan, reference_plan))
        paths.append(path)
    output = tmp_path / "aggregate.json"

    module.aggregate_score_receipts(tuple(paths), output)

    aggregate = module.load_canonical_json(output)
    assert aggregate["decision_scope"] == "complete_declared_fold_seed_aggregate"
    assert aggregate["final_pass"] is True
    assert aggregate["candidate_scoring_plan"]["bootstrap_seed"] == 20260731
    assert aggregate["candidate_scoring_plan"]["bootstrap_replicates"] == 1000
    assert {item["sha256"] for item in aggregate["score_receipts"]} == {
        hashlib.sha256(path.read_bytes()).hexdigest() for path in paths
    }
    for path in paths:
        single = module.load_canonical_json(path)
        assert single["decision_status"] == "non_final"
        assert "final_pass" not in single


def test_aggregate_rejects_candidate_reference_cross_seed_pairing(tmp_path: Path):
    module = _score_module()
    candidates = _cell_conditions(seeds=(101, 102), folds=(0,))
    references = tuple(
        condition
        for condition in stage_one_conditions(seeds=(101, 102), folds=(0,))
        if (condition.method, condition.selector, condition.shot_count) == ("m1", "div", 1)
    )
    candidate_plan = _plan(tuple(row.condition_id for row in candidates), seeds=(101, 102))
    reference_plan = _plan(tuple(row.condition_id for row in references), seeds=(101, 102))
    paths = []
    for index, (candidate, reference) in enumerate(
        zip(candidates, reversed(references), strict=True)
    ):
        path = tmp_path / f"cross-seed-{index}.json"
        _write_canonical(path, _non_final_score(candidate, reference, candidate_plan, reference_plan))
        paths.append(path)

    with pytest.raises(ValueError, match="paired fold/seed"):
        module.aggregate_score_receipts(tuple(paths), tmp_path / "aggregate.json")
