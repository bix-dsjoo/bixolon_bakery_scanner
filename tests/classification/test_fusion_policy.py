from bakery_scanner.classification.full_evidence import FullEvidenceRow
import pytest

from bakery_scanner.classification.fusion_policy import FusionPolicyArtifact, validate_evidence_hashes
from bakery_scanner.classification.fusion_ranker import FusionRanker
from bakery_scanner.classification.risk_calibrator import RiskCalibrator


def test_fusion_policy_artifact_round_trips_canonical_common_models():
    artifact = FusionPolicyArtifact(
        ranker=FusionRanker((0.0,) * 9, (1.0,) * 9, (0.0,) * 9, 0.0),
        risk_calibrator=RiskCalibrator((0.0,) * 9, (1.0,) * 9, (0.0,) * 9, 0.0),
        risk_threshold=0.2,
        development_evidence_sha256="0" * 64,
        artifact_hashes={
            "repvit_checkpoint_sha256": "1" * 64,
            "repvit_manifest_sha256": "2" * 64,
            "repvit_prototype_sha256": "3" * 64,
            "dinov3_weights_sha256": "4" * 64,
            "dinov3_support_sha256": "5" * 64,
            "dinov3_local_bank_sha256": "6" * 64,
            "preprocess_sha256": "7" * 64,
        },
    )

    assert FusionPolicyArtifact.from_json_bytes(artifact.to_json_bytes()) == artifact


def test_fusion_policy_uses_one_fixed_risk_threshold_for_sku_or_unknown():
    artifact = FusionPolicyArtifact(
        ranker=FusionRanker((0.0,) * 9, (1.0,) * 9, (0.0,) * 9, 0.0),
        risk_calibrator=RiskCalibrator((0.0,) * 9, (1.0,) * 9, (0.0,) * 9, 0.0),
        risk_threshold=0.6,
        development_evidence_sha256="0" * 64,
        artifact_hashes={
            "repvit_checkpoint_sha256": "1" * 64,
            "repvit_manifest_sha256": "2" * 64,
            "repvit_prototype_sha256": "3" * 64,
            "dinov3_weights_sha256": "4" * 64,
            "dinov3_support_sha256": "5" * 64,
            "dinov3_local_bank_sha256": "6" * 64,
            "preprocess_sha256": "7" * 64,
        },
    )
    row = FullEvidenceRow(
        sample_id="locked-1", capture_group="group-1", registered=True, sku_id=1,
        role="locked_acceptance", image_sha256="a" * 64,
        repvit_values=(0.1,) * 20, dinov3_values=(0.2,) * 20,
        candidate_sku_ids=(1, 2, 3), local_values=(0.3, 0.2, 0.1),
        repvit_crop_disagreement=0.01, nearest_prototype_distance=0.1,
        local_product_patch_count=16, local_product_patch_ratio=0.8,
        repvit_checkpoint_sha256="1" * 64, repvit_manifest_sha256="2" * 64,
        repvit_prototype_sha256="3" * 64, dinov3_weights_sha256="4" * 64,
        dinov3_support_sha256="5" * 64, dinov3_local_bank_sha256="6" * 64,
        preprocess_sha256="7" * 64,
    )

    decision, risk = artifact.decide(row)

    assert risk == 0.5
    assert decision.decision == "sku"
    assert decision.predicted_sku_id == 1


def test_fusion_policy_rejects_evidence_built_with_different_model_artifacts():
    row = FullEvidenceRow(
        sample_id="locked-1", capture_group="group-1", registered=True, sku_id=1,
        role="locked_acceptance", image_sha256="a" * 64,
        repvit_values=(0.1,) * 20, dinov3_values=(0.2,) * 20,
        candidate_sku_ids=(1, 2, 3), local_values=(0.3, 0.2, 0.1),
        repvit_crop_disagreement=0.01, nearest_prototype_distance=0.1,
        local_product_patch_count=16, local_product_patch_ratio=0.8,
        repvit_checkpoint_sha256="1" * 64, repvit_manifest_sha256="2" * 64,
        repvit_prototype_sha256="3" * 64, dinov3_weights_sha256="4" * 64,
        dinov3_support_sha256="5" * 64, dinov3_local_bank_sha256="6" * 64,
        preprocess_sha256="7" * 64,
    )
    expected = {
        "repvit_checkpoint_sha256": "1" * 64, "repvit_manifest_sha256": "2" * 64,
        "repvit_prototype_sha256": "3" * 64, "dinov3_weights_sha256": "4" * 64,
        "dinov3_support_sha256": "5" * 64, "dinov3_local_bank_sha256": "6" * 64,
        "preprocess_sha256": "0" * 64,
    }

    with pytest.raises(ValueError, match="artifact hash"):
        validate_evidence_hashes((row,), expected)
