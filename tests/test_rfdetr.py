from types import SimpleNamespace
from pathlib import Path

import numpy as np
from PIL import Image

from bakery_scanner.contracts import Box
from bakery_scanner.detectors.rfdetr import RFDetrRunner


class _FakeModel:
    def predict(self, image, *, threshold, include_source_image):
        assert image.size == (100, 60)
        assert threshold == 0.5
        assert include_source_image is False
        return SimpleNamespace(
            xyxy=np.asarray([
                [-5.0, 3.0, 101.0, 65.0],
                [25.0, 10.0, 25.0, 30.0],
                [120.0, 10.0, 130.0, 30.0],
                [0.0, 0.0, 2.0, 2.0],
            ]),
            confidence=np.asarray([0.8, 0.7, 0.6, 0.9]),
            class_id=np.asarray([0, 0, 0, 1]),
            data={"class_name": np.asarray(["product", "product", "product", "__background__"])},
        )


def test_rfdetr_runner_clips_product_boxes_and_rejects_background_or_empty_geometry():
    runner = RFDetrRunner.from_model(_FakeModel(), score_threshold=0.5)

    proposals = runner.predict(7, Image.new("RGB", (100, 60)))

    assert len(proposals) == 1
    proposal = proposals[0]
    assert proposal.image_id == 7
    assert proposal.source == "rfdetr_large_bakery_v1"
    assert proposal.score == 0.8
    assert proposal.box == Box(0.0, 3.0, 100.0, 57.0)
    assert proposal.class_id == 1
    assert proposal.class_name == "bread"


def test_rfdetr_loader_passes_cpu_device_to_the_backend_factory(tmp_path):
    checkpoint = tmp_path / "checkpoint.pth"
    checkpoint.write_bytes(b"checkpoint")
    calls = []

    class Backend:
        def predict(self, *args, **kwargs):
            raise AssertionError("not used")

    runner = RFDetrRunner.load(
        checkpoint,
        score_threshold=0.5,
        device="cpu",
        model_factory=lambda **kwargs: calls.append(kwargs) or Backend(),
    )

    assert runner.source == "rfdetr_large_bakery_v1"
    assert calls == [{"pretrain_weights": str(checkpoint.resolve()), "num_classes": 1, "device": "cpu"}]
