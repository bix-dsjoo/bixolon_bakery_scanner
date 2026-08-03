from __future__ import annotations

import hashlib
from io import BytesIO
import json
import math
from pathlib import Path
from dataclasses import replace

import pytest
import torch
from PIL import Image

from bakery_scanner.classification.config import ClassifierConfig, preprocess_sha256
from bakery_scanner.classification.contracts import (
    DecisionPath,
    ModelProvenance,
    ModelScoreVector,
)
from bakery_scanner.classification.dinov3 import DinoGlobalLocalEvidence, DinoV3Rechecker
from bakery_scanner.classification.fusion_policy import FusionPolicyArtifact
from bakery_scanner.classification.fusion_ranker import FusionRanker
from bakery_scanner.classification.policy import DecisionPolicy, PolicyCalibration
from bakery_scanner.classification.preprocess import build_transform
from bakery_scanner.classification.preprocess import ClassifierPreprocessDescriptor
from bakery_scanner.classification.repvit import RepVitEvidence
from bakery_scanner.classification.risk_calibrator import RiskCalibrator
from bakery_scanner.classification.runtime import (
    ClassifierPipeline,
    CudaTimingCollector,
    TightContextRepVitEvidence,
    SerialStageTimings,
)
from bakery_scanner.contracts import Box


SKU_IDS = tuple(range(1, 21))


class RecordingRunner:
    def __init__(self, scores: ModelScoreVector, *, crop_disagreement: float = 0.01) -> None:
        self.scores = scores
        self.crop_disagreement = crop_disagreement
        self.received_crops: tuple[Image.Image, ...] | None = None
        self.call_count = 0

    def score(self, crops: tuple[Image.Image, ...]) -> ModelScoreVector:
        self.call_count += 1
        self.received_crops = crops
        return self.scores

    def score_with_evidence(self, crops: tuple[Image.Image, ...]) -> RepVitEvidence:
        scores = self.score(crops)
        return RepVitEvidence(
            scores=scores,
            feature=torch.ones(384),
            crop_disagreement=self.crop_disagreement,
        )


class StageCheckingRunner(RecordingRunner):
    def __init__(
        self,
        scores: ModelScoreVector,
        *,
        stages: list[str],
        expected_stages: tuple[str, ...],
    ) -> None:
        super().__init__(scores)
        self.stages = stages
        self.expected_stages = expected_stages

    def score_with_evidence(self, crops: tuple[Image.Image, ...]) -> RepVitEvidence:
        assert tuple(self.stages) == self.expected_stages
        return super().score_with_evidence(crops)


class FixedPrototypeBank:
    def __init__(self, distance: float = 0.02) -> None:
        self.distance = distance

    def distances(self, feature: torch.Tensor) -> tuple[float, ...]:
        assert tuple(feature.shape) == (384,)
        return (self.distance,) + (1.0,) * 19


class OutOfMemoryEncoder(torch.nn.Module):
    def forward(self, batch: torch.Tensor) -> torch.Tensor:
        raise torch.OutOfMemoryError("sensitive backend detail")


class OutOfMemoryFeatureEncoder(torch.nn.Module):
    def forward_features(self, batch: torch.Tensor):
        raise torch.OutOfMemoryError("sensitive backend detail")


class ProgrammingErrorDino:
    def score(self, crops: tuple[Image.Image, ...]) -> ModelScoreVector:
        raise ValueError("wrong tensor shape")


class LocalRecordingDino(RecordingRunner):
    def __init__(self, scores: ModelScoreVector) -> None:
        super().__init__(scores)
        self.product_boxes: tuple[Box, ...] | None = None
        self.local_bank = None

    def score_global_and_local(self, crops, product_boxes, local_bank, *, repvit_scores):
        self.call_count += 1
        self.received_crops = crops
        self.product_boxes = tuple(product_boxes)
        self.local_bank = local_bank
        assert repvit_scores.model_id == "repvit_m1_15plus5_v1"
        return self.scores, {6: 0.90, 5: 0.10}


class FullEvidenceDino(LocalRecordingDino):
    def __init__(self, scores: ModelScoreVector) -> None:
        super().__init__(scores)
        self.full_evidence_call_count = 0

    def score_global_and_local_evidence(self, crops, product_boxes, local_bank, *, repvit_scores):
        self.full_evidence_call_count += 1
        scores, local = self.score_global_and_local(crops, product_boxes, local_bank, repvit_scores=repvit_scores)
        return scores, local, 32, 0.5


class DisagreeingFullEvidenceDino(FullEvidenceDino):
    def score_global_and_local_evidence(self, crops, product_boxes, local_bank, *, repvit_scores):
        scores, _, patch_count, patch_ratio = super().score_global_and_local_evidence(
            crops, product_boxes, local_bank, repvit_scores=repvit_scores,
        )
        return scores, {6: 0.10, 5: 0.90, 4: 0.01}, patch_count, patch_ratio


class ManyRecordingRunner(RecordingRunner):
    def __init__(self, evidence: tuple[RepVitEvidence, ...]) -> None:
        super().__init__(evidence[0].scores)
        self.evidence = evidence
        self.received_object_count = 0

    def score_many_with_evidence(self, crop_groups, *, max_objects):
        assert max_objects == 2
        self.received_object_count = len(crop_groups)
        return self.evidence


class ManyFullEvidenceDino(FullEvidenceDino):
    def __init__(self, evidence: tuple[DinoGlobalLocalEvidence, ...]) -> None:
        super().__init__(evidence[0].global_scores)
        self.evidence = evidence
        self.received_object_count = 0

    def score_many_global_and_local_evidence(
        self, crop_groups, product_box_groups, local_bank, *, repvit_scores, max_objects
    ):
        assert max_objects == 2
        self.received_object_count = len(crop_groups)
        return self.evidence


class PreflightRecordingRepVit(RecordingRunner):
    def __init__(self, scores: ModelScoreVector) -> None:
        super().__init__(scores)
        self.serial_calls = 0
        self.batch_calls = 0
        self.batch_max_objects: int | None = None
        self.returned_evidence: list[RepVitEvidence] = []

    def score_with_evidence(self, crops: tuple[Image.Image, ...]) -> RepVitEvidence:
        self.serial_calls += 1
        evidence = super().score_with_evidence(crops)
        self.returned_evidence.append(evidence)
        return evidence

    def score_many_with_evidence(self, crop_groups, *, max_objects):
        self.batch_calls += 1
        self.batch_max_objects = max_objects
        evidence = tuple(
            RecordingRunner.score_with_evidence(self, crops) for crops in crop_groups
        )
        self.returned_evidence.extend(evidence)
        return evidence


class PreflightRecordingDino(RecordingRunner):
    def __init__(self, scores: ModelScoreVector) -> None:
        super().__init__(scores)
        self.global_local_calls = 0
        self.product_boxes: tuple[Box, ...] | None = None
        self.local_bank = None
        self.repvit_scores: ModelScoreVector | None = None
        self.local_scores = {6: 0.90, 5: 0.10}

    def score_global_and_local_evidence(
        self, crops, product_boxes, local_bank, *, repvit_scores
    ):
        self.global_local_calls += 1
        self.received_crops = crops
        self.product_boxes = tuple(product_boxes)
        self.local_bank = local_bank
        self.repvit_scores = repvit_scores
        assert repvit_scores.model_id == "repvit_m1_15plus5_v1"
        return self.scores, self.local_scores, 32, 0.5


class StepClock:
    def __init__(self, values: tuple[float, ...]) -> None:
        self._values = iter(values)
        self.sync_count = 0

    def synchronize(self) -> None:
        self.sync_count += 1

    def __call__(self) -> float:
        return next(self._values)


class ManualStageClock:
    def __init__(self) -> None:
        self.value = 0.0
        self.sync_count = 0

    def synchronize(self) -> None:
        self.sync_count += 1

    def __call__(self) -> float:
        return self.value

    def advance(self, seconds: float) -> None:
        self.value += seconds


class TimedRunner(RecordingRunner):
    def __init__(
        self,
        scores: ModelScoreVector,
        *,
        clock: ManualStageClock,
        duration: float,
    ) -> None:
        super().__init__(scores)
        self.clock = clock
        self.duration = duration

    def score(self, crops: tuple[Image.Image, ...]) -> ModelScoreVector:
        self.clock.advance(self.duration)
        return super().score(crops)


def test_cuda_event_collector_records_active_stream_ranges_and_syncs_only_on_finalize(monkeypatch):
    from bakery_scanner.classification import runtime

    operations: list[tuple[str, object]] = []

    class Event:
        def __init__(self, *, enable_timing):
            self.name = f"event-{sum(item[0] == 'event' for item in operations)}"
            operations.append(("event", enable_timing))

        def record(self, stream):
            operations.append(("record", (self.name, stream)))

        def elapsed_time(self, other):
            return 3.5

    monkeypatch.setattr(runtime.torch.cuda, "is_available", lambda: True)
    monkeypatch.setattr(runtime.torch.cuda, "current_stream", lambda device: "active-stream")
    monkeypatch.setattr(runtime.torch.cuda, "Event", Event)
    monkeypatch.setattr(runtime.torch.cuda, "synchronize", lambda device: operations.append(("sync", str(device))))
    monkeypatch.setattr(runtime.torch.cuda.nvtx, "range_push", lambda name: operations.append(("push", name)))
    monkeypatch.setattr(runtime.torch.cuda.nvtx, "range_pop", lambda: operations.append(("pop", None)))

    collector = CudaTimingCollector("cuda:0")
    collector.measure("repvit", lambda: operations.append(("launch", "repvit")))
    collector.measure("dinov3", lambda: operations.append(("launch", "dinov3")))
    assert not any(name == "sync" for name, _ in operations)

    assert collector.finalize() == {"repvit": 3.5, "dinov3": 3.5}
    assert [name for name, _ in operations].count("sync") == 1
    assert operations.index(("push", "repvit")) < operations.index(("launch", "repvit")) < operations.index(("pop", None))


def test_direct_repvit_confirmation_never_loads_or_calls_dino():
    dino_loads = 0

    def load_dino() -> RecordingRunner:
        nonlocal dino_loads
        dino_loads += 1
        return RecordingRunner(_dino_scores({6: 0.8, 5: 0.2}))

    repvit = RecordingRunner(_repvit_scores({6: 0.80, 5: 0.20}))
    original_box = _box()
    result = _pipeline(repvit=repvit, dino_loader=load_dino).infer(
        _image(), original_box
    )

    assert result.decision_path is DecisionPath.REPVIT_DIRECT
    assert result.sku_id == 6
    assert result.confidence == pytest.approx(0.80)
    assert result.box is original_box
    assert dino_loads == 0


def test_serial_timing_sink_records_stages_without_changing_decision():
    observed = []
    plain = _pipeline(
        repvit=RecordingRunner(_repvit_scores({6: 0.50, 5: 0.30, 19: 0.10})),
        dino_loader=lambda: RecordingRunner(_dino_scores({5: 0.50, 6: 0.30, 19: 0.10})),
    )
    instrumented = _pipeline(
        repvit=RecordingRunner(_repvit_scores({6: 0.50, 5: 0.30, 19: 0.10})),
        dino_loader=lambda: RecordingRunner(_dino_scores({5: 0.50, 6: 0.30, 19: 0.10})),
        stage_timing_sink=observed.append,
    )

    expected = plain.infer(_image(), _box())
    actual = instrumented.infer(_image(), _box())

    assert replace(actual, timings=expected.timings) == expected
    assert len(observed) == 1
    timing = observed[0]
    assert isinstance(timing, SerialStageTimings)
    assert timing.dino_executed is True
    assert timing.total_ms >= timing.crop_ms + timing.repvit_ms
    assert all(
        value >= 0.0
        for value in (
            timing.crop_ms,
            timing.repvit_ms,
            timing.dinov3_ms,
            timing.fusion_ms,
            timing.total_ms,
        )
    )


def test_serial_timing_sink_marks_direct_decision_without_dino():
    observed = []
    pipeline = _pipeline(
        repvit=RecordingRunner(_repvit_scores({6: 0.80, 5: 0.20})),
        dino_loader=lambda: pytest.fail("DINO must stay lazy"),
        stage_timing_sink=observed.append,
    )

    result = pipeline.infer(_image(), _box())

    assert result.decision_path is DecisionPath.REPVIT_DIRECT
    assert len(observed) == 1
    assert observed[0].dino_executed is False
    assert observed[0].dinov3_ms == 0.0
    assert observed[0].fusion_ms == 0.0


@pytest.mark.parametrize(
    "invalid_value",
    (-1.0, math.nan, math.inf, True),
    ids=("negative", "nan", "infinity", "bool"),
)
def test_serial_stage_timings_reject_non_finite_negative_or_non_numeric_values(invalid_value):
    with pytest.raises(ValueError, match="serial stage timings must be finite and non-negative"):
        SerialStageTimings(
            crop_ms=invalid_value,
            repvit_ms=0.0,
            dinov3_ms=0.0,
            fusion_ms=0.0,
            total_ms=0.0,
            dino_executed=False,
        )


def test_infer_many_batches_repvit_and_only_rechecks_direct_rejections():
    repvit = ManyRecordingRunner(
        (
            RepVitEvidence(_repvit_scores({6: 0.80, 5: 0.20}), torch.ones(384), 0.01),
            RepVitEvidence(_repvit_scores({5: 0.50, 6: 0.30}), torch.ones(384), 0.01),
            RepVitEvidence(_repvit_scores({19: 0.50, 6: 0.30}), torch.ones(384), 0.01),
        )
    )
    dino = ManyFullEvidenceDino(
        (
            DinoGlobalLocalEvidence(_dino_scores({5: 0.80}), {5: 0.90}, 32, 0.5),
            DinoGlobalLocalEvidence(_dino_scores({19: 0.80}), {19: 0.90}, 32, 0.5),
        )
    )
    pipeline = _pipeline(repvit=repvit, dino_loader=lambda: dino, local_bank=object())

    result = pipeline.infer_many(
        _image(),
        (Box(1, 1, 20, 20), Box(22, 1, 20, 20), Box(43, 1, 16, 20)),
        repvit_max_objects=2,
        dino_max_objects=2,
    )

    assert len(result.decisions) == 3
    assert result.decisions[0].decision_path is DecisionPath.REPVIT_DIRECT
    assert repvit.received_object_count == 3
    assert dino.received_object_count == 2
    assert result.dino_object_count == 2
    assert result.timings.total_ms >= result.timings.crop_ms + result.timings.repvit_ms


class StaticPairRunner(RecordingRunner):
    def __init__(self, evidence: tuple[TightContextRepVitEvidence, ...], *, fail_chunk: int | None = None) -> None:
        super().__init__(evidence[0].scores)
        self.evidence = evidence
        self.fail_chunk = fail_chunk
        self.chunks: list[tuple[tuple[Image.Image, ...], tuple[bool, ...]]] = []
        self.cursor = 0

    def score_tight_context_chunk(self, rows, *, valid_mask):
        self.chunks.append((tuple(rows), tuple(valid_mask)))
        if self.fail_chunk == len(self.chunks):
            raise RuntimeError("repvit static chunk failed")
        valid_objects = sum(valid_mask) // 2
        selected = self.evidence[self.cursor : self.cursor + valid_objects]
        self.cursor += valid_objects
        return selected


class StaticContextDino(FullEvidenceDino):
    def __init__(self, evidence: tuple[DinoGlobalLocalEvidence, ...], *, fail_chunk: int | None = None) -> None:
        super().__init__(evidence[0].global_scores)
        self.evidence = evidence
        self.fail_chunk = fail_chunk
        self.chunks = []
        self.cursor = 0

    def score_context_chunk_global_and_local_evidence(
        self, crops, product_boxes, local_bank, *, repvit_scores, valid_mask
    ):
        self.chunks.append((tuple(crops), tuple(product_boxes), tuple(valid_mask), tuple(repvit_scores)))
        if self.fail_chunk == len(self.chunks):
            raise RuntimeError("dino static chunk failed")
        valid_objects = sum(valid_mask)
        selected = self.evidence[self.cursor : self.cursor + valid_objects]
        self.cursor += valid_objects
        return selected


def _paired_evidence(
    aggregate: ModelScoreVector,
    tight: ModelScoreVector | None = None,
    context: ModelScoreVector | None = None,
) -> TightContextRepVitEvidence:
    return TightContextRepVitEvidence(
        scores=aggregate,
        tight_scores=tight or aggregate,
        context_scores=context or aggregate,
        feature=torch.ones(384),
        crop_disagreement=0.01,
    )


def test_direct_gate_rejects_tight_context_top1_disagreement():
    aggregate = _repvit_scores({6: 0.80, 5: 0.20})
    repvit = StaticPairRunner((
        _paired_evidence(
            aggregate,
            tight=_repvit_scores({6: 0.80, 5: 0.20}),
            context=_repvit_scores({5: 0.80, 6: 0.20}),
        ),
    ))
    dino = StaticContextDino((
        DinoGlobalLocalEvidence(_dino_scores({6: 0.80}), {6: 0.90}, 32, 0.5),
    ))
    pipeline = _static_pipeline(repvit=repvit, dino_loader=lambda: dino, local_bank=object())

    result = pipeline.infer_many(
        _image(), (_box(),), repvit_rows_per_invocation=14, dino_objects_per_invocation=7
    )

    assert result.dino_object_count == 1
    assert result.decisions[0].decision_path is not DecisionPath.REPVIT_DIRECT
    assert repvit.chunks[0][1] == (True, True) + (False,) * 12
    assert dino.chunks[0][2] == (True,) + (False,) * 6
    assert dino.chunks[0][0][0].size == (44, 22)


def test_static_route_requires_immutable_fusion_before_repvit_execution():
    aggregate = _repvit_scores({6: 0.80, 5: 0.20})
    repvit = StaticPairRunner((_paired_evidence(aggregate),))

    with pytest.raises(ValueError, match="immutable fusion"):
        _pipeline(repvit=repvit, dino_loader=lambda: pytest.fail("DINO must not load")).infer_many(
            _image(), (_box(),), repvit_rows_per_invocation=14, dino_objects_per_invocation=7
        )

    assert repvit.chunks == []


def test_static_preprocess_hash_is_distinct_and_mismatch_aborts_before_repvit():
    descriptor_hash = ClassifierPreprocessDescriptor().sha256()
    legacy_hash = preprocess_sha256(ClassifierConfig.load(Path("configs/classifier_policy.yaml")).preprocess)
    assert descriptor_hash != legacy_hash
    aggregate = _repvit_scores({6: 0.80, 5: 0.20})
    repvit = StaticPairRunner((_paired_evidence(aggregate),))

    with pytest.raises(ValueError, match="static preprocessing"):
        _fusion_pipeline(
            mode="batch_pytorch", repvit=repvit,
            dino_loader=lambda: pytest.fail("DINO must not load"), local_bank=object(),
        ).infer_many(
            _image(), (_box(),), repvit_rows_per_invocation=14, dino_objects_per_invocation=7
        )

    assert repvit.chunks == []


def test_static_repvit_chunks_eight_objects_as_ordered_pairs_and_restores_order():
    boxes = tuple(Box(2 + index * 11, 10, 8, 10) for index in range(8))
    evidence = tuple(_paired_evidence(_repvit_scores({sku_id: 0.80, 20 if sku_id != 20 else 19: 0.20})) for sku_id in range(1, 9))
    repvit = StaticPairRunner(evidence)
    pipeline = _static_pipeline(repvit=repvit, dino_loader=lambda: pytest.fail("DINO must stay lazy"), local_bank=object())

    result = pipeline.infer_many(
        _image(), boxes, repvit_rows_per_invocation=14, dino_objects_per_invocation=7
    )

    assert [decision.box for decision in result.decisions] == list(boxes)
    assert len(repvit.chunks) == 2
    assert all(len(rows) == 14 and len(mask) == 14 for rows, mask in repvit.chunks)
    assert repvit.chunks[0][1] == (True,) * 14
    assert repvit.chunks[1][1] == (True, True) + (False,) * 12
    assert [crop.size for crop in repvit.chunks[0][0][:4]] == [(8, 10), (10, 12), (8, 10), (10, 12)]


def test_static_dino_receives_only_rejected_context_crops_in_seven_object_chunks():
    boxes = tuple(Box(2 + index * 11, 10, 8, 10) for index in range(8))
    rejected = tuple(_paired_evidence(_repvit_scores({6: 0.50, 5: 0.30})) for _ in boxes)
    dino_rows = tuple(DinoGlobalLocalEvidence(_dino_scores({6: 0.80}), {6: 0.90}, 32, 0.5) for _ in boxes)
    repvit = StaticPairRunner(rejected)
    dino = StaticContextDino(dino_rows)
    pipeline = _static_pipeline(repvit=repvit, dino_loader=lambda: dino, local_bank=object())

    result = pipeline.infer_many(
        _image(), boxes, repvit_rows_per_invocation=14, dino_objects_per_invocation=7
    )

    assert len(result.decisions) == 8
    assert result.dino_object_count == 8
    assert len(dino.chunks) == 2
    assert dino.chunks[0][2] == (True,) * 7
    assert dino.chunks[1][2] == (True,) + (False,) * 6
    assert all(crop.size == (10, 12) for crop in dino.chunks[0][0])


def test_static_chunk_failure_aborts_whole_operation_without_partial_decisions():
    boxes = tuple(Box(2 + index * 11, 10, 8, 10) for index in range(8))
    evidence = tuple(_paired_evidence(_repvit_scores({6: 0.80, 5: 0.20})) for _ in boxes)
    repvit = StaticPairRunner(evidence, fail_chunk=2)

    with pytest.raises(RuntimeError, match="static chunk failed"):
        _static_pipeline(repvit=repvit, dino_loader=lambda: pytest.fail("DINO must not load"), local_bank=object()).infer_many(
            _image(), boxes, repvit_rows_per_invocation=14, dino_objects_per_invocation=7
        )


def test_static_batch_contract_accepts_one_two_and_more_than_seven_objects():
    for count in (1, 2, 8):
        boxes = tuple(Box(2 + index * 11, 10, 8, 10) for index in range(count))
        evidence = tuple(_paired_evidence(_repvit_scores({6: 0.80, 5: 0.20})) for _ in boxes)
        result = _static_pipeline(
            repvit=StaticPairRunner(evidence),
            dino_loader=lambda: pytest.fail("DINO must stay lazy"),
            local_bank=object(),
        ).infer_many(
            _image(), boxes, repvit_rows_per_invocation=14, dino_objects_per_invocation=7
        )
        assert len(result.decisions) == count


def test_batch_shared_cuda_timing_never_synchronizes_the_host_clock():
    evidence = RepVitEvidence(_repvit_scores({6: 0.80, 5: 0.20}), torch.ones(384), 0.01)
    clock = ManualStageClock()

    class SharedTiming:
        def measure(self, _stage, action):
            return action()

    pipeline = _pipeline(
        repvit=ManyRecordingRunner((evidence,)),
        dino_loader=lambda: pytest.fail("direct decision must not load DINO"),
        clock=clock,
    )

    pipeline.infer_many(
        _image(),
        (Box(1, 1, 20, 20),),
        repvit_max_objects=2,
        dino_max_objects=2,
        cuda_timing=SharedTiming(),
    )

    assert clock.sync_count == 0


def test_batch_standalone_cuda_timing_finalizes_the_host_clock_once(monkeypatch):
    from bakery_scanner.classification import runtime

    class Event:
        def __init__(self, *, enable_timing):
            assert enable_timing is True

        def record(self, _stream):
            return None

        def elapsed_time(self, _other):
            return 1.0

    monkeypatch.setattr(runtime.torch.cuda, "is_available", lambda: True)
    monkeypatch.setattr(runtime.torch.cuda, "current_stream", lambda _device: object())
    monkeypatch.setattr(runtime.torch.cuda, "Event", Event)
    monkeypatch.setattr(runtime.torch.cuda.nvtx, "range_push", lambda _name: None)
    monkeypatch.setattr(runtime.torch.cuda.nvtx, "range_pop", lambda: None)
    clock = ManualStageClock()
    evidence = RepVitEvidence(_repvit_scores({6: 0.80, 5: 0.20}), torch.ones(384), 0.01)
    pipeline = _pipeline(
        repvit=ManyRecordingRunner((evidence,)),
        dino_loader=lambda: pytest.fail("direct decision must not load DINO"),
        clock=clock,
    )

    pipeline.infer_many(
        _image(), (Box(1, 1, 20, 20),),
        repvit_max_objects=2, dino_max_objects=2,
    )

    assert clock.sync_count == 1


def test_direct_decision_observes_only_repvit_stage():
    stages: list[str] = []
    repvit = StageCheckingRunner(
        _repvit_scores({6: 0.80, 5: 0.20}),
        stages=stages,
        expected_stages=("repvit",),
    )

    result = _pipeline(
        repvit=repvit,
        dino_loader=lambda: pytest.fail("DINO must stay lazy"),
    ).infer(_image(), _box(), on_stage=stages.append)

    assert result.decision_path is DecisionPath.REPVIT_DIRECT
    assert stages == ["repvit"]


def test_conditional_recheck_observes_repvit_then_dinov3_stages():
    stages: list[str] = []
    repvit = StageCheckingRunner(
        _repvit_scores({6: 0.50, 5: 0.30, 19: 0.10}),
        stages=stages,
        expected_stages=("repvit",),
    )
    dino = RecordingRunner(_dino_scores({5: 0.50, 6: 0.30, 19: 0.10}))

    def load_dino() -> RecordingRunner:
        assert tuple(stages) == ("repvit", "dinov3")
        return dino

    result = _pipeline(
        repvit=repvit,
        dino_loader=load_dino,
    ).infer(_image(), _box(), on_stage=stages.append)

    assert result.decision_path is DecisionPath.UNKNOWN_TOP3
    assert tuple(stages) == ("repvit", "dinov3")


def test_runtime_interprets_exif_oriented_input_in_visual_coordinates():
    encoded = BytesIO()
    exif = Image.Exif()
    exif[274] = 6
    Image.new("RGB", (40, 20), "white").save(encoded, format="JPEG", exif=exif)
    repvit = RecordingRunner(_repvit_scores({6: 0.80, 5: 0.20}))

    result = _pipeline(repvit=repvit, dino_loader=lambda: pytest.fail("DINO must stay lazy")).infer(
        Image.open(BytesIO(encoded.getvalue())),
        Box(1, 2, 10, 20),
    )

    assert result.box == Box(1, 2, 10, 20)
    assert result.provenance.canonical_frame_version == "exif_visual_rgb_v1"
    assert result.provenance.exif_orientation == 6
    assert tuple(crop.size for crop in repvit.received_crops or ()) == (
        (12, 22),
        (12, 22),
        (12, 24),
    )


def test_preflight_models_loads_and_scores_dino_before_all_direct_inference():
    repvit = RecordingRunner(_repvit_scores({6: 0.80, 5: 0.20}))
    dino = FullEvidenceDino(_dino_scores({6: 0.70, 5: 0.20}))
    local_bank = object()
    dino_loads = 0
    local_bank_loads = 0

    def load_dino() -> FullEvidenceDino:
        nonlocal dino_loads
        dino_loads += 1
        return dino

    def load_local_bank() -> object:
        nonlocal local_bank_loads
        local_bank_loads += 1
        return local_bank

    pipeline = _pipeline(
        repvit=repvit,
        dino_loader=load_dino,
        local_bank_loader=load_local_bank,
    )

    pipeline.preflight_models(_image(), _box())
    result = pipeline.infer(_image(), _box())

    assert result.decision_path is DecisionPath.REPVIT_DIRECT
    assert dino_loads == 1
    assert local_bank_loads == 1
    assert repvit.call_count == 2
    assert dino.call_count == 1
    assert dino.full_evidence_call_count == 1
    assert dino.local_bank is local_bank
    assert repvit.received_crops is not dino.received_crops
    assert tuple(crop.size for crop in dino.received_crops) == (
        (42, 22),
        (44, 22),
        (46, 24),
    )


@pytest.mark.parametrize(
    "mode, expected_serial, expected_batch",
    [
        ("serial_reference", 3, 0),
        ("batch_pytorch", 0, 1),
    ],
)
def test_benchmark_preflight_exercises_repvit_dino_local_and_fusion(
    monkeypatch, mode, expected_serial, expected_batch
):
    recorder = PreflightRecordingRepVit(_repvit_scores({6: 0.80, 5: 0.20}))
    dino = PreflightRecordingDino(_dino_scores({6: 0.70, 5: 0.20}))
    local_bank = object()
    first_box = Box(1, 1, 10, 10)
    pipeline = _fusion_pipeline(
        mode=mode,
        repvit=recorder,
        dino_loader=lambda: dino,
        local_bank=local_bank,
    )
    real_fusion_decision = pipeline._fusion_decision
    fusion_calls = []

    def record_real_fusion_call(**kwargs):
        fusion_calls.append(kwargs)
        return real_fusion_decision(**kwargs)

    monkeypatch.setattr(pipeline, "_fusion_decision", record_real_fusion_call)

    evidence = pipeline.preflight_benchmark(
        _image(),
        (first_box, Box(12, 1, 10, 10), Box(24, 1, 10, 10)),
        repvit_max_objects=2,
        dino_max_objects=2,
    )

    assert recorder.serial_calls == expected_serial
    assert recorder.batch_calls == expected_batch
    assert recorder.batch_max_objects == (2 if mode == "batch_pytorch" else None)
    assert dino.global_local_calls == 1
    assert dino.local_bank is local_bank
    assert tuple(crop.size for crop in dino.received_crops) == ((12, 12),) * 3
    assert dino.product_boxes == (Box(1, 1, 10, 10),) * 3
    assert len(fusion_calls) == 1
    fusion_call = fusion_calls[0]
    assert fusion_call["box"] is first_box
    assert fusion_call["repvit_scores"] is recorder.returned_evidence[0].scores
    assert fusion_call["repvit_scores"] is dino.repvit_scores
    assert fusion_call["dino_scores"] is dino.scores
    assert fusion_call["local_scores"] is dino.local_scores
    assert evidence.repvit == 3
    assert evidence.dinov3_global_local == 1
    assert evidence.fusion == 1


def test_benchmark_preflight_rejects_an_empty_box_sequence():
    pipeline = _fusion_pipeline(
        mode="serial_reference",
        repvit=PreflightRecordingRepVit(_repvit_scores({6: 0.80, 5: 0.20})),
        dino_loader=lambda: pytest.fail("DINO must not load"),
        local_bank=object(),
    )

    with pytest.raises(ValueError, match="requires at least one box"):
        pipeline.preflight_benchmark(
            _image(),
            (),
            repvit_max_objects=2,
            dino_max_objects=2,
        )


@pytest.mark.parametrize(
    "with_fusion, with_local, expected_message",
    [
        (False, True, "requires an immutable fusion policy"),
        (True, False, "requires a DINO local bank"),
    ],
)
def test_benchmark_preflight_rejects_missing_fusion_or_local_artifacts(
    with_fusion, with_local, expected_message
):
    repvit = PreflightRecordingRepVit(_repvit_scores({6: 0.80, 5: 0.20}))
    if with_fusion:
        pipeline = _fusion_pipeline(
            mode="serial_reference",
            repvit=repvit,
            dino_loader=lambda: pytest.fail("DINO must not load"),
            local_bank=object() if with_local else None,
        )
    else:
        pipeline = _pipeline(
            repvit=repvit,
            dino_loader=lambda: pytest.fail("DINO must not load"),
            local_bank=object() if with_local else None,
        )

    with pytest.raises(ValueError, match=expected_message):
        pipeline.preflight_benchmark(
            _image(),
            (_box(),),
            repvit_max_objects=2,
            dino_max_objects=2,
        )


def test_ambiguous_repvit_loads_dino_once_and_reuses_the_same_crops():
    repvit = RecordingRunner(_repvit_scores({6: 0.50, 5: 0.30, 19: 0.10}))
    dino = RecordingRunner(_dino_scores({5: 0.50, 6: 0.30, 19: 0.10}))
    dino_loads = 0

    def load_dino() -> RecordingRunner:
        nonlocal dino_loads
        dino_loads += 1
        return dino

    pipeline = _pipeline(repvit=repvit, dino_loader=load_dino)
    first = pipeline.infer(_image(), _box())
    second = pipeline.infer(_image(), _box())

    assert first.decision_path is DecisionPath.UNKNOWN_TOP3
    assert len(first.top3) == 3
    assert dino_loads == 1
    assert dino.call_count == 2
    assert repvit.received_crops is dino.received_crops
    payload = first.to_json_bytes()
    assert (
        json.dumps(
            json.loads(payload),
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        == payload
    )
    assert second.decision_path is DecisionPath.UNKNOWN_TOP3
    assert first.box == _box()
    assert second.box == _box()


def test_unsafe_repvit_prototype_distance_defers_to_dino():
    repvit = RecordingRunner(_repvit_scores({6: 0.80, 5: 0.20}))
    dino_loads = 0

    def load_dino() -> RecordingRunner:
        nonlocal dino_loads
        dino_loads += 1
        return RecordingRunner(_dino_scores({6: 0.70, 5: 0.20}))

    result = _pipeline(
        repvit=repvit,
        dino_loader=load_dino,
        prototype_bank=FixedPrototypeBank(0.21),
    ).infer(_image(), _box())

    assert result.decision_path is DecisionPath.DINOV3_CONFIRMED
    assert dino_loads == 1


def test_recheck_uses_local_dino_scores_and_crop_relative_product_boxes():
    repvit = RecordingRunner(_repvit_scores({6: 0.60, 5: 0.20}))
    dino = LocalRecordingDino(_dino_scores({6: 0.60, 5: 0.20}))
    local_bank = object()
    result = _pipeline(
        repvit=repvit,
        dino_loader=lambda: dino,
        local_bank=local_bank,
        calibration=_calibration(dino_threshold=0.20, fused_margin=0.10),
    ).infer(_image(), _box())

    assert result.decision_path is DecisionPath.DINOV3_CONFIRMED
    assert dino.local_bank is local_bank
    assert dino.product_boxes == (
        Box(1, 1, 40, 20),
        Box(2, 1, 40, 20),
        Box(3, 2, 40, 20),
    )


def test_runtime_fusion_local_agreement_uses_dino_evidence_despite_risk_abstention():
    config = ClassifierConfig.load(Path("configs/classifier_policy.yaml"))
    selected = _calibration(direct_threshold=0.99)
    provenance = ModelProvenance(
        repvit_artifact_id=selected.repvit_artifact_id, repvit_sha256="1" * 64,
        dinov3_artifact_id=selected.dinov3_artifact_id, dinov3_sha256="2" * 64,
        dinov3_support_sha256="3" * 64, calibration_id=selected.calibration_id,
        calibration_sha256=hashlib.sha256(selected.to_json_bytes()).hexdigest(),
    )
    fusion = FusionPolicyArtifact(
        ranker=FusionRanker((0.0,) * 9, (1.0,) * 9, (1.0,) + (0.0,) * 8, 0.0),
        risk_calibrator=RiskCalibrator((0.0,) * 9, (1.0,) * 9, (0.0,) * 9, 0.0),
        risk_threshold=0.2,
        development_evidence_sha256="0" * 64,
        artifact_hashes={
            "repvit_checkpoint_sha256": config.repvit.checkpoint_sha256,
            "repvit_manifest_sha256": config.repvit.manifest_sha256,
            "repvit_prototype_sha256": config.repvit.prototype_bank_sha256,
            "dinov3_weights_sha256": config.dinov3.weights_sha256,
            "dinov3_support_sha256": config.dinov3.support_sha256,
            "dinov3_local_bank_sha256": config.dinov3.local_bank_sha256,
            "preprocess_sha256": preprocess_sha256(config.preprocess),
        },
        decision_rule="fusion_local_agree_v1",
    )
    dino = FullEvidenceDino(_dino_scores({6: 0.60, 5: 0.20}))
    pipeline = ClassifierPipeline(
        config=config, repvit=RecordingRunner(_repvit_scores({6: 0.8, 5: 0.2})),
        dino_loader=lambda: dino, policy=DecisionPolicy(selected, provenance=provenance),
        prototype_bank=FixedPrototypeBank(), local_bank=object(), fusion_policy=fusion,
        fusion_provenance=replace(provenance, calibration_id="fusion_policy_v1", calibration_sha256="9" * 64),
    )

    result = pipeline.infer(_image(), _box())

    assert dino.call_count == 1
    assert result.decision_path is DecisionPath.FUSION_RANKED
    assert result.sku_id == 6
    assert result.provenance.calibration_id == "fusion_policy_v1"


def test_runtime_records_high_margin_consensus_abstention_reason():
    config = ClassifierConfig.load(Path("configs/classifier_policy.yaml"))
    selected = _calibration(direct_threshold=0.99)
    provenance = ModelProvenance(
        repvit_artifact_id=selected.repvit_artifact_id, repvit_sha256="1" * 64,
        dinov3_artifact_id=selected.dinov3_artifact_id, dinov3_sha256="2" * 64,
        dinov3_support_sha256="3" * 64, calibration_id=selected.calibration_id,
        calibration_sha256=hashlib.sha256(selected.to_json_bytes()).hexdigest(),
    )
    fusion = FusionPolicyArtifact(
        ranker=FusionRanker((0.0,) * 9, (1.0,) * 9, (2.0,) + (0.0,) * 8, 0.0),
        risk_calibrator=RiskCalibrator((0.0,) * 9, (1.0,) * 9, (0.0,) * 9, 0.0),
        risk_threshold=0.2,
        development_evidence_sha256="0" * 64,
        artifact_hashes={
            "repvit_checkpoint_sha256": config.repvit.checkpoint_sha256,
            "repvit_manifest_sha256": config.repvit.manifest_sha256,
            "repvit_prototype_sha256": config.repvit.prototype_bank_sha256,
            "dinov3_weights_sha256": config.dinov3.weights_sha256,
            "dinov3_support_sha256": config.dinov3.support_sha256,
            "dinov3_local_bank_sha256": config.dinov3.local_bank_sha256,
            "preprocess_sha256": preprocess_sha256(config.preprocess),
        },
        decision_rule="fusion_local_or_global_consensus_margin_v1",
        schema_version=3,
        consensus_margin_floor=0.85,
    )
    pipeline = ClassifierPipeline(
        config=config, repvit=RecordingRunner(_repvit_scores({6: 0.6, 5: 0.2})),
        dino_loader=lambda: DisagreeingFullEvidenceDino(_dino_scores({6: 0.6, 5: 0.2})),
        policy=DecisionPolicy(selected, provenance=provenance), prototype_bank=FixedPrototypeBank(),
        local_bank=object(), fusion_policy=fusion,
        fusion_provenance=replace(provenance, calibration_id="fusion_policy_v1", calibration_sha256="9" * 64),
    )

    result = pipeline.infer(_image(), _box())

    assert result.decision == "unknown"
    assert result.unknown_reason == "fusion_global_consensus_margin"


def test_recheck_confirmation_keeps_fused_confidence_meaning():
    calibration = _calibration(
        alpha=0.5,
        dino_threshold=0.40,
        fused_margin=0.10,
    )
    repvit = RecordingRunner(_repvit_scores({6: 0.40, 5: 0.30}))
    dino = RecordingRunner(_dino_scores({6: 0.40, 5: 0.30}))

    result = _pipeline(
        repvit=repvit,
        dino_loader=lambda: dino,
        calibration=calibration,
    ).infer(_image(), _box())

    assert result.decision_path is DecisionPath.DINOV3_CONFIRMED
    assert result.sku_id == 6
    assert result.confidence == pytest.approx(0.40)
    assert result.box == _box()


def test_runtime_records_provenance_stage_timings_and_synchronizes():
    clock = StepClock((10.000, 10.001, 10.004, 10.005, 10.011, 10.012))
    repvit = RecordingRunner(_repvit_scores({6: 0.50, 5: 0.30, 19: 0.10}))
    dino = RecordingRunner(_dino_scores({5: 0.50, 6: 0.30, 19: 0.10}))
    pipeline = _pipeline(
        repvit=repvit,
        dino_loader=lambda: dino,
        clock=clock,
    )

    result = pipeline.infer(_image(), _box())

    assert result.provenance == pipeline.policy.provenance
    assert result.provenance.repvit_sha256 == "1" * 64
    assert result.provenance.dinov3_sha256 == "2" * 64
    assert result.provenance.dinov3_support_sha256 == "3" * 64
    assert result.timings.repvit_ms == pytest.approx(3.0)
    assert result.timings.dinov3_ms == pytest.approx(6.0)
    assert result.timings.total_ms == pytest.approx(12.0)
    assert clock.sync_count == 6


def test_stage_observer_time_is_excluded_from_repvit_and_dinov3_timings():
    clock = ManualStageClock()
    repvit = TimedRunner(
        _repvit_scores({6: 0.50, 5: 0.30, 19: 0.10}),
        clock=clock,
        duration=0.004,
    )
    dino = TimedRunner(
        _dino_scores({5: 0.50, 6: 0.30, 19: 0.10}),
        clock=clock,
        duration=0.006,
    )
    pipeline = _pipeline(
        repvit=repvit,
        dino_loader=lambda: dino,
        clock=clock,
    )

    result = pipeline.infer(
        _image(),
        _box(),
        on_stage=lambda stage: clock.advance(1.0),
    )

    assert result.timings.repvit_ms == pytest.approx(4.0)
    assert result.timings.dinov3_ms == pytest.approx(6.0)
    assert result.timings.total_ms == pytest.approx(2010.0)


def test_dino_failure_returns_unknown_repvit_top3_and_safe_failure_code():
    repvit = RecordingRunner(_repvit_scores({19: 0.40, 6: 0.30, 5: 0.20}))
    real_dino = DinoV3Rechecker(
        OutOfMemoryEncoder(),
        torch.eye(384, dtype=torch.float32)[:20],
        SKU_IDS,
        build_transform(224),
        "dinov3_vits16_15plus5_v1",
        torch.device("cpu"),
    )

    result = _pipeline(
        repvit=repvit,
        dino_loader=lambda: real_dino,
    ).infer(_image(), _box())

    assert result.decision == "unknown"
    assert result.decision_path is DecisionPath.UNKNOWN_TOP3
    assert [(candidate.rank, candidate.sku_id) for candidate in result.top3] == [
        (1, 19),
        (2, 6),
        (3, 5),
    ]
    assert result.provenance.failure_code == "dino_out_of_memory"
    assert b"sensitive backend detail" not in result.to_json_bytes()
    assert result.box == _box()


def test_fusion_pipeline_dino_failure_keeps_effective_fusion_provenance():
    real_dino = DinoV3Rechecker(
        OutOfMemoryFeatureEncoder(),
        torch.eye(384, dtype=torch.float32)[:20],
        SKU_IDS,
        build_transform(224),
        "dinov3_vits16_15plus5_v1",
        torch.device("cpu"),
    )

    result = _fusion_pipeline(
        mode="serial_reference",
        repvit=RecordingRunner(_repvit_scores({19: 0.40, 6: 0.30, 5: 0.20})),
        dino_loader=lambda: real_dino,
        local_bank=object(),
    ).infer(_image(), _box())

    assert result.decision == "unknown"
    assert result.decision_path is DecisionPath.UNKNOWN_TOP3
    assert result.provenance.calibration_id == "fusion_policy_v1"
    assert result.provenance.calibration_sha256 == "9" * 64
    assert result.provenance.failure_code == "dino_out_of_memory"


def test_serial_timing_sink_records_dino_failure_policy_evaluation(monkeypatch):
    def failing_dino() -> DinoV3Rechecker:
        return DinoV3Rechecker(
            OutOfMemoryEncoder(),
            torch.eye(384, dtype=torch.float32)[:20],
            SKU_IDS,
            build_transform(224),
            "dinov3_vits16_15plus5_v1",
            torch.device("cpu"),
        )

    repvit_scores = _repvit_scores({19: 0.40, 6: 0.30, 5: 0.20})
    expected = _pipeline(
        repvit=RecordingRunner(repvit_scores),
        dino_loader=failing_dino,
        clock=StepClock((10.000, 10.001, 10.004, 10.005, 10.011, 10.012)),
    ).infer(_image(), _box())
    observed = []
    perf_counter_values = iter((0.000, 0.001, 0.002, 0.003, 0.004, 0.005, 0.006, 0.007, 0.008))
    monkeypatch.setattr(
        "bakery_scanner.classification.runtime.time.perf_counter",
        lambda: next(perf_counter_values),
    )

    actual = _pipeline(
        repvit=RecordingRunner(repvit_scores),
        dino_loader=failing_dino,
        clock=StepClock((10.000, 10.001, 10.004, 10.005, 10.011, 10.012)),
        stage_timing_sink=observed.append,
    ).infer(_image(), _box())

    assert actual == expected
    assert len(observed) == 1
    assert observed[0].dino_executed is True
    assert observed[0].fusion_ms == pytest.approx(1.0)


def test_dino_programming_error_is_not_converted_to_unknown():
    repvit = RecordingRunner(_repvit_scores({6: 0.50, 5: 0.30}))

    with pytest.raises(ValueError, match="wrong tensor shape"):
        _pipeline(
            repvit=repvit,
            dino_loader=ProgrammingErrorDino,
        ).infer(_image(), _box())


@pytest.mark.parametrize(
    "box",
    [
        Box(-1, 10, 40, 20),
        Box(10, -1, 40, 20),
        Box(61, 10, 40, 20),
        Box(10, 61, 40, 20),
    ],
)
def test_runtime_rejects_box_outside_canonical_visual_image(box):
    repvit = RecordingRunner(_repvit_scores({6: 0.80, 5: 0.20}))

    with pytest.raises(ValueError, match="canonical visual"):
        _pipeline(
            repvit=repvit,
            dino_loader=lambda: pytest.fail("DINO must not load"),
        ).infer(_image(), box)


def test_lazy_dino_initialization_failure_is_not_converted_to_unknown():
    repvit = RecordingRunner(_repvit_scores({6: 0.50, 5: 0.30}))

    def load_dino() -> RecordingRunner:
        raise ValueError("DINO artifact hash mismatch")

    with pytest.raises(ValueError, match="artifact hash mismatch"):
        _pipeline(repvit=repvit, dino_loader=load_dino).infer(_image(), _box())


def test_load_requires_calibration_before_loading_repvit(monkeypatch, tmp_path):
    config = ClassifierConfig.load(Path("configs/classifier_policy.yaml"))
    missing = tmp_path / "missing-policy.json"
    configured = config.model_copy(
        update={
            "calibration": config.calibration.model_copy(update={"artifact": missing})
        }
    )
    monkeypatch.setattr(
        "bakery_scanner.classification.runtime.ClassifierConfig.load",
        lambda path: configured,
    )
    monkeypatch.setattr(
        "bakery_scanner.classification.runtime.RepVitM1Runner.load",
        lambda config: pytest.fail("RepViT must not load without calibration"),
    )

    with pytest.raises(FileNotFoundError):
        ClassifierPipeline.load(tmp_path / "classifier.yaml")


def test_load_builds_provenance_and_defers_dino_model_load(monkeypatch, tmp_path):
    config = ClassifierConfig.load(Path("configs/classifier_policy.yaml"))
    calibration = _calibration(
        repvit_checkpoint_sha256=config.repvit.checkpoint_sha256,
        repvit_manifest_sha256=config.repvit.manifest_sha256,
        dinov3_weights_sha256=config.dinov3.weights_sha256,
        dinov3_support_sha256=config.dinov3.support_sha256,
        preprocess_sha256=preprocess_sha256(config.preprocess),
        repvit_prototype_sha256=config.repvit.prototype_bank_sha256,
        direct_max_prototype_distance=2.0,
    )
    calibration_path = tmp_path / "policy.json"
    calibration_path.write_bytes(calibration.to_json_bytes())
    configured = config.model_copy(
        update={
                "calibration": config.calibration.model_copy(
                    update={"artifact": calibration_path, "fusion_policy": None}
                )
        }
    )
    repvit = RecordingRunner(_repvit_scores({6: 0.80, 5: 0.20}))
    dino_loads = 0

    monkeypatch.setattr(
        "bakery_scanner.classification.runtime.ClassifierConfig.load",
        lambda path: configured,
    )
    monkeypatch.setattr(
        "bakery_scanner.classification.runtime.RepVitM1Runner.load",
        lambda loaded_config: repvit,
    )
    monkeypatch.setattr(
        "bakery_scanner.classification.runtime.RepVitPrototypeBank.load",
        lambda *args, **kwargs: FixedPrototypeBank(),
    )

    def load_dino(loaded_config):
        nonlocal dino_loads
        dino_loads += 1
        return RecordingRunner(_dino_scores({6: 0.7, 5: 0.2}))

    monkeypatch.setattr(
        "bakery_scanner.classification.runtime.DinoV3Rechecker.load",
        load_dino,
    )

    pipeline = ClassifierPipeline.load(tmp_path / "classifier.yaml")

    assert dino_loads == 0
    assert pipeline.policy.provenance == ModelProvenance(
        repvit_artifact_id=config.repvit.artifact_id,
        repvit_sha256=config.repvit.checkpoint_sha256,
        dinov3_artifact_id=config.dinov3.artifact_id,
        dinov3_sha256=config.dinov3.weights_sha256,
        dinov3_support_sha256=config.dinov3.support_sha256,
        calibration_id=calibration.calibration_id,
        calibration_sha256=hashlib.sha256(calibration.to_json_bytes()).hexdigest(),
        preprocess_sha256=preprocess_sha256(config.preprocess),
        repvit_manifest_sha256=config.repvit.manifest_sha256,
        repvit_prototype_sha256=config.repvit.prototype_bank_sha256,
    )
    pipeline.infer(_image(), _box())
    assert dino_loads == 0


def _pipeline(
    *,
    repvit: RecordingRunner,
    dino_loader,
    calibration: PolicyCalibration | None = None,
    clock=None,
    prototype_bank: FixedPrototypeBank | None = None,
    local_bank: object | None = None,
    local_bank_loader=None,
    stage_timing_sink=None,
) -> ClassifierPipeline:
    selected = calibration or _calibration()
    provenance = ModelProvenance(
        repvit_artifact_id=selected.repvit_artifact_id,
        repvit_sha256="1" * 64,
        dinov3_artifact_id=selected.dinov3_artifact_id,
        dinov3_sha256="2" * 64,
        dinov3_support_sha256="3" * 64,
        calibration_id=selected.calibration_id,
        calibration_sha256=hashlib.sha256(selected.to_json_bytes()).hexdigest(),
    )
    config = ClassifierConfig.load(Path("configs/classifier_policy.yaml"))
    return ClassifierPipeline(
        config=config,
        repvit=repvit,
        dino_loader=dino_loader,
        policy=DecisionPolicy(selected, provenance=provenance),
        clock=clock,
        prototype_bank=prototype_bank or FixedPrototypeBank(),
        local_bank=local_bank,
        local_bank_loader=local_bank_loader,
        stage_timing_sink=stage_timing_sink,
    )


def _fusion_pipeline(
    *,
    mode: str,
    repvit: RecordingRunner,
    dino_loader,
    local_bank: object | None,
) -> ClassifierPipeline:
    config = ClassifierConfig.load(Path("configs/classifier_policy.yaml"))
    config = config.model_copy(
        update={"runtime": config.runtime.model_copy(update={"mode": mode})}
    )
    selected = _calibration()
    provenance = ModelProvenance(
        repvit_artifact_id=selected.repvit_artifact_id,
        repvit_sha256="1" * 64,
        dinov3_artifact_id=selected.dinov3_artifact_id,
        dinov3_sha256="2" * 64,
        dinov3_support_sha256="3" * 64,
        calibration_id=selected.calibration_id,
        calibration_sha256=hashlib.sha256(selected.to_json_bytes()).hexdigest(),
    )
    fusion = FusionPolicyArtifact(
        ranker=FusionRanker((0.0,) * 9, (1.0,) * 9, (1.0,) + (0.0,) * 8, 0.0),
        risk_calibrator=RiskCalibrator((0.0,) * 9, (1.0,) * 9, (0.0,) * 9, 0.0),
        risk_threshold=0.2,
        development_evidence_sha256="0" * 64,
        artifact_hashes={
            "repvit_checkpoint_sha256": config.repvit.checkpoint_sha256,
            "repvit_manifest_sha256": config.repvit.manifest_sha256,
            "repvit_prototype_sha256": config.repvit.prototype_bank_sha256,
            "dinov3_weights_sha256": config.dinov3.weights_sha256,
            "dinov3_support_sha256": config.dinov3.support_sha256,
            "dinov3_local_bank_sha256": config.dinov3.local_bank_sha256,
            "preprocess_sha256": preprocess_sha256(config.preprocess),
        },
        decision_rule="fusion_local_or_global_consensus_margin_v1",
        schema_version=3,
        consensus_margin_floor=0.85,
    )
    return ClassifierPipeline(
        config=config,
        repvit=repvit,
        dino_loader=dino_loader,
        policy=DecisionPolicy(selected, provenance=provenance),
        prototype_bank=FixedPrototypeBank(),
        fusion_policy=fusion,
        fusion_provenance=replace(
            provenance,
            calibration_id="fusion_policy_v1",
            calibration_sha256="9" * 64,
        ),
        local_bank=local_bank,
    )


def _static_pipeline(*, repvit, dino_loader, local_bank) -> ClassifierPipeline:
    config = ClassifierConfig.load(Path("configs/classifier_policy.yaml"))
    static_preprocess = ClassifierPreprocessDescriptor().sha256()
    selected = _calibration(preprocess_sha256=static_preprocess)
    provenance = ModelProvenance(
        repvit_artifact_id=selected.repvit_artifact_id,
        repvit_sha256="1" * 64,
        dinov3_artifact_id=selected.dinov3_artifact_id,
        dinov3_sha256="2" * 64,
        dinov3_support_sha256="3" * 64,
        calibration_id=selected.calibration_id,
        calibration_sha256=hashlib.sha256(selected.to_json_bytes()).hexdigest(),
        preprocess_sha256=static_preprocess,
        repvit_manifest_sha256="0" * 64,
        repvit_prototype_sha256="0" * 64,
    )
    hashes = {
        "repvit_checkpoint_sha256": "1" * 64,
        "repvit_manifest_sha256": "0" * 64,
        "repvit_prototype_sha256": "0" * 64,
        "dinov3_weights_sha256": "2" * 64,
        "dinov3_support_sha256": "3" * 64,
        "dinov3_local_bank_sha256": "0" * 64,
        "preprocess_sha256": static_preprocess,
    }
    fusion = FusionPolicyArtifact(
        ranker=FusionRanker((0.0,) * 9, (1.0,) * 9, (1.0,) + (0.0,) * 8, 0.0),
        risk_calibrator=RiskCalibrator((0.0,) * 9, (1.0,) * 9, (0.0,) * 9, 0.0),
        risk_threshold=0.2,
        development_evidence_sha256="0" * 64,
        artifact_hashes=hashes,
        decision_rule="fusion_local_or_global_consensus_margin_v1",
        schema_version=3,
        consensus_margin_floor=0.85,
    )
    return ClassifierPipeline(
        config=config,
        repvit=repvit,
        dino_loader=dino_loader,
        policy=DecisionPolicy(selected, provenance=provenance),
        prototype_bank=FixedPrototypeBank(),
        fusion_policy=fusion,
        fusion_provenance=replace(
            provenance,
            calibration_id="fusion_policy_static_v1",
            calibration_sha256="9" * 64,
        ),
        local_bank=local_bank,
    )


def _calibration(**overrides: object) -> PolicyCalibration:
    values: dict[str, object] = {
        "schema_version": 2,
        "calibration_id": "policy_v1",
        "repvit_artifact_id": "repvit_m1_15plus5_v1",
        "dinov3_artifact_id": "dinov3_vits16_15plus5_v1",
        "repvit_temperature": 1.0,
        "dinov3_temperature": 1.0,
        "alpha": 0.60,
        "direct_threshold": 0.70,
        "direct_margin": 0.30,
        "direct_max_crop_disagreement": 0.30,
        "direct_max_prototype_distance": 0.20,
        "dino_threshold": 0.50,
        "fused_margin": 0.20,
        "evidence_sha256": "0" * 64,
        "repvit_checkpoint_sha256": "1" * 64,
        "repvit_manifest_sha256": "0" * 64,
        "repvit_prototype_sha256": "0" * 64,
        "dinov3_weights_sha256": "2" * 64,
        "dinov3_support_sha256": "3" * 64,
        "preprocess_sha256": "0" * 64,
    }
    values.update(overrides)
    return PolicyCalibration(**values)


def _repvit_scores(values: dict[int, float]) -> ModelScoreVector:
    remaining = 1.0 - sum(values.values())
    fill = remaining / (20 - len(values)) if len(values) < 20 else 0.0
    return ModelScoreVector(
        "repvit_m1_15plus5_v1",
        SKU_IDS,
        tuple(values.get(sku_id, fill) for sku_id in SKU_IDS),
        "probability",
    )


def _dino_scores(values: dict[int, float]) -> ModelScoreVector:
    import math

    remaining = 1.0 - sum(values.values())
    fill = remaining / (20 - len(values)) if len(values) < 20 else 0.0
    return ModelScoreVector(
        "dinov3_vits16_15plus5_v1",
        SKU_IDS,
        tuple(math.log(values.get(sku_id, fill)) for sku_id in SKU_IDS),
        "similarity",
    )


def _image() -> Image.Image:
    return Image.new("RGB", (100, 80), "goldenrod")


def _box() -> Box:
    return Box(x=10, y=10, width=40, height=20)
