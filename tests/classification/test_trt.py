from __future__ import annotations

from dataclasses import dataclass

import pytest

from bakery_scanner.classification.trt import (
    DinoBatchEvidence,
    DinoTensorRtRunner,
    GpuCrop,
    GpuCropPair,
    RepVitBatchEvidence,
    RepVitTensorRtRunner,
    TensorRtInferenceError,
)


@dataclass
class Tensor:
    shape: tuple[int, ...]
    dtype: str = "float16"


class InputBuffer(Tensor):
    def __init__(self, shape):
        super().__init__(shape)
        self.staged = []

    def stage_rows(self, rows, *, valid_mask, stream):
        self.staged.append((tuple(row.object_order for row in rows), tuple(valid_mask)))


class Output(Tensor):
    def __init__(self, shape):
        super().__init__(shape)
        self.reads = []


class Session:
    def __init__(self, outputs):
        self.outputs = outputs
        self.calls = []
        self.fail_at = None

    def execute(self, bindings, stream):
        self.calls.append(tuple(bindings["crops"].shape))
        if self.fail_at == len(self.calls):
            raise RuntimeError("CUDA OOM")
        return self.outputs


def crop(order):
    return GpuCrop(Tensor((3, 224, 224)), object_order=order)


def pair(order):
    return GpuCropPair(crop(order), crop(order), object_order=order)


def repvit_decoder(outputs, valid_rows):
    outputs["logits"].reads.append(valid_rows)
    return tuple(
        RepVitBatchEvidence((0.9,) + (0.1 / 19,) * 19, (0.9,) + (0.1 / 19,) * 19)
        for _ in range(len(valid_rows) // 2)
    )


def dino_decoder(outputs, valid_rows):
    outputs["global_embeddings"].reads.append(valid_rows)
    outputs["local_patch_tokens"].reads.append(valid_rows)
    return tuple(
        DinoBatchEvidence(
            (0.9,) + (0.1 / 19,) * 19, (1, 2, 3), (0.9, 0.08, 0.02), 12, 0.6
        )
        for _ in valid_rows
    )


def test_repvit_chunks_eight_objects_in_order_and_never_reads_padding():
    output = Output((14, 20))
    session = Session({"logits": output})
    buffer = InputBuffer((14, 3, 224, 224))
    runner = RepVitTensorRtRunner(session, object(), buffer, repvit_decoder)

    evidence = runner.score_pairs(tuple(pair(i) for i in range(1, 9)))

    assert len(evidence) == 8
    assert session.calls == [(14, 3, 224, 224), (14, 3, 224, 224)]
    assert buffer.staged[0][1] == (True,) * 14
    assert buffer.staged[1][1] == (True, True) + (False,) * 12
    assert output.reads == [tuple(range(14)), (0, 1)]


@pytest.mark.parametrize("count", [1, 2, 8, 15])
def test_repvit_accepts_every_positive_object_count(count):
    session = Session({"logits": Output((14, 20))})
    runner = RepVitTensorRtRunner(
        session, object(), InputBuffer((14, 3, 224, 224)), repvit_decoder
    )
    assert len(runner.score_pairs(tuple(pair(i) for i in range(1, count + 1)))) == count


def test_dino_chunks_only_rejections_and_masks_the_last_chunk():
    outputs = {
        "global_embeddings": Output((7, 384)),
        "local_patch_tokens": Output((7, 196, 384)),
    }
    session = Session(outputs)
    buffer = InputBuffer((7, 3, 224, 224))
    runner = DinoTensorRtRunner(session, object(), buffer, dino_decoder)

    evidence = runner.score_rejections(tuple(crop(i) for i in range(1, 9)))

    assert len(evidence) == 8
    assert buffer.staged[1][1] == (True,) + (False,) * 6
    assert outputs["global_embeddings"].reads == [tuple(range(7)), (0,)]


def test_chunk_failure_is_raised_without_returning_partial_evidence():
    session = Session({"logits": Output((14, 20))})
    session.fail_at = 2
    runner = RepVitTensorRtRunner(
        session, object(), InputBuffer((14, 3, 224, 224)), repvit_decoder
    )
    with pytest.raises(TensorRtInferenceError, match="RepViT.*chunk 2"):
        runner.score_pairs(tuple(pair(i) for i in range(1, 9)))
