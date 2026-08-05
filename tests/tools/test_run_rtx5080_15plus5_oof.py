from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from tools.evaluate.run_rtx5080_15plus5_oof import (
    ArtifactAdmissionError,
    REQUIRED_FOLD_ARTIFACT_ROLES,
    _utility_without_top3_passed,
    build_compact_receipt,
    expected_artifact_ids,
    load_fold_execution_specs,
    select_status,
    verify_row_artifact_binding,
    verify_exact_fold_union,
    write_external_raw_rows,
    write_unverified_checkpoint,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SPLITS = REPOSITORY_ROOT / "data" / "splits" / "rtx5080_15plus5_oof_v1"


def _declared_by_fold() -> dict[int, tuple[str, ...]]:
    return {
        fold: tuple(
            json.loads((SPLITS / f"fold-{fold}.json").read_text(encoding="utf-8"))[
                "scene_ids"
            ]["evaluation"]
        )
        for fold in range(5)
    }


def test_exact_fold_union_accepts_each_canonical_scene_once() -> None:
    declared = _declared_by_fold()

    verified = verify_exact_fold_union(declared, splits=SPLITS)

    assert len(verified) == 299
    assert verified == tuple(
        json.loads((SPLITS / "inventory.json").read_text(encoding="utf-8"))[
            "scene_ids"
        ]
    )


def test_exact_fold_union_rejects_missing_result() -> None:
    declared = _declared_by_fold()
    declared[2] = declared[2][:-1]

    with pytest.raises(ValueError, match="exactly 299"):
        verify_exact_fold_union(declared, splits=SPLITS)


def test_exact_fold_union_rejects_duplicate_or_wrong_fold_result() -> None:
    declared = _declared_by_fold()
    declared[1] = (*declared[1][:-1], declared[0][0])

    with pytest.raises(ValueError, match="exactly once|declared evaluation"):
        verify_exact_fold_union(declared, splits=SPLITS)


@pytest.mark.parametrize(
    ("wrong", "critical", "utility", "top3", "expected"),
    (
        (1, 0, False, False, "quality-rejected"),
        (0, 1, True, True, "quality-rejected"),
        (0, 0, False, True, "utility-rejected"),
        (0, 0, True, False, "quality-rejected"),
        (0, 0, True, True, "quality-passed-performance-unverified"),
    ),
)
def test_status_selection_is_fail_closed_and_top3_is_independent(
    wrong: int,
    critical: int,
    utility: bool,
    top3: bool,
    expected: str,
) -> None:
    assert (
        select_status(
            wrong_auto_approval_count=wrong,
            accepted_scan_critical_failure_count=critical,
            utility_passed=utility,
            top3_passed=top3,
        )
        == expected
    )


def _fabricated_acceptance() -> dict[str, object]:
    private_path = r"C:\private\datasets\scan.jpg"
    acceptance = {
        "status": "quality-accepted",
        "scene_count": 299,
        "object_count": 1406,
        "registered_object_total": 1200,
        "unknown_count": 206,
        "quality": {
            "miss_count": 0,
            "duplicate_count": 0,
            "non_target_detection_count": 0,
            "split_count": 0,
            "merge_count": 0,
            "detected_count_mismatch_count": 0,
            "object_order_mismatch_count": 0,
            "wrong_auto_approval_count": 0,
            "accepted_scan_critical_failure_count": 0,
            "scan_error_upper_95": 0.01,
            "object_error_upper_95": 0.002,
            "scan_sample_size": 299,
            "object_sample_size": 1406,
            "private_path": private_path,
        },
        "utility": {
            "passes": True,
            "unknown_top3_recall": {
                "overall": 0.97,
                "E": 0.96,
                "M": 0.98,
                "H": 0.97,
            },
            "normal_scan_acceptance": {"overall": 0.9, "E": 0.9, "M": 0.9, "H": 0.9},
            "unnecessary_retake": {"overall": 0.1, "E": 0.1, "M": 0.1, "H": 0.1},
            "auto_sku_approval_coverage": {"overall": 0.8, "E": 0.8, "M": 0.8, "H": 0.8},
            "unknown_rate": {"overall": 0.2, "E": 0.2, "M": 0.2, "H": 0.2},
            "incremental_auto_sku_approval_coverage": 0.7,
            "counterfactual_completeness_block_rate": {
                "missing": 1.0,
                "split": 1.0,
                "merge": 1.0,
                "truncation": 1.0,
            },
            "counterfactual_expected_case_count": {
                "missing": 299,
                "split": 299,
                "merge": 299,
                "truncation": 299,
            },
            "counterfactual_submitted_case_count": {
                "missing": 299,
                "split": 299,
                "merge": 299,
                "truncation": 299,
            },
            "missing_required_slices": [],
            "has_violation": False,
            "private_payload": {"path": private_path},
        },
        "top3_rank_hits": {"rank_1": 100, "rank_2": 20, "rank_3": 10, "miss": 5},
        "object_count_slices": {"count_1_2": 0, "count_3_7": 299, "count_8_plus": 0},
        "report_slices": {"difficulty": {"E": 100, "M": 99, "H": 100}},
        "quality_claims_by_count": {
            "count_1_2": None,
            "count_3_7": "current_oof_evidence",
            "count_8_plus": None,
        },
        "policy_by_fold": {str(fold): hashlib.sha256(f"policy-{fold}".encode()).hexdigest() for fold in range(5)},
        "seed_by_fold": {str(fold): 20260803 for fold in range(5)},
        "acceptance_sources": {"combined_sha256": "a" * 64},
        "evaluation_input_sha256": "b" * 64,
        "evaluation_row_count": 315,
        "completeness_evidence_index_sha256": "c" * 64,
        "sample_size_limit": "observed OOF only",
        "raw_predictions": [{"image_path": private_path}],
    }
    return acceptance


def test_compact_receipt_rejects_private_relative_scene_and_raw_nested_payload() -> None:
    acceptance = _fabricated_acceptance()
    quality = acceptance["quality"]
    utility = acceptance["utility"]
    assert isinstance(quality, dict) and isinstance(utility, dict)
    quality["private_scene"] = "customer-order-scene-0001.jpg"
    utility["raw_payload"] = {
        "prediction": {"object_id": "customer-order-object-9"}
    }

    with pytest.raises(ValueError, match="validated Task 6|unknown|private|raw"):
        build_compact_receipt(acceptance)


def test_quality_pass_cannot_be_built_from_fabricated_acceptance_mapping() -> None:
    acceptance = _fabricated_acceptance()
    quality = acceptance["quality"]
    utility = acceptance["utility"]
    assert isinstance(quality, dict) and isinstance(utility, dict)
    quality.pop("private_path")
    utility.pop("private_payload")
    acceptance.pop("raw_predictions")

    with pytest.raises(ValueError, match="validated Task 6|frozen"):
        build_compact_receipt(acceptance)


def test_top3_missing_slice_is_quality_failure_not_utility_failure() -> None:
    utility = {
        "normal_scan_acceptance": {"overall": 0.9, "E": 0.9, "M": 0.9, "H": 0.9},
        "unnecessary_retake": {"overall": 0.1, "E": 0.1, "M": 0.1, "H": 0.1},
        "auto_sku_approval_coverage": {"overall": 0.8, "E": 0.8, "M": 0.8, "H": 0.8},
        "unknown_rate": {"overall": 0.2, "E": 0.2, "M": 0.2, "H": 0.2},
        "incremental_auto_sku_approval_coverage": 0.7,
        "counterfactual_completeness_block_rate": {
            "missing": 1.0,
            "split": 1.0,
            "merge": 1.0,
            "truncation": 1.0,
        },
        "missing_required_slices": ["unknown_top3_recall:H"],
    }

    assert _utility_without_top3_passed(utility) is True
    assert select_status(
        wrong_auto_approval_count=0,
        accepted_scan_critical_failure_count=0,
        utility_passed=True,
        top3_passed=False,
    ) == "quality-rejected"


def _artifact_tree(root: Path) -> None:
    for fold in range(5):
        fold_root = root / f"fold-{fold}"
        fold_root.mkdir(parents=True)
        for role in REQUIRED_FOLD_ARTIFACT_ROLES:
            payload = fold_root / f"{role}.bin"
            payload.write_bytes(f"{fold}:{role}".encode())
            descriptor = {
                "schema_version": 1,
                "artifact_id": f"fold-{fold}:{role}",
                "role": role,
                "file": payload.name,
                "bytes": payload.stat().st_size,
                "sha256": hashlib.sha256(payload.read_bytes()).hexdigest(),
            }
            (fold_root / f"{role}.json").write_text(
                json.dumps(descriptor), encoding="utf-8"
            )


def test_fold_artifact_loader_verifies_exact_declared_bytes(tmp_path: Path) -> None:
    _artifact_tree(tmp_path)

    specs = load_fold_execution_specs(tmp_path, splits=SPLITS)

    assert tuple(spec.fold_index for spec in specs) == (0, 1, 2, 3, 4)
    assert len(specs[0].evaluation_scene_ids) == 60
    assert set(specs[0].artifact_sha256) == set(REQUIRED_FOLD_ARTIFACT_ROLES)
    assert specs[0].policy_sha256 == specs[0].artifact_sha256["fold_policy"]


def test_fold_artifact_loader_rejects_tampered_declared_bytes(tmp_path: Path) -> None:
    _artifact_tree(tmp_path)
    (tmp_path / "fold-3" / "repvit_checkpoint.bin").write_bytes(b"tampered")

    with pytest.raises(ArtifactAdmissionError, match="fold-3:repvit_checkpoint"):
        load_fold_execution_specs(tmp_path, splits=SPLITS)


def test_evaluation_row_must_bind_every_declared_fold_artifact() -> None:
    hashes = {role: hashlib.sha256(role.encode()).hexdigest() for role in REQUIRED_FOLD_ARTIFACT_ROLES}
    row = SimpleNamespace(
        code_sha256=hashes["code"],
        detector_sha256=hashes["detector"],
        dinov3_local_bank_sha256=hashes["dinov3_local_bank"],
        dinov3_support_sha256=hashes["dinov3_support"],
        dinov3_weights_sha256=hashes["dinov3_weights"],
        fold_policy_sha256=hashes["fold_policy"],
        preprocess_sha256=hashes["preprocess"],
        repvit_checkpoint_sha256=hashes["repvit_checkpoint"],
        repvit_prototype_sha256=hashes["repvit_prototype"],
        runtime_sha256=hashes["runtime"],
        completeness_evidence_index_sha256=hashes["completeness_evidence"],
        evidence_kind="observed",
        counterfactual_source_evidence=SimpleNamespace(
            completeness_policy_artifact_sha256=hashes["completeness_policy"]
        ),
    )

    verify_row_artifact_binding(row, hashes)

    row.detector_sha256 = "f" * 64
    with pytest.raises(ValueError, match="detector"):
        verify_row_artifact_binding(row, hashes)


def test_unverified_checkpoint_lists_exact_missing_ids_without_fake_metrics(
    tmp_path: Path,
) -> None:
    output = tmp_path / "checkpoint.json"
    summary = tmp_path / "summary.md"
    missing = expected_artifact_ids()

    payload = write_unverified_checkpoint(
        output,
        summary,
        missing_artifact_ids=missing,
    )

    assert payload == json.loads(output.read_text(encoding="utf-8"))
    assert payload["status"] == "unverified_missing_artifacts"
    assert payload["missing_artifact_ids"] == list(missing)
    assert "quality" not in payload
    assert "utility" not in payload
    assert "Top3" not in summary.read_text(encoding="utf-8")
    assert set(REQUIRED_FOLD_ARTIFACT_ROLES) == {
        artifact_id.split(":", 1)[1] for artifact_id in missing
    }


def test_external_raw_rows_require_identified_predictions_timings_and_external_output(
    tmp_path: Path,
) -> None:
    output = tmp_path / "external" / "raw.json"
    row = {
        "scene_id": "private-scene-name",
        "fold_index": 0,
        "input_sha256": "a" * 64,
        "artifact_sha256": {role: "b" * 64 for role in REQUIRED_FOLD_ARTIFACT_ROLES},
        "predictions": [{"object_id": "object-1", "state": "unknown", "top3": [1, 2, 3]}],
        "timings_ms": {"total": 42.0},
        "status": "verified",
    }

    receipt = write_external_raw_rows(output, (row,), repository_root=REPOSITORY_ROOT)

    assert receipt["row_count"] == 1
    assert receipt["rows_sha256"] == hashlib.sha256(output.read_bytes()).hexdigest()
    persisted = json.loads(output.read_text(encoding="utf-8"))
    assert persisted["rows"] == [row]
    with pytest.raises(ValueError, match="outside the repository"):
        write_external_raw_rows(
            REPOSITORY_ROOT / "raw-private.json",
            (row,),
            repository_root=REPOSITORY_ROOT,
        )
