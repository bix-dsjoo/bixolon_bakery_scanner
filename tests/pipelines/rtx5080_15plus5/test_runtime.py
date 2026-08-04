from __future__ import annotations

from dataclasses import dataclass

import pytest

from bakery_scanner.classification.trt import (
    DinoBatchEvidence,
    GpuCrop,
    GpuCropPair,
    RepVitBatchEvidence,
)
from bakery_scanner.contracts import Box, BreadProposal
from bakery_scanner.detection.completeness import (
    CaptureQuality,
    CompletenessPolicy,
    ForegroundEvidence,
)
from bakery_scanner.detection.rfdetr_trt import CanonicalGpuFrame
from bakery_scanner.pipelines.rtx5080_15plus5.contracts import (
    CANONICAL_SKUS,
    ObjectProvenance,
    RetakeReason,
    ScanProvenance,
    ScanState,
)
from bakery_scanner.pipelines.rtx5080_15plus5.runtime import (
    DirectGateDecision,
    FusionGateDecision,
    Rtx5080Pipeline,
    RuntimeInferenceError,
    ScanContext,
)


H = "a" * 64


@dataclass
class Tensor:
    shape: tuple[int, ...]
    dtype: str = "float16"


class Stream:
    def __init__(self):
        self.syncs = 0

    def synchronize(self):
        self.syncs += 1


class Timer:
    def __init__(self):
        self.values = {}

    def measure(self, name, stream, fn):
        value = fn()
        self.values[name] = self.values.get(name, 0.0) + 1.0
        return value

    def duration_ms(self, name):
        return self.values.get(name, 0.0)


class Decoder:
    def __init__(self):
        self.calls = 0

    def decode(self, encoded, *, stream):
        self.calls += 1
        return CanonicalGpuFrame(
            200, 100, 6, Tensor((100, 200, 3), "uint8"), "exif_visual_rgb_v1"
        )


def boxes(count):
    return tuple(
        BreadProposal(
            1, "rfdetr_l_bread_gpu_fp16_v1", 0.9, Box(5 + i * 12, 20, 10, 10), 200, 100
        )
        for i in range(count)
    )


class Detector:
    def __init__(self, count, fail=False):
        self.count, self.fail = count, fail

    def detect(self, frame):
        if self.fail:
            raise RuntimeError("CUDA OOM")
        return boxes(self.count)


class SceneJob:
    def resolve(self, proposals):
        return ForegroundEvidence(0, 1, (), (), (), 0), CaptureQuality(10, 0.5, 0)


class SceneAnalyzer:
    def __init__(self):
        self.frames = []

    def start(self, frame, tray_roi, *, stream):
        self.frames.append(frame.device_rgb)
        return SceneJob()


class Cropper:
    def __init__(self):
        self.frames = []

    def build_pairs(self, frame, proposals, *, stream):
        self.frames.append(frame.device_rgb)
        return tuple(
            GpuCropPair(
                GpuCrop(Tensor((3, 224, 224)), i), GpuCrop(Tensor((3, 224, 224)), i), i
            )
            for i in range(1, len(proposals) + 1)
        )


class Repvit:
    def __init__(self):
        self.counts = []

    def score_pairs(self, pairs):
        self.counts.append(len(pairs))
        return tuple(
            RepVitBatchEvidence(
                (0.9,) + (0.1 / 19,) * 19,
                (0.9,) + (0.1 / 19,) * 19,
                pair.object_order,
            )
            for pair in pairs
        )


class Dino:
    def __init__(self, fail=False):
        self.orders = []
        self.fail = fail

    def score_rejections(self, crops):
        self.orders.append(tuple(c.object_order for c in crops))
        if self.fail:
            raise RuntimeError("chunk failed")
        return tuple(
            DinoBatchEvidence(
                (0.9,) + (0.1 / 19,) * 19,
                (2, 1, 3),
                (0.9, 0.08, 0.02),
                10,
                0.5,
                crop.object_order,
            )
            for crop in crops
        )


class Direct:
    immutable = True

    def __init__(self, reject=()):
        self.reject = set(reject)

    def decide(self, evidence, *, object_order):
        if object_order in self.reject:
            return None
        return DirectGateDecision(1, 0.95, ((1, 0.95), (2, 0.03), (3, 0.02)))


class Fusion:
    immutable = True
    consensus_margin_floor = 0.85

    def decide(self, repvit, dino, *, object_order):
        return (
            FusionGateDecision(None, None, 0.5, ((1, 0.7), (2, 0.2), (3, 0.1)))
            if object_order == 2
            else FusionGateDecision(2, 0.9, 0.84, ((2, 0.9), (1, 0.06), (3, 0.04)))
        )


POLICY = CompletenessPolicy(0.1, 0.9, 0, 1, (0, 1), 0.2, 0.2)
OBJ_PROV = ObjectProvenance(
    "det", H, "rep", H, "dino", H, "fusion", H, "rtx5080_trt_fp16_static7_v1"
)
SCAN_PROV = ScanProvenance(
    "rtx5080_15plus5_single_frame_v1", "rtx5080_trt_fp16_static7_v1", H, {"detector": H}
)


def runtime(count, *, reject=(), detector_fail=False, dino_fail=False):
    decoder, analyzer, cropper = Decoder(), SceneAnalyzer(), Cropper()
    pipeline = Rtx5080Pipeline(
        decoder=decoder,
        detector=Detector(count, detector_fail),
        scene_analyzer=analyzer,
        cropper=cropper,
        repvit=Repvit(),
        dino=Dino(dino_fail),
        direct_policy=Direct(reject),
        fusion_policy=Fusion(),
        completeness_policy=POLICY,
        tray_roi=(0, 0, 200, 100),
        detector_stream=Stream(),
        completeness_stream=Stream(),
        timer=Timer(),
        object_provenance=OBJ_PROV,
        scan_provenance=SCAN_PROV,
    )
    return pipeline, decoder, analyzer, cropper


@pytest.mark.parametrize("count", [1, 2, 8, 15])
def test_pipeline_accepts_every_positive_count_and_preserves_original_order(count):
    pipeline, decoder, analyzer, cropper = runtime(count)
    result = pipeline.infer(b"jpeg", ScanContext("scan", "chain", 1))
    assert result.state is ScanState.ACCEPTED
    assert result.object_total == count
    assert tuple(item.location.object_order for item in result.objects) == tuple(
        range(1, count + 1)
    )
    assert decoder.calls == 1
    assert analyzer.frames[0] is cropper.frames[0]


def test_zero_targets_returns_no_target_retake_without_classification():
    pipeline, *_ = runtime(0)
    result = pipeline.infer(b"jpeg", ScanContext("scan", "chain", 1))
    assert result.state is ScanState.NEEDS_RETAKE
    assert result.objects == ()
    assert result.reasons == (RetakeReason.NO_TARGET_DETECTED,)
    assert pipeline.repvit.counts == []


def test_dino_runs_only_for_direct_rejections_and_unknown_remains_separate():
    pipeline, *_ = runtime(3, reject=(2, 3))
    result = pipeline.infer(b"jpeg", ScanContext("scan", "chain", 1))
    assert pipeline.dino.orders == [(2, 3)]
    assert result.unknown_total == 1
    assert result.sku_totals == {1: 1, 2: 1}
    assert result.objects[1].sku_name == "Unknown"
    assert result.objects[2].sku_name == CANONICAL_SKUS[2]


@pytest.mark.parametrize("failure", ["detector", "dino"])
def test_any_engine_failure_aborts_whole_scan_without_partial_result(failure):
    pipeline, *_ = runtime(
        8,
        reject=(1, 2, 3, 4, 5, 6, 7, 8),
        detector_fail=failure == "detector",
        dino_fail=failure == "dino",
    )
    with pytest.raises(RuntimeInferenceError, match="aborted") as error:
        pipeline.infer(b"jpeg", ScanContext("scan", "chain", 1))
    assert error.value.partial_objects == ()


def test_needs_retake_never_exposes_final_objects():
    pipeline, *_ = runtime(1)
    pipeline.scene_analyzer = type(
        "BadScene",
        (),
        {
            "start": lambda self, frame, tray_roi, stream: type(
                "Job",
                (),
                {
                    "resolve": lambda self, proposals: (
                        ForegroundEvidence(0.5, 0.5, ((0, 0, 10, 10),), (), (), 0.5),
                        CaptureQuality(10, 0.5, 0),
                    )
                },
            )()
        },
    )()
    result = pipeline.infer(b"jpeg", ScanContext("scan", "chain", 2))
    assert result.state is ScanState.NEEDS_RETAKE and result.objects == ()


def test_runtime_rejects_a_direct_policy_approval_that_disagrees_with_both_crops():
    pipeline, *_ = runtime(1)
    pipeline.direct_policy = type(
        "UnsafeDirect",
        (),
        {
            "immutable": True,
            "decide": lambda self, evidence, object_order: DirectGateDecision(
                2, 0.95, ((2, 0.95), (1, 0.03), (3, 0.02))
            ),
        },
    )()
    with pytest.raises(RuntimeInferenceError, match="aborted"):
        pipeline.infer(b"jpeg", ScanContext("scan", "chain", 1))


def test_runtime_rejects_fusion_sku_without_local_or_global_consensus():
    pipeline, *_ = runtime(1, reject=(1,))
    pipeline.fusion_policy = type(
        "UnsafeFusion",
        (),
        {
            "immutable": True,
            "consensus_margin_floor": 0.85,
            "decide": lambda self, repvit, dino, object_order: FusionGateDecision(
                3, 0.9, 0.84, ((3, 0.9), (1, 0.06), (2, 0.04))
            ),
        },
    )()
    with pytest.raises(RuntimeInferenceError, match="aborted"):
        pipeline.infer(b"jpeg", ScanContext("scan", "chain", 1))
