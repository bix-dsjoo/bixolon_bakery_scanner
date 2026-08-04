from pathlib import Path
from types import SimpleNamespace

from PIL import Image

from bakery_scanner.contracts import Box, BreadProposal
from bakery_scanner.prototype.camera_runtime import CameraInferenceRuntime


class _ReferenceBackend:
    """Minimal warmed backend so this test exercises runtime admission only."""

    detector_id = "rfdetr_large_bakery_v1"
    repvit_id = "repvit_m1_15plus5_v1"
    dinov3_id = "dinov3_vits16_15plus5_v1"
    fusion_policy_id = "fusion_local_or_global_consensus_margin_v1"
    detector_threshold = 0.8502742052078247
    applied_artifact_hashes = {
        key: "a" * 64
        for key in (
            "detector_checkpoint_sha256", "detector_calibration_sha256", "detector_manifest_sha256",
            "repvit_checkpoint_sha256", "repvit_manifest_sha256", "repvit_prototype_sha256",
            "dinov3_weights_sha256", "dinov3_support_sha256", "dinov3_local_bank_sha256",
            "classifier_calibration_sha256", "preprocess_sha256", "fusion_policy_sha256",
            "presentation_policy_sha256",
        )
    }

    def __init__(self, device: str) -> None:
        self.device = device
        self.detector = SimpleNamespace(
            source=self.detector_id,
            predict=lambda image_id, image: (
                BreadProposal(1, self.detector_id, 0.9, Box(1, 1, 4, 4), 8, 8),
            ),
        )
        self.classifier = SimpleNamespace(
            config=SimpleNamespace(runtime=SimpleNamespace(mode="serial_reference")),
            preflight_models=lambda image, box: None,
            infer=lambda image, box: None,
        )

    def close(self) -> None:
        pass


def test_production_default_keeps_unverified_rfdetr_engine_out_of_automatic_routing(
    tmp_path: Path,
):
    """CUDA availability alone must not admit the draft RF-DETR TensorRT route."""
    warmup_image = tmp_path / "warmup.jpg"
    Image.new("RGB", (8, 8), "white").save(warmup_image, format="JPEG")

    runtime = CameraInferenceRuntime.initialize(
        Path.cwd(),
        warmup_image,
        preference="auto",
        cuda_probe=lambda: True,
        backend_loader=_ReferenceBackend,
    )
    try:
        assert runtime.device == "cuda:0"
        assert runtime.runtime_mode == "gpu_reference"
        assert runtime.startup_metrics.fallback_reason == "rfdetr_engine_parity_missing"
    finally:
        runtime.close()
