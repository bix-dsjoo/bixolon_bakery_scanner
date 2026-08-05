from __future__ import annotations

from dataclasses import dataclass

import pytest

from bakery_scanner.contracts import Box, BreadProposal
from bakery_scanner.detection.rfdetr_trt import (
    CanonicalGpuFrame,
    DetectorTensorRtError,
    RfDetrTensorRtRunner,
)


@dataclass
class Tensor:
    shape: tuple[int, ...]
    dtype: str = "float16"


class Buffer(Tensor):
    def __init__(self):
        super().__init__((1, 3, 640, 640))
        self.frames = []

    def stage_frame(self, frame, *, stream):
        self.frames.append(frame)


class Session:
    def __init__(self, outputs):
        self.outputs = outputs
        self.calls = 0

    def execute(self, bindings, stream):
        self.calls += 1
        return self.outputs


def proposal(frame):
    return BreadProposal(
        1,
        "rfdetr_l_bread_gpu_fp16_v1",
        0.91,
        Box(10, 20, 30, 40),
        frame.width,
        frame.height,
    )


def test_detector_executes_static_binding_and_returns_canonical_boxes():
    boxes, scores = Tensor((1, 300, 4)), Tensor((1, 300))
    session, buffer = Session({"boxes": boxes, "scores": scores}), Buffer()
    frame = CanonicalGpuFrame(
        100, 80, 6, Tensor((80, 100, 3), "uint8"), "exif_visual_rgb_v1"
    )
    runner = RfDetrTensorRtRunner(
        session, object(), buffer, lambda outputs, canonical: (proposal(canonical),)
    )

    assert runner.detect(frame) == (proposal(frame),)
    assert session.calls == 1
    assert buffer.frames == [frame]


@pytest.mark.parametrize(
    "bad", ["wrong_size", "wrong_source", "unordered", "non_tuple"]
)
def test_detector_rejects_malformed_or_noncanonical_decoder_output(bad):
    frame = CanonicalGpuFrame(
        100, 80, 1, Tensor((80, 100, 3), "uint8"), "exif_visual_rgb_v1"
    )
    valid = proposal(frame)
    if bad == "wrong_size":
        decoded = (BreadProposal(1, valid.source, valid.score, valid.box, 101, 80),)
    elif bad == "wrong_source":
        decoded = (BreadProposal(1, "legacy", valid.score, valid.box, 100, 80),)
    elif bad == "unordered":
        decoded = (
            BreadProposal(1, valid.source, 0.9, Box(50, 50, 10, 10), 100, 80),
            BreadProposal(1, valid.source, 0.9, Box(5, 5, 10, 10), 100, 80),
        )
    else:
        decoded = [valid]
    runner = RfDetrTensorRtRunner(
        Session({"boxes": Tensor((1, 300, 4)), "scores": Tensor((1, 300))}),
        object(),
        Buffer(),
        lambda outputs, canonical: decoded,
    )
    with pytest.raises(DetectorTensorRtError):
        runner.detect(frame)
