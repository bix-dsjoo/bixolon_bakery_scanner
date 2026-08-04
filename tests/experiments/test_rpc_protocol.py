"""Contract tests for the preregistered RPC few-shot protocol."""

from __future__ import annotations

import json
import hashlib
import importlib.util
import inspect
import sys
import tempfile
from dataclasses import replace
from pathlib import Path

import pytest
import yaml

from bakery_scanner.experiments.rpc_protocol import (
    ExperimentCondition,
    ExperimentReceipt,
    FoldBaseArtifact,
    ScoringPlan,
    StageFourConfirmationReceipt,
    StageFourSelection,
    ascending_conditions,
    confirmation_conditions,
    all_available_diagnostic_conditions,
    StageOneMethodEvidence,
    select_stage_one_methods,
    StageOneSelectionReceipt,
    load_stage_one_selection_receipt,
    locked_conditions,
    refinement_shots,
    stage_one_conditions,
    write_experiment_receipt,
    write_stage_one_selection_receipt,
    _condition_id,
)
from bakery_scanner.experiments.rpc_manifest import canonical_json_bytes
from bakery_scanner.experiments.rpc_metrics import ResearchEvidenceRow
from bakery_scanner.experiments import rpc_scoring
from bakery_scanner.experiments import rpc_protocol as _rpc_protocol
from bakery_scanner.experiments.rpc_support import (
    SupportCandidate,
    materialize_support_bank,
    parse_train_capture_stratum,
    write_support_bank,
)


_HASH = "a" * 64
_COHORT = {
    "cohort_manifest_sha256": "1" * 64,
    "novel_category_ids": (1,),
    "base_category_ids": (2,),
}
_TEST_TRUSTED_ROOT = Path("C:/rpc-test-trusted-root")
_public_locked_conditions = locked_conditions
_STAGE_ONE_CACHE_DIRECTORY = tempfile.TemporaryDirectory(
    prefix="rpc-stage-one-protocol-cache-"
)
_STAGE_ONE_ARTIFACT_CACHE: dict[tuple[object, ...], tuple[Path, tuple[Path, ...]]] = {}


def locked_conditions(
    selection: StageFourSelection,
    *,
    confirmation_score_receipt_paths,
    trusted_index,
):
    """Test adapter for the scorer's private raw-index seam."""
    rpc_scoring._load_verified_default_rpc_index = lambda _root: trusted_index
    return _public_locked_conditions(
        selection,
        confirmation_score_receipt_paths=confirmation_score_receipt_paths,
        trusted_source_root=_TEST_TRUSTED_ROOT,
    )


def _condition() -> ExperimentCondition:
    return stage_one_conditions(seeds=(101, 102, 103, 104, 105), folds=(0,))[0]


def test_public_scorer_cannot_accept_a_prevalidated_ground_truth_override():
    """Only the scorer's trusted raw-root loader may authenticate truth."""
    assert "_validated_ground_truth" not in inspect.signature(rpc_scoring.score).parameters


def _stage_one_score_artifacts(
    tmp_path: Path,
    *,
    declared_seeds: tuple[int, ...] = (101, 102, 103, 104, 105),
    write_selection: bool = True,
    clear_winner: bool = False,
    method_pairs: tuple[tuple[str, str], ...] | None = None,
    reuse: bool = True,
) -> tuple[Path, tuple[Path, ...]]:
    """Build Stage-1 receipts through the real scorer, never JSON shortcuts."""
    cache_key = (declared_seeds, write_selection, clear_winner, method_pairs)
    if reuse:
        cached = _STAGE_ONE_ARTIFACT_CACHE.get(cache_key)
        if cached is not None:
            fixture = _scoring_fixture()
            fixture._install_trusted_index_for_test(fixture._trusted_index())
            return cached
        cache_path = Path(_STAGE_ONE_CACHE_DIRECTORY.name) / str(
            len(_STAGE_ONE_ARTIFACT_CACHE)
        )
        cached = _stage_one_score_artifacts(
            cache_path,
            declared_seeds=declared_seeds,
            write_selection=write_selection,
            clear_winner=clear_winner,
            method_pairs=method_pairs,
            reuse=False,
        )
        _STAGE_ONE_ARTIFACT_CACHE[cache_key] = cached
        return cached
    tmp_path.mkdir(parents=True, exist_ok=True)
    fixture = _scoring_fixture()
    fixture._install_trusted_index_for_test(fixture._trusted_index())
    ground_truth_path = tmp_path / "development-ground-truth.json"
    fixture._write_development_ground_truth(ground_truth_path)
    base_evidence_path = tmp_path / "base-evidence.json"
    base_sha = fixture._write_fold_base_evidence(
        base_evidence_path,
        fold=0,
        checkpoint_sha256="2" * 64,
        cohort_manifest_sha256=fixture.DEVELOPMENT_GROUND_TRUTH_SHA256,
    )
    cells = tuple(
        cell
        for cell in stage_one_conditions(seeds=declared_seeds, folds=(0,))
        if method_pairs is None or (cell.method, cell.selector) in method_pairs
    )
    plan = ScoringPlan(
        bootstrap_seed=7,
        bootstrap_replicates=10,
        folds=(0,),
        support_seeds=declared_seeds,
        expected_condition_ids=tuple(item.condition_id for item in cells),
        cohort_id="rpc-test",
        registered_category_ids=(1, 2),
        fold_base_artifacts=(FoldBaseArtifact(0, "2" * 64, base_sha),),
    )
    banks = {
        selector: _stage_one_support_bank(tmp_path, selector, declared_seeds)
        for selector in ("div", "rnd")
    }
    paths: list[Path] = []
    for index, condition in enumerate(cells):
        bank_path, bank_sha = banks[condition.selector]
        receipt = ExperimentReceipt.completed(
            condition,
            condition_manifest_sha256="a" * 64,
            model_sha256="b" * 64,
            support_sha256=bank_sha,
            calibration_sha256="d" * 64,
            policy_sha256="e" * 64,
            preprocessing_sha256="f" * 64,
            code_sha256="0" * 64,
            cohort_manifest_sha256=fixture.DEVELOPMENT_GROUND_TRUTH_SHA256,
            novel_category_ids=(1,),
            base_category_ids=(2,),
            scoring_plan=plan,
            base_checkpoint_sha256="2" * 64,
            base_checkpoint_evidence_sha256=base_sha,
            environment_lock_digest="sha256:environment",
            output_uri=f"file:///external/stage1/{index}",
        )
        condition_path = tmp_path / f"stage1-condition-{index}.json"
        condition_path.write_bytes(canonical_json_bytes(receipt.to_dict()))
        method_score = (
            1.0
            if clear_winner and (condition.method, condition.selector) == ("m0", "div")
            else 0.0
            if clear_winner or condition.method == "m1"
            else 1.0
        )
        evidence = (
            ResearchEvidenceRow(
                sample_id="novel", object_id=1, condition_id=condition.condition_id,
                fold=0, difficulty="E", burst_id="burst", truth_category_id=1,
                predicted_category_id=1, score_category_ids=(1, 2),
                repvit_global_scores=(method_score, 1.0 - method_score),
                dinov3_global_scores=(method_score, 1.0 - method_score),
                dinov3_local_scores=(method_score, 1.0 - method_score),
                conditional_dino_executed=True,
                condition_manifest_sha256="a" * 64, model_sha256="b" * 64,
                support_sha256=bank_sha, calibration_sha256="d" * 64,
                policy_sha256="e" * 64, preprocessing_sha256="f" * 64,
                code_sha256="0" * 64,
            ),
            ResearchEvidenceRow(
                sample_id="base", object_id=2, condition_id=condition.condition_id,
                fold=0, difficulty="E", burst_id="burst", truth_category_id=2,
                predicted_category_id=2, score_category_ids=(1, 2),
                repvit_global_scores=(0.0, 1.0), dinov3_global_scores=(0.0, 1.0),
                dinov3_local_scores=(0.0, 1.0), conditional_dino_executed=False,
                condition_manifest_sha256="a" * 64, model_sha256="b" * 64,
                support_sha256=bank_sha, calibration_sha256="d" * 64,
                policy_sha256="e" * 64, preprocessing_sha256="f" * 64,
                code_sha256="0" * 64,
            ),
        )
        evidence_path = tmp_path / f"stage1-evidence-{index}.jsonl"
        evidence_path.write_bytes(b"".join(canonical_json_bytes(row.to_dict()) + b"\n" for row in evidence))
        path = tmp_path / f"stage1-score-{index}.json"
        rpc_scoring.score(
            evidence_path, evidence_path, condition_path, condition_path,
            ground_truth_path, base_evidence_path, path,
            trusted_source_root=_TEST_TRUSTED_ROOT, support_bank_path=bank_path,
        )
        _cache_real_score_receipt_for_test(path)
        paths.append(path)
    receipt_path = tmp_path / "stage1-selection.json"
    if write_selection:
        write_stage_one_selection_receipt(
            receipt_path, tuple(paths), trusted_source_root=_TEST_TRUSTED_ROOT
        )
    return receipt_path, tuple(paths)


def _resolved_ten_seed_stage_one_artifacts(
    tmp_path: Path, *, clear_winner: bool = False
) -> tuple[Path, tuple[Path, ...], Path, tuple[Path, ...]]:
    """Build the required five-seed parent and hash-bound ten-seed child."""
    seeds = (101, 102, 103, 104, 105)
    initial_path, initial_scores = _stage_one_score_artifacts(
        tmp_path / "five", declared_seeds=seeds, clear_winner=clear_winner
    )
    initial = load_stage_one_selection_receipt(
        initial_path,
        score_receipt_paths=initial_scores,
        trusted_source_root=_TEST_TRUSTED_ROOT,
    )
    ten_path, ten_scores = _stage_one_score_artifacts(
        tmp_path / "ten",
        declared_seeds=(*seeds, 106, 107, 108, 109, 110),
        method_pairs=initial.decision.expand_to_ten_seeds,
        write_selection=False,
        clear_winner=clear_winner,
    )
    if not ten_path.exists():
        write_stage_one_selection_receipt(
            ten_path,
            ten_scores,
            initial_selection_receipt_path=initial_path,
            initial_score_receipt_paths=initial_scores,
            trusted_source_root=_TEST_TRUSTED_ROOT,
        )
    return ten_path, ten_scores, initial_path, initial_scores


def _cache_real_score_receipt_for_test(path: Path) -> None:
    """Test-only acceleration for scores just emitted by the real scorer.

    Production validation still checks every artifact's current bytes and
    re-authenticates the raw source before this cache can be used.  Test
    fixtures avoid only a redundant byte-for-byte rebuild of their own fresh
    scorer output.
    """
    receipt = rpc_scoring.load_canonical_json(path)
    artifacts = receipt["derivation_artifacts"]
    assert isinstance(artifacts, dict)
    digests = tuple(
        sorted(
            (
                name,
                value["content_sha256"] if name == "support_bank" else value["sha256"],
            )
            for name, value in artifacts.items()
        )
    )
    rpc_scoring._VERIFIED_SCORE_DERIVATIONS.add(
        (
            str(_TEST_TRUSTED_ROOT.resolve()),
            hashlib.sha256(canonical_json_bytes(dict(receipt))).hexdigest(),
            digests,
        )
    )


def _scoring_fixture():
    specification = importlib.util.spec_from_file_location(
        "rpc_scoring_stage1_fixture",
        Path(__file__).with_name("test_rpc_scoring_plan.py"),
    )
    assert specification is not None and specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    sys.modules[specification.name] = module
    specification.loader.exec_module(module)
    return module


def _stage_one_support_bank(
    tmp_path: Path, selector: str, seeds: tuple[int, ...]
) -> tuple[Path, str]:
    bank = materialize_support_bank(
        {
            category: tuple(
                SupportCandidate(
                    category, f"{selector}-{category}-{index}",
                    f"{selector}{category}{index}_camera{(index % 4) + 1}-top.jpg",
                    hashlib.sha256(f"{selector}-{category}-{index}".encode()).hexdigest(),
                    1, parse_train_capture_stratum(
                        f"{selector}{category}{index}_camera{(index % 4) + 1}-top.jpg", category
                    ), (float(index + 1), float(category)),
                )
                for index in range(160)
            )
            for category in (1, 2)
        }, method=selector, seeds=seeds,
    )
    path = tmp_path / f"stage1-support-{selector}.json"
    write_support_bank(path, bank)
    return path, bank.sha256


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


def test_stage_one_rejects_a_non_screen_seed_count():
    with pytest.raises(ValueError, match="five or ten support seeds"):
        stage_one_conditions(seeds=(101,), folds=range(5))


def test_stage_one_has_exactly_twelve_cells_per_fold_seed():
    cells = stage_one_conditions(seeds=(101, 102, 103, 104, 105), folds=range(5))
    assert len(cells) == 300
    assert {(row.method, row.selector, row.shot_count) for row in cells} == {
        (method, selector, shot)
        for method, selector in (("m0", "div"), ("m1", "div"), ("m2", "div"), ("m2", "rnd"))
        for shot in (1, 3, 5)
    }


def test_committed_stage_one_plan_binds_all_300_pair_shot_fold_seed_cells():
    plan = yaml.safe_load(
        (Path(__file__).parents[2] / "experiments/20260731-rpc-fewshot/experiment.yaml").read_text(encoding="utf-8")
    )
    declared = plan["scoring_plan"]["expected_condition_ids"]

    assert len(declared) == 300
    assert set(declared) == {
        item.condition_id
        for item in stage_one_conditions(seeds=(101, 102, 103, 104, 105), folds=range(5))
    }


def test_conditions_have_deterministic_ids():
    first = stage_one_conditions(seeds=(101, 102, 103, 104, 105), folds=(0,))[0]
    second = stage_one_conditions(seeds=(101, 102, 103, 104, 105), folds=(0,))[0]
    assert first.condition_id == second.condition_id
    assert first.condition_id.startswith("rpc-")


def test_stage_one_rejects_an_unregistered_method_selector_shot_cell():
    with pytest.raises(ValueError, match="unsupported Stage-1 condition"):
        replace(_condition(), shot_count=10)


def test_ascending_extended_shots_require_explicit_opt_in(tmp_path: Path):
    selection_path, score_paths, initial_path, initial_scores = (
        _resolved_ten_seed_stage_one_artifacts(tmp_path, clear_winner=True)
    )
    retained = load_stage_one_selection_receipt(
        selection_path, score_receipt_paths=score_paths,
        initial_selection_receipt_path=initial_path,
        initial_score_receipt_paths=initial_scores,
        trusted_source_root=_TEST_TRUSTED_ROOT,
    ).decision.retained_methods
    basic = ascending_conditions(
        retained,
        seeds=(101,),
        folds=(0,),
        stage_one_selection_receipt_path=selection_path,
        stage_one_score_receipt_paths=score_paths,
        initial_stage_one_selection_receipt_path=initial_path,
        initial_stage_one_score_receipt_paths=initial_scores,
        trusted_source_root=_TEST_TRUSTED_ROOT,
    )
    extended = ascending_conditions(
        retained,
        seeds=(101,),
        folds=(0,),
        extended=True,
        stage_one_selection_receipt_path=selection_path,
        stage_one_score_receipt_paths=score_paths,
        initial_stage_one_selection_receipt_path=initial_path,
        initial_stage_one_score_receipt_paths=initial_scores,
        trusted_source_root=_TEST_TRUSTED_ROOT,
    )
    assert {item.shot_count for item in basic} == {1, 3, 5, 10, 20}
    assert {item.shot_count for item in extended} == {1, 3, 5, 10, 20, 40, 80, 150}


def test_ascending_rejects_an_unresolved_five_seed_expansion(tmp_path: Path):
    """A five-seed screen cannot be mistaken for the ten-seed final choice."""
    selection_path, score_paths = _stage_one_score_artifacts(
        tmp_path, declared_seeds=(101, 102, 103, 104, 105)
    )
    selection = load_stage_one_selection_receipt(
        selection_path, score_receipt_paths=score_paths,
        trusted_source_root=_TEST_TRUSTED_ROOT,
    )
    assert selection.decision.expand_to_ten_seeds

    with pytest.raises(ValueError, match="ten-seed re-selection"):
        ascending_conditions(
            selection.decision.retained_methods,
            seeds=(101,),
            folds=(0,),
            stage_one_selection_receipt_path=selection_path,
            stage_one_score_receipt_paths=score_paths,
            trusted_source_root=_TEST_TRUSTED_ROOT,
        )


def test_clear_five_seed_winner_requires_ten_seed_reselection(tmp_path: Path):
    """Even a unique survivor is within 1pp of itself and must expand."""
    selection_path, score_paths = _stage_one_score_artifacts(
        tmp_path, declared_seeds=(101, 102, 103, 104, 105), clear_winner=True
    )
    selection = load_stage_one_selection_receipt(
        selection_path, score_receipt_paths=score_paths,
        trusted_source_root=_TEST_TRUSTED_ROOT,
    )

    assert selection.decision.expand_to_ten_seeds == (("m0", "div"),)
    with pytest.raises(ValueError, match="ten-seed re-selection"):
        ascending_conditions(
            selection.decision.retained_methods,
            seeds=(101,),
            folds=(0,),
            stage_one_selection_receipt_path=selection_path,
            stage_one_score_receipt_paths=score_paths,
            trusted_source_root=_TEST_TRUSTED_ROOT,
        )


def test_hash_bound_ten_seed_reselection_allows_only_initial_contenders(
    tmp_path: Path,
):
    initial_path, initial_scores = _stage_one_score_artifacts(
        tmp_path / "five", declared_seeds=(101, 102, 103, 104, 105)
    )
    initial = StageOneSelectionReceipt.from_dict(
        json.loads(initial_path.read_text(encoding="utf-8"))
    )
    assert initial.decision.expand_to_ten_seeds
    ten_path, ten_scores = _stage_one_score_artifacts(
        tmp_path / "ten",
        declared_seeds=(101, 102, 103, 104, 105, 106, 107, 108, 109, 110),
        method_pairs=initial.decision.expand_to_ten_seeds,
        write_selection=False,
    )
    write_stage_one_selection_receipt(
        ten_path, ten_scores,
        initial_selection_receipt_path=initial_path,
        initial_score_receipt_paths=initial_scores,
        trusted_source_root=_TEST_TRUSTED_ROOT,
    )
    reselected = StageOneSelectionReceipt.from_dict(
        json.loads(ten_path.read_text(encoding="utf-8"))
    )

    assert reselected.phase == "ten_seed_reselection"
    assert set(reselected.decision.retained_methods) <= set(
        initial.decision.expand_to_ten_seeds
    )
    assert ascending_conditions(
        reselected.decision.retained_methods,
        seeds=(101,), folds=(0,),
        stage_one_selection_receipt_path=ten_path,
        stage_one_score_receipt_paths=ten_scores,
        initial_stage_one_selection_receipt_path=initial_path,
        initial_stage_one_score_receipt_paths=initial_scores,
        trusted_source_root=_TEST_TRUSTED_ROOT,
    )


def test_hash_bound_ten_seed_reselection_requires_initial_five_seeds(
    tmp_path: Path,
):
    """The expanded screen must retain the original five random draws."""
    initial_path, initial_scores = _stage_one_score_artifacts(
        tmp_path / "five", declared_seeds=(101, 102, 103, 104, 105)
    )
    initial = StageOneSelectionReceipt.from_dict(
        json.loads(initial_path.read_text(encoding="utf-8"))
    )
    ten_path, fresh_ten_scores = _stage_one_score_artifacts(
        tmp_path / "fresh-ten",
        declared_seeds=(201, 202, 203, 204, 205, 206, 207, 208, 209, 210),
        method_pairs=initial.decision.expand_to_ten_seeds,
        write_selection=False,
    )

    with pytest.raises(ValueError, match="initial five support seeds"):
        write_stage_one_selection_receipt(
            ten_path,
            fresh_ten_scores,
            initial_selection_receipt_path=initial_path,
            initial_score_receipt_paths=initial_scores,
            trusted_source_root=_TEST_TRUSTED_ROOT,
        )
def test_stage_one_rejects_a_full_looking_hand_authored_score_receipt(tmp_path: Path):
    """JSON fields and hashes alone cannot substitute for a scorer derivation."""
    _, score_paths = _stage_one_score_artifacts(
        tmp_path, write_selection=False, reuse=False
    )
    forged = json.loads(score_paths[0].read_text(encoding="utf-8"))
    forged["candidate_branch_top1"]["repvit_global"]["novel_macro_recall"] = 0.37
    score_paths[0].write_bytes(canonical_json_bytes(forged))

    with pytest.raises(ValueError, match="derived scorer"):
        write_stage_one_selection_receipt(
            tmp_path / "selection.json", score_paths,
            trusted_source_root=_TEST_TRUSTED_ROOT,
        )


def test_stage_one_cache_rechecks_raw_evidence_bytes_before_reuse(tmp_path: Path):
    """A cached scorer reconstruction cannot hide post-validation artifact edits."""
    selection_path, score_paths = _stage_one_score_artifacts(tmp_path, reuse=False)
    receipt = json.loads(score_paths[0].read_text(encoding="utf-8"))
    evidence_path = Path(receipt["raw_evidence"]["candidate"]["path"])
    evidence_path.write_bytes(b"tampered\n")

    with pytest.raises(ValueError, match="derived scorer"):
        load_stage_one_selection_receipt(
            selection_path,
            score_receipt_paths=score_paths,
            trusted_source_root=_TEST_TRUSTED_ROOT,
        )


def test_stage_one_derivation_cache_reauthenticates_materialized_raw_images(
    tmp_path: Path,
):
    """A cached re-derivation cannot conceal a raw-image replacement."""
    selection_path, score_paths = _stage_one_score_artifacts(tmp_path, reuse=False)
    receipt = json.loads(score_paths[0].read_text(encoding="utf-8"))
    rpc_scoring.validate_score_receipt_derivation(
        receipt, trusted_source_root=_TEST_TRUSTED_ROOT
    )
    fixture = _scoring_fixture()
    trusted = fixture._trusted_index()
    tampered = replace(
        trusted,
        images=tuple(
            replace(image, sha256="f" * 64)
            if image.split == "val2019" and image.image_id == 1
            else image
            for image in trusted.images
        ),
    )
    fixture._install_trusted_index_for_test(tampered)

    with pytest.raises(ValueError, match="trusted RPC source split"):
        rpc_scoring.validate_score_receipt_derivation(
            receipt, trusted_source_root=_TEST_TRUSTED_ROOT
        )


def test_confirmation_and_locked_conditions_bind_the_150_shot_reference(tmp_path: Path):
    confirmation = confirmation_conditions(
        ("m0", "div"),
        shot_counts=(4, 5, 10, 150),
        seeds=(101,),
        folds=(0,),
    )
    selected, paths = _stage_four_selection_artifacts(tmp_path)
    locked = locked_conditions(
        selected, confirmation_score_receipt_paths=paths, trusted_index=_trusted_index()
    )

    assert {condition.stage for condition in confirmation} == {"confirmation"}
    assert {condition.shot_count for condition in confirmation} == {4, 5, 10, 150}
    assert {condition.stage for condition in locked} == {"locked"}
    assert {condition.shot_count for condition in locked} == {5, 150}


def test_k1_stage_four_selection_has_no_imaginary_lower_failure(monkeypatch: pytest.MonkeyPatch):
    conditions = confirmation_conditions(
        ("m0", "div"), shot_counts=(1, 3, 150), seeds=(101,), folds=(0,)
    )
    selection = StageFourSelection(
        tuple(
            StageFourConfirmationReceipt(
                condition=condition,
                score_receipt_sha256=f"{index + 1:x}" * 64,
                provisional_pass=True,
            )
            for index, condition in enumerate(conditions)
        )
    )

    assert selection.provisional_minimum_shot_count == 1
    assert selection.is_lowest_shot_special_case
    monkeypatch.setattr(
        _rpc_protocol,
        "validate_stage_four_confirmation_score_receipts",
        lambda *args, **kwargs: None,
    )
    locked = locked_conditions(
        selection,
        confirmation_score_receipt_paths=(Path("one"), Path("three"), Path("reference")),
        trusted_index=_trusted_index(),
    )
    assert {item.shot_count for item in locked} == {1, 150}
    with pytest.raises(ValueError, match="next passing anchor"):
        StageFourSelection(tuple(replace(item, provisional_pass=item.condition.shot_count != 3) for item in selection.confirmation_receipts))


def test_k80_stage_four_selection_reuses_150_as_next_anchor_and_reference(
    monkeypatch: pytest.MonkeyPatch,
):
    """Rejecting the three-receipt k=80 certificate would leave k=80 unconfirmable."""
    conditions = confirmation_conditions(
        ("m0", "div"), shot_counts=(40, 80, 150), seeds=(101,), folds=(0,)
    )
    selection = StageFourSelection(
        tuple(
            StageFourConfirmationReceipt(
                condition=condition,
                score_receipt_sha256=f"{index + 1:x}" * 64,
                provisional_pass=condition.shot_count != 40,
            )
            for index, condition in enumerate(conditions)
        )
    )

    assert selection.provisional_minimum_shot_count == 80
    assert not selection.is_lowest_shot_special_case
    monkeypatch.setattr(
        _rpc_protocol,
        "validate_stage_four_confirmation_score_receipts",
        lambda *args, **kwargs: None,
    )
    locked = locked_conditions(
        selection,
        confirmation_score_receipt_paths=(Path("forty"), Path("eighty"), Path("reference")),
        trusted_index=_trusted_index(),
    )
    assert {item.shot_count for item in locked} == {80, 150}


def test_k80_three_receipt_exception_still_requires_the_40_shot_failure():
    """Accepting a passing k=40 would turn the fixed exception into a bypass."""
    conditions = confirmation_conditions(
        ("m0", "div"), shot_counts=(40, 80, 150), seeds=(101,), folds=(0,)
    )

    with pytest.raises(ValueError, match="last failure"):
        StageFourSelection(
            tuple(
                StageFourConfirmationReceipt(
                    condition=condition,
                    score_receipt_sha256=f"{index + 1:x}" * 64,
                    provisional_pass=True,
                )
                for index, condition in enumerate(conditions)
            )
        )


def test_stage_four_requires_the_preregistered_adjacent_larger_anchor():
    """A certificate cannot skip the fixed predecessor or next larger anchor."""
    skipped_anchor = tuple(
        _rpc_protocol._new_condition("m0", "div", shot, 0, 101, "confirmation")
        for shot in (1, 5, 20, 150)
    )
    skipped_certificate = tuple(
        StageFourConfirmationReceipt(
            condition=condition,
            score_receipt_sha256=f"{index + 1:x}" * 64,
            provisional_pass=condition.shot_count != 1,
        )
        for index, condition in enumerate(skipped_anchor)
    )

    with pytest.raises(ValueError, match="preceding ascending point"):
        StageFourSelection(skipped_certificate)
    with pytest.raises(ValueError, match="preceding ascending point"):
        confirmation_conditions(
            ("m0", "div"),
            shot_counts=(1, 5, 20, 150),
            seeds=(101,),
            folds=(0,),
        )

    valid_conditions = confirmation_conditions(
        ("m0", "div"),
        shot_counts=(4, 5, 10, 150),
        seeds=(101,),
        folds=(0,),
    )
    valid = StageFourSelection(
        tuple(
            StageFourConfirmationReceipt(
                condition=condition,
                score_receipt_sha256=f"{index + 5:x}" * 64,
                provisional_pass=condition.shot_count != 4,
            )
            for index, condition in enumerate(valid_conditions)
        )
    )

    assert valid.provisional_minimum_shot_count == 5


def test_stage_four_rejects_a_provisional_candidate_that_skips_ascending_lineage():
    """k=8 cannot cite k=1 as its last failure after skipping k=3/5/6."""
    skipped_candidate = tuple(
        _rpc_protocol._new_condition("m0", "div", shot, 0, 101, "confirmation")
        for shot in (1, 8, 10, 150)
    )

    with pytest.raises(ValueError, match="immediate preceding ascending point"):
        StageFourSelection(
            tuple(
                StageFourConfirmationReceipt(
                    condition=condition,
                    score_receipt_sha256=f"{index + 1:x}" * 64,
                    provisional_pass=condition.shot_count != 1,
                )
                for index, condition in enumerate(skipped_candidate)
            )
        )


def test_all_available_is_an_ascending_diagnostic_not_a_shot_condition():
    conditions = all_available_diagnostic_conditions(("m0", "div"), folds=(0,))

    assert len(conditions) == 1
    assert conditions[0].support_scope == "all_available"
    assert conditions[0].shot_count == 0
    assert conditions[0].stage == "ascending"
    with pytest.raises(ValueError, match="all_available"):
        replace(conditions[0], stage="confirmation")


def test_all_available_receipt_is_labeled_as_diagnostic_only():
    condition = all_available_diagnostic_conditions(("m0", "div"), folds=(0,))[0]
    plan = ScoringPlan(
        bootstrap_seed=7,
        bootstrap_replicates=10,
        folds=(0,),
        support_seeds=(0,),
        expected_condition_ids=(condition.condition_id,),
        cohort_id="rpc-test",
        registered_category_ids=(1, 2),
        fold_base_artifacts=(FoldBaseArtifact(0, "2" * 64, "3" * 64),),
    )
    receipt = ExperimentReceipt.completed(
        condition,
        condition_manifest_sha256=_HASH,
        model_sha256="b" * 64,
        support_sha256="c" * 64,
        calibration_sha256="d" * 64,
        policy_sha256="e" * 64,
        preprocessing_sha256="f" * 64,
        code_sha256="0" * 64,
        **_COHORT,
        scoring_plan=plan,
        base_checkpoint_sha256="2" * 64,
        base_checkpoint_evidence_sha256="3" * 64,
        environment_lock_digest="sha256:environment",
        output_uri="file:///external/run",
    )
    assert receipt.to_dict()["decision_scope"] == "upper_bound_diagnostic_not_a_minimum"


def test_stage_one_selection_preregisters_dominance_and_seed_expansion():
    result = select_stage_one_methods(
        (
            StageOneMethodEvidence("m0", "div", 0.91, 0.90, 0.10, 0.10),
            StageOneMethodEvidence("m1", "div", 0.88, 0.87, 0.11, 0.11),
            StageOneMethodEvidence("m2", "div", 0.905, 0.87, 0.08, 0.09),
        )
    )

    assert result.removed_methods == (("m1", "div"),)
    assert result.retained_methods == (("m0", "div"), ("m2", "div"))
    assert result.expand_to_ten_seeds == (("m0", "div"), ("m2", "div"))
    receipt = StageOneSelectionReceipt(
        evidence=(
            StageOneMethodEvidence("m0", "div", 0.91, 0.90, 0.10, 0.10),
            StageOneMethodEvidence("m1", "div", 0.88, 0.87, 0.11, 0.11),
            StageOneMethodEvidence("m2", "div", 0.905, 0.87, 0.08, 0.09),
        ),
        score_receipt_sha256s=("1" * 64, "2" * 64, "3" * 64),
        decision=result,
        declared_support_seeds=(101, 102, 103, 104, 105),
    )
    assert receipt.to_dict()["decision"]["retained_methods"] == [["m0", "div"], ["m2", "div"]]
    assert receipt.to_dict()["score_receipt_sha256s"] == ["1" * 64, "2" * 64, "3" * 64]


def test_stage_one_selection_receipt_rejects_a_non_screen_seed_count():
    evidence = (StageOneMethodEvidence("m0", "div", 0.9, 0.9, 0.1, 0.1),)
    with pytest.raises(ValueError, match="initial selection receipt"):
        StageOneSelectionReceipt(
            evidence=evidence,
            score_receipt_sha256s=("1" * 64,),
            decision=select_stage_one_methods(evidence),
            declared_support_seeds=(101,),
        )


def test_stage_one_selection_receipt_rejects_forged_scalar_evidence(tmp_path: Path):
    selection_path, score_paths = _stage_one_score_artifacts(tmp_path, reuse=False)
    forged = json.loads(selection_path.read_text(encoding="utf-8"))
    forged["evidence"][0]["repvit_novel_macro_top1"] = 0.01
    selection_path.write_bytes(canonical_json_bytes(forged))

    with pytest.raises(ValueError, match="Stage-1 selection receipt"):
        load_stage_one_selection_receipt(
            selection_path, score_receipt_paths=score_paths,
            trusted_source_root=_TEST_TRUSTED_ROOT,
        )


def test_ascending_rejects_rejected_pair_even_with_valid_stage_one_receipt(
    tmp_path: Path,
):
    selection_path, score_paths, initial_path, initial_scores = (
        _resolved_ten_seed_stage_one_artifacts(tmp_path, clear_winner=True)
    )
    selection = load_stage_one_selection_receipt(
        selection_path, score_receipt_paths=score_paths,
        initial_selection_receipt_path=initial_path,
        initial_score_receipt_paths=initial_scores,
        trusted_source_root=_TEST_TRUSTED_ROOT,
    )
    rejected = next(
        pair for pair in (("m0", "div"), ("m1", "div"), ("m2", "div"), ("m2", "rnd"))
        if pair not in selection.decision.retained_methods
    )

    with pytest.raises(ValueError, match="exactly the Stage-1 retained"):
        ascending_conditions(
            (rejected,),
            seeds=(101,),
            folds=(0,),
            stage_one_selection_receipt_path=selection_path,
            stage_one_score_receipt_paths=score_paths,
            initial_stage_one_selection_receipt_path=initial_path,
            initial_stage_one_score_receipt_paths=initial_scores,
            trusted_source_root=_TEST_TRUSTED_ROOT,
        )


def test_stage_one_selection_requires_all_twelve_preregistered_cells(tmp_path: Path):
    selection_path = tmp_path / "selection.json"
    _, score_paths = _stage_one_score_artifacts(tmp_path)

    with pytest.raises(ValueError, match="every preregistered 12-cell"):
        write_stage_one_selection_receipt(
            selection_path, score_paths[:-1], trusted_source_root=_TEST_TRUSTED_ROOT
        )
    assert not selection_path.exists()


def test_stage_one_selection_requires_all_declared_fold_seed_cells(tmp_path: Path):
    selection_path = tmp_path / "selection.json"
    _, score_paths = _stage_one_score_artifacts(
        tmp_path,
        declared_seeds=(101, 102, 103, 104, 105),
        write_selection=False,
    )

    with pytest.raises(ValueError, match="declared fold/seed"):
        write_stage_one_selection_receipt(
            selection_path, score_paths[:12], trusted_source_root=_TEST_TRUSTED_ROOT
        )
    assert not selection_path.exists()


def _stage_four_selection() -> StageFourSelection:
    conditions = confirmation_conditions(
        ("m0", "div"),
        shot_counts=(4, 5, 10, 150),
        seeds=(101,),
        folds=(0,),
    )
    return StageFourSelection(
        confirmation_receipts=tuple(
            StageFourConfirmationReceipt(
                condition=condition,
                score_receipt_sha256=f"{index + 1:x}" * 64,
                provisional_pass=condition.shot_count != 4,
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
    # Preserve the source-owned Stage-2/3 score lineage as well as the
    # re-hashed copied confirmation artifacts.  The copied selection must
    # remain schedulable only when that complete lineage is present.
    return StageFourSelection(tuple(claims), selection.ascending_receipts), tuple(paths)


def _trusted_index():
    """Load the independent hermetic resolver from the score fixture module."""
    specification = importlib.util.spec_from_file_location(
        "rpc_scoring_plan_trusted_index_fixture",
        Path(__file__).with_name("test_rpc_scoring_plan.py"),
    )
    assert specification is not None and specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    sys.modules[specification.name] = module
    specification.loader.exec_module(module)
    return module._trusted_index()


def _branch_summaries() -> dict[str, object]:
    return {
        branch: {
            "sample_count": 2,
            "novel_macro_recall": 1.0,
            "base_macro_recall": 1.0,
            "per_category_recall": {"1": 1.0, "2": 1.0},
            "confusion_matrix": {"1": {"1": 1}, "2": {"2": 1}},
            "fifth_percentile_sku_accuracy": 1.0,
            "wrong_registered_sku_rate": 0.0,
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
        "conditional_dino_execution_rate": 0.5,
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
        selection, confirmation_score_receipt_paths=paths, trusted_index=_trusted_index()
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
            trusted_index=_trusted_index(),
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
            tampered, confirmation_score_receipt_paths=paths, trusted_index=_trusted_index()
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
            mismatched, confirmation_score_receipt_paths=paths, trusted_index=_trusted_index()
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
        locked_conditions(
            selection, confirmation_score_receipt_paths=paths, trusted_index=_trusted_index()
        )


def test_locked_experiment_receipt_records_foreign_cohort_without_authorizing_it(
    tmp_path: Path,
):
    """Construction records a run; scorer derivation remains the authority."""
    selection, paths = _stage_four_selection_artifacts(tmp_path)
    condition = next(
        item
        for item in locked_conditions(
            selection, confirmation_score_receipt_paths=paths, trusted_index=_trusted_index()
        )
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

    receipt = ExperimentReceipt.completed(
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
    assert receipt.status == "completed"


@pytest.mark.parametrize("last_failure, first_pass, expected", [(3, 5, (4,)), (5, 10, (6, 8)), (10, 20, (12, 15, 18))])
def test_refinement_shots_are_preregistered(last_failure: int, first_pass: int, expected: tuple[int, ...]):
    assert refinement_shots(last_failure, first_pass) == expected


def test_refinement_shots_reject_unregistered_interval():
    with pytest.raises(ValueError, match="preregistered"):
        refinement_shots(1, 3)


@pytest.mark.parametrize("methods", [(("m1", "rnd"),), (("m0", "div"), ("m0", "div")), (("m0", "div"), ("m1", "div"), ("m2", "div"))])
def test_ascending_rejects_unsupported_or_non_preregistered_methods(methods: tuple[tuple[str, str], ...], tmp_path: Path):
    selection_path, score_paths = _stage_one_score_artifacts(tmp_path)
    with pytest.raises(ValueError):
        ascending_conditions(
            methods,
            seeds=(101,),
            folds=(0,),
            stage_one_selection_receipt_path=selection_path,
            stage_one_score_receipt_paths=score_paths,
            trusted_source_root=_TEST_TRUSTED_ROOT,
        )


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


def test_public_locked_artifact_apis_do_not_accept_caller_constructed_indexes():
    """Only a verified RPC source root may establish trusted raw data."""
    for function in (
        rpc_scoring.load_locked_ground_truth,
        rpc_scoring.materialize_locked_ground_truth,
        rpc_scoring.score,
        rpc_scoring.aggregate_score_receipts,
        rpc_scoring.validate_stage_four_confirmation_derivation,
        _rpc_protocol.locked_conditions,
        _rpc_protocol.validate_stage_four_confirmation_score_receipts,
        _rpc_protocol.validate_stage_four_binding_for_locked_target,
    ):
        signature = inspect.signature(function)
        assert "trusted_index" not in signature.parameters
        assert signature.parameters["trusted_source_root"].default is inspect.Signature.empty


def test_locked_receipt_cannot_bypass_stage_four_derivation_after_construction():
    """A structural training receipt is never an authority for Stage-5 completion."""
    selection = _stage_four_selection()
    condition = ExperimentCondition(
        "m0", "div", 5, 0, 101, "locked",
        _condition_id("m0", "div", 5, 0, 101, "locked"),
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
            FoldBaseArtifact(0, "2" * 64, "3" * 64),
        ),
    )
    receipt = ExperimentReceipt.completed(
            condition,
            condition_manifest_sha256=_HASH,
            model_sha256="b" * 64,
            support_sha256="c" * 64,
            calibration_sha256="d" * 64,
            policy_sha256="e" * 64,
            preprocessing_sha256="f" * 64,
            code_sha256="0" * 64,
            **_COHORT,
            scoring_plan=plan,
            base_checkpoint_sha256="2" * 64,
            base_checkpoint_evidence_sha256="3" * 64,
            environment_lock_digest="sha256:environment",
            output_uri="file:///external/run",
            stage_four_selection=selection,
            stage_four_confirmation_score_receipt_paths=(),
    )
    assert receipt.status == "completed"
