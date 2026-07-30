from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path

import pytest
from PIL import Image

from bakery_scanner.classification.contracts import (
    ClassificationDecision,
    DecisionPath,
    ModelProvenance,
    SkuCandidate,
    StageTimings,
)
from bakery_scanner.classification.runtime import (
    BatchInferenceResult,
    BatchStageTimings,
    BenchmarkPreflightEvidence,
    SerialStageTimings,
)
from bakery_scanner.contracts import Box, BreadProposal
from bakery_scanner.data.preprocess import CanonicalImage
from bakery_scanner.e2e.cpu_benchmark_protocol import (
    ErrorMessage,
    PassResult,
    PassResultMessage,
    PrepareCommand,
    ReadyMessage,
    RunPassCommand,
    ShutdownCommand,
    StoppedMessage,
    WarmupStageCounts,
    WorkerEnvironment,
    WorkerSpec,
)
from bakery_scanner.e2e.cpu_benchmark_worker import (
    BenchmarkWorker,
    BenchmarkWorkerFailure,
    WorkerDependencies,
    worker_process_main,
)
from bakery_scanner.e2e.cpu_dataset import CpuEvaluationSample, CpuEvaluationTarget
from bakery_scanner.e2e.cpu_regression import (
    ImageRegressionRecord,
    ObjectOutcome,
    ObjectRecord,
    build_image_regression_record,
)


_ROOT = Path(__file__).resolve().parents[2]
_HASH = "a" * 64


class StepClock:
    def __init__(self, *, step: float = 0.02) -> None:
        self.value = 0.0
        self.step = step

    def __call__(self) -> float:
        value = self.value
        self.value += self.step
        return value


class RecordingDetector:
    def __init__(
        self,
        samples: tuple[CpuEvaluationSample, ...],
        *,
        score_threshold: float,
    ) -> None:
        self._samples = {sample.source_image_id: sample for sample in samples}
        self._score_threshold = score_threshold
        self.calls: list[int] = []

    def predict(self, image_id: int, image: Image.Image) -> tuple[BreadProposal, ...]:
        self.calls.append(image_id)
        sample = self._samples[image_id]
        width, height = image.size
        return tuple(
            BreadProposal(
                image_id=image_id,
                source="rfdetr_large_bakery_v1",
                score=0.9,
                box=target.box,
                image_width=width,
                image_height=height,
            )
            for target in sample.targets
        )


class RecordingClassifier:
    def __init__(self, mode: str, timing_sink) -> None:
        self.mode = mode
        self.timing_sink = timing_sink
        self.infer_calls = 0
        self.infer_many_calls = 0
        self.preflight_calls = 0

    def preflight_benchmark(
        self,
        frame: CanonicalImage,
        boxes: tuple[Box, ...],
        *,
        repvit_max_objects: int,
        dino_max_objects: int,
    ) -> BenchmarkPreflightEvidence:
        self.preflight_calls += 1
        assert repvit_max_objects >= 1
        assert dino_max_objects >= 1
        return BenchmarkPreflightEvidence(len(boxes), 1, 1)

    def infer(self, frame: CanonicalImage, box: Box) -> ClassificationDecision:
        self.infer_calls += 1
        self.timing_sink(SerialStageTimings(0.1, 0.2, 0.0, 0.0, 0.3, False))
        return _decision(box, unknown=False)

    def infer_many(
        self,
        frame: CanonicalImage,
        boxes: tuple[Box, ...],
        *,
        repvit_max_objects: int,
        dino_max_objects: int,
    ) -> BatchInferenceResult:
        self.infer_many_calls += 1
        decisions = tuple(
            _decision(box, unknown=index == 0) for index, box in enumerate(boxes)
        )
        return BatchInferenceResult(
            decisions,
            BatchStageTimings(1.0, 2.0, 3.0, 4.0, 10.0),
            min(1, len(decisions)),
        )


@dataclass
class RecordingWorkerDependencies:
    mode: str = "serial_reference"
    detector_threshold: float = 0.5
    artifact_hash: str = _HASH

    def __post_init__(self) -> None:
        self.all_samples = _samples()
        self.measured_samples = self.all_samples[3:9]
        self.configure_calls = 0
        self.detector_loads = 0
        self.classifier_loads = 0
        self.loaded_threshold: float | None = None
        self.runtime = None
        self.clock = StepClock()
        self.detector: RecordingDetector | None = None
        self.classifier: RecordingClassifier | None = None

    def dependencies(self) -> WorkerDependencies:
        return WorkerDependencies(
            load_samples=lambda root: self.all_samples,
            select_samples=lambda samples, **kwargs: self.measured_samples,
            detector_metadata=lambda root: {
                "artifact_id": "rfdetr_large_bakery_v1",
                "score_threshold": 0.5,
                "calibration_score_threshold": 0.5,
                "manifest_sha256": "b" * 64,
                "checkpoint_sha256": "c" * 64,
                "calibration_sha256": "d" * 64,
                "artifact_hashes": {"fixture_sha256": self.artifact_hash},
            },
            load_detector=self._load_detector,
            load_classifier=self._load_classifier,
            load_canonical_image=lambda path: _frame(),
            build_regression_record=_regression_record,
            configure_cpu_process=self._configure,
            read_environment=_environment,
            clock=self.clock,
        )

    def _configure(self, runtime) -> None:
        self.configure_calls += 1
        self.runtime = runtime

    def _load_detector(self, checkpoint: Path, threshold: float) -> RecordingDetector:
        self.detector_loads += 1
        self.loaded_threshold = threshold
        self.detector = RecordingDetector(
            self.all_samples, score_threshold=self.detector_threshold
        )
        return self.detector

    def _load_classifier(self, config: Path, runtime, timing_sink) -> RecordingClassifier:
        self.classifier_loads += 1
        self.classifier = RecordingClassifier(runtime.mode, timing_sink)
        return self.classifier


def _samples() -> tuple[CpuEvaluationSample, ...]:
    samples = []
    profiles = ("E", "M", "H")
    for index in range(299):
        target_count = 5 if index < 210 else 4
        targets = tuple(
            CpuEvaluationTarget(
                annotation_id=index * 10 + offset + 1,
                sku_id=(offset % 20) + 1,
                box=Box(2.0 + offset * 10.0, 2.0, 8.0, 8.0),
            )
            for offset in range(target_count)
        )
        samples.append(
            CpuEvaluationSample(
                key=f"source/image-{index:03d}.jpg",
                source="source",
                source_image_id=index + 1,
                image_path=_ROOT / f"image-{index:03d}.jpg",
                profile=profiles[index % 3],
                targets=targets,
            )
        )
    assert sum(len(sample.targets) for sample in samples) == 1406
    return tuple(samples)


def _frame() -> CanonicalImage:
    image = Image.new("RGB", (100, 100))
    return CanonicalImage(image, image.size, image.size, 1)


def _environment() -> WorkerEnvironment:
    return WorkerEnvironment(
        python_version="3.12",
        pytorch_version="2.7",
        torchvision_version="0.22",
        numpy_version="2.2",
        os_name="nt",
        os_version="test",
        logical_cpu_count=4,
        inherited_affinity=(0, 1, 2, 3),
        filesystem_encoding="utf-8",
        default_encoding="utf-8",
        utf8_mode=1,
        gc_enabled=True,
    )


def _provenance() -> ModelProvenance:
    return ModelProvenance(
        repvit_artifact_id="repvit",
        repvit_sha256=_HASH,
        dinov3_artifact_id="dino",
        dinov3_sha256=_HASH,
        dinov3_support_sha256=_HASH,
        calibration_id="calibration",
        calibration_sha256=_HASH,
    )


def _decision(box: Box, *, unknown: bool) -> ClassificationDecision:
    if unknown:
        return ClassificationDecision(
            "unknown",
            None,
            0.4,
            box,
            DecisionPath.UNKNOWN_TOP3,
            (
                SkuCandidate(1, 1, 0.4),
                SkuCandidate(2, 2, 0.3),
                SkuCandidate(3, 3, 0.2),
            ),
            _provenance(),
            StageTimings(1.0, 1.0, 2.0),
            "fusion_rejected",
        )
    sku_id = round((box.x - 2.0) / 10.0) + 1
    return ClassificationDecision(
        "sku",
        sku_id,
        0.9,
        box,
        DecisionPath.REPVIT_DIRECT,
        (),
        _provenance(),
        StageTimings(1.0, 0.0, 1.0),
    )


def _regression_record(
    sample: CpuEvaluationSample,
    proposals: tuple[BreadProposal, ...],
    decisions: tuple[ClassificationDecision, ...],
) -> ImageRegressionRecord:
    records = []
    for index, (target, decision) in enumerate(
        zip(sample.targets, decisions, strict=True)
    ):
        unknown = decision.decision == "unknown"
        records.append(
            ObjectRecord(
                sample_key=sample.key,
                annotation_id=target.annotation_id,
                expected_sku=target.sku_id,
                outcome=(
                    (
                        ObjectOutcome.TOP3_CANDIDATE
                        if target.sku_id
                        in {candidate.sku_id for candidate in decision.top3}
                        else ObjectOutcome.CANDIDATE_OUT_UNKNOWN
                    )
                    if unknown
                    else ObjectOutcome.CORRECT
                ),
                predicted_sku=None if unknown else decision.sku_id,
                top3_sku_ids=(
                    tuple(candidate.sku_id for candidate in decision.top3)
                    if unknown
                    else ()
                ),
                matched_proposal_index=index,
                iou=1.0,
            )
        )
    return ImageRegressionRecord(sample.key, tuple(records), ())


def _worker_spec(mode: str = "serial_reference", *, artifact_hash: str = _HASH) -> WorkerSpec:
    overrides = () if mode == "serial_reference" else (("mode", mode),)
    return WorkerSpec(
        role="reference" if mode == "serial_reference" else "candidate",
        mode=mode,
        package_root=_ROOT,
        classifier_config=_ROOT / "configs" / "cpu_rfdetr_classifier_policy.yaml",
        sample_profile="batch2_e3_m3_h3",
        runtime_overrides=overrides,
        expected_artifact_hashes=(("fixture_sha256", artifact_hash),),
    )


def _worker(
    mode: str = "serial_reference",
    **dependency_options,
) -> tuple[BenchmarkWorker, RecordingWorkerDependencies]:
    recorder = RecordingWorkerDependencies(mode=mode, **dependency_options)
    return BenchmarkWorker(_worker_spec(mode), dependencies=recorder.dependencies()), recorder


def test_prepare_loads_once_applies_runtime_once_and_warms_two_e_m_h_repetitions():
    worker, recorder = _worker()

    metadata = worker.prepare()

    assert recorder.configure_calls == 1
    assert recorder.detector_loads == 1
    assert recorder.classifier_loads == 1
    assert tuple(item.profile for item in metadata.warmup.images) == (
        "E",
        "M",
        "H",
        "E",
        "M",
        "H",
    )
    assert all(
        item.stage_counts
        == WarmupStageCounts(1, 1, item.stage_counts.repvit, 1, 1)
        for item in metadata.warmup.images
    )
    assert recorder.loaded_threshold == 0.5
    assert metadata.resolved_runtime.intra_op_threads == 4
    assert metadata.resolved_runtime.cpu_affinity == (0, 1, 2, 3)
    assert all(
        value is not None
        for field in metadata.environment.__dataclass_fields__
        for value in (getattr(metadata.environment, field),)
    )
    assert worker.prepare() is metadata


def test_serial_pass_uses_requested_order_excludes_warmup_and_sums_observations():
    worker, recorder = _worker()
    metadata = worker.prepare()
    keys = tuple(sample.key for sample in recorder.measured_samples)

    result = worker.run_pass(RunPassCommand(pass_index=2, image_keys=keys))

    assert result.pass_index == 2
    assert tuple(row.key for row in result.rows) == keys
    assert not set(row.key for row in result.rows) & {
        warmup.key for warmup in metadata.warmup.images
    }
    assert all(row.total_ms >= row.canonical_ms + row.detector_ms for row in result.rows)
    assert recorder.classifier.infer_calls == sum(
        len(sample.targets) for sample in recorder.measured_samples
    )
    assert recorder.classifier.infer_many_calls == 0
    assert all(row.crop_ms == pytest.approx(row.object_count * 0.1) for row in result.rows)
    assert all(row.dino_object_count == 0 for row in result.rows)
    assert all(
        row.registered_count + row.unknown_count == len(row.records)
        for row in result.rows
    )


def test_batch_pass_calls_infer_many_once_per_image_and_uses_dino_count():
    worker, recorder = _worker("batch_pytorch")
    worker.prepare()
    keys = tuple(sample.key for sample in recorder.measured_samples)

    result = worker.run_pass(RunPassCommand(pass_index=0, image_keys=keys))

    assert recorder.classifier.infer_calls == 0
    assert recorder.classifier.infer_many_calls == len(recorder.measured_samples)
    assert all(row.dino_object_count == 1 for row in result.rows)
    assert all(row.unknown_count == 1 for row in result.rows)
    assert all(row.registered_count == row.object_count - 1 for row in result.rows)


def test_prepare_rejects_manifest_threshold_mismatch():
    worker, _ = _worker(detector_threshold=0.1)

    with pytest.raises(BenchmarkWorkerFailure, match="threshold"):
        worker.prepare()


def test_prepare_rejects_functioning_detector_without_applied_threshold():
    recorder = RecordingWorkerDependencies()
    dependencies = recorder.dependencies()

    class DetectorWithoutThreshold:
        def __init__(self) -> None:
            self.delegate = RecordingDetector(
                recorder.all_samples,
                score_threshold=0.5,
            )

        def predict(self, image_id: int, image: Image.Image):
            return self.delegate.predict(image_id, image)

    worker = BenchmarkWorker(
        _worker_spec(),
        dependencies=replace(
            dependencies,
            load_detector=lambda checkpoint, threshold: DetectorWithoutThreshold(),
        ),
    )

    with pytest.raises(BenchmarkWorkerFailure, match="threshold"):
        worker.prepare()


def test_prepare_rejects_artifact_hash_mismatch():
    recorder = RecordingWorkerDependencies(artifact_hash="b" * 64)
    worker = BenchmarkWorker(_worker_spec(), dependencies=recorder.dependencies())

    with pytest.raises(BenchmarkWorkerFailure, match="artifact"):
        worker.prepare()


@pytest.mark.parametrize(
    "keys",
    [
        ("missing",),
        ("source/image-004.jpg", "source/image-003.jpg"),
    ],
)
def test_run_pass_rejects_missing_or_reordered_image_keys(keys):
    worker, _ = _worker()
    worker.prepare()

    with pytest.raises(BenchmarkWorkerFailure, match="image key"):
        worker.run_pass(RunPassCommand(pass_index=0, image_keys=keys))


def test_protocol_rejects_duplicate_image_keys_before_worker_dispatch():
    with pytest.raises(ValueError, match="image_keys"):
        RunPassCommand(pass_index=0, image_keys=("a", "a"))


def test_run_pass_rejects_regression_record_with_changed_expected_sku():
    recorder = RecordingWorkerDependencies()
    dependencies = recorder.dependencies()

    def changed_expected_sku(sample, proposals, decisions):
        record = _regression_record(sample, proposals, decisions)
        first = record.objects[0]
        changed = replace(
            first,
            expected_sku=2 if first.expected_sku == 1 else 1,
        )
        return replace(record, objects=(changed, *record.objects[1:]))

    worker = BenchmarkWorker(
        _worker_spec(),
        dependencies=replace(
            dependencies,
            build_regression_record=changed_expected_sku,
        ),
    )
    worker.prepare()
    keys = tuple(sample.key for sample in recorder.measured_samples)

    with pytest.raises(BenchmarkWorkerFailure, match="regression record"):
        worker.run_pass(RunPassCommand(pass_index=0, image_keys=keys))


def test_run_pass_preserves_one_missed_gt_and_one_false_positive_proposal():
    recorder = RecordingWorkerDependencies()
    dependencies = recorder.dependencies()
    measured_image_id = recorder.measured_samples[0].source_image_id

    class MissAndExtraDetector(RecordingDetector):
        def predict(
            self, image_id: int, image: Image.Image
        ) -> tuple[BreadProposal, ...]:
            proposals = list(super().predict(image_id, image))
            if image_id == measured_image_id:
                proposals.pop()
                proposals.append(
                    BreadProposal(
                        image_id=image_id,
                        source="rfdetr_large_bakery_v1",
                        score=0.8,
                        box=Box(80.0, 80.0, 8.0, 8.0),
                        image_width=image.width,
                        image_height=image.height,
                    )
                )
            return tuple(proposals)

    detector = MissAndExtraDetector(
        recorder.all_samples,
        score_threshold=0.5,
    )
    worker = BenchmarkWorker(
        _worker_spec(),
        dependencies=replace(
            dependencies,
            load_detector=lambda checkpoint, threshold: detector,
            build_regression_record=build_image_regression_record,
        ),
    )
    worker.prepare()
    keys = tuple(sample.key for sample in recorder.measured_samples)

    result = worker.run_pass(RunPassCommand(pass_index=0, image_keys=keys))

    row = result.rows[0]
    assert row.object_count == 5
    assert len(row.records) == 5
    assert sum(
        record.outcome is ObjectOutcome.MISSED for record in row.records
    ) == 1
    assert row.false_positive_proposal_indices == (4,)
    assert row.registered_count + row.unknown_count == 5


def test_run_pass_rejects_total_that_cannot_cover_sequential_stage_timings():
    recorder = RecordingWorkerDependencies()
    recorder.clock = StepClock(step=0.001)
    worker = BenchmarkWorker(
        _worker_spec(),
        dependencies=recorder.dependencies(),
    )
    worker.prepare()
    keys = tuple(sample.key for sample in recorder.measured_samples)

    with pytest.raises(BenchmarkWorkerFailure, match="total timing"):
        worker.run_pass(RunPassCommand(pass_index=0, image_keys=keys))


@pytest.mark.parametrize(
    "mutation",
    [
        "top_level_key",
        "false_positive_overlap",
        "wrong_iou",
        "swapped_indexes",
        "below_threshold_indexes",
    ],
)
def test_run_pass_rejects_malformed_regression_record_mutations(mutation):
    recorder = RecordingWorkerDependencies()
    dependencies = recorder.dependencies()

    def malformed_record(sample, proposals, decisions):
        record = build_image_regression_record(sample, proposals, decisions)
        if mutation == "top_level_key":
            object.__setattr__(record, "sample_key", "other/image.jpg")
            return record
        if mutation == "false_positive_overlap":
            return replace(record, false_positive_proposal_indices=(0,))
        objects = list(record.objects)
        if mutation == "wrong_iou":
            objects[0] = replace(objects[0], iou=0.5)
        else:
            first, second = objects[:2]
            objects[0] = replace(
                first,
                outcome=ObjectOutcome.MISCLASSIFIED,
                predicted_sku=decisions[1].sku_id,
                matched_proposal_index=1,
                iou=0.5,
            )
            objects[1] = replace(
                second,
                outcome=ObjectOutcome.MISCLASSIFIED,
                predicted_sku=decisions[0].sku_id,
                matched_proposal_index=0,
                iou=0.5,
            )
            if mutation == "below_threshold_indexes":
                object.__setattr__(objects[0], "iou", 0.0)
                object.__setattr__(objects[1], "iou", 0.0)
        return replace(record, objects=tuple(objects))

    worker = BenchmarkWorker(
        _worker_spec(),
        dependencies=replace(
            dependencies,
            build_regression_record=malformed_record,
        ),
    )
    worker.prepare()
    keys = tuple(sample.key for sample in recorder.measured_samples)

    with pytest.raises(BenchmarkWorkerFailure, match="regression"):
        worker.run_pass(RunPassCommand(pass_index=0, image_keys=keys))


class RecordingConnection:
    def __init__(self, commands) -> None:
        self.commands = list(commands)
        self.sent = []
        self.closed = False

    def recv(self):
        return self.commands.pop(0)

    def send(self, message) -> None:
        self.sent.append(message)

    def close(self) -> None:
        self.closed = True


def test_worker_process_target_runs_prepare_pass_and_shutdown_protocol(monkeypatch):
    spec = _worker_spec()
    metadata = _worker()[0].prepare()
    command = RunPassCommand(pass_index=0, image_keys=("source/image-003.jpg",))
    result = PassResult(spec.role, metadata.pid, command.pass_index, ())
    construction: list[WorkerSpec] = []

    class ProcessWorker:
        def __init__(self, received_spec: WorkerSpec) -> None:
            construction.append(received_spec)

        def prepare(self):
            return metadata

        def run_pass(self, received_command):
            assert received_command is command
            return result

    connection = RecordingConnection(
        (PrepareCommand(spec), command, ShutdownCommand())
    )
    monkeypatch.setattr(
        "bakery_scanner.e2e.cpu_benchmark_worker.BenchmarkWorker",
        ProcessWorker,
    )

    worker_process_main(connection)

    assert construction == [spec]
    assert isinstance(connection.sent[0], ReadyMessage)
    assert connection.sent[0].metadata is metadata
    assert connection.sent[1] == PassResultMessage(result)
    assert connection.sent[2] == StoppedMessage(spec.role, metadata.pid)
    assert connection.closed


def test_worker_process_target_requires_prepare_before_constructing_worker(
    monkeypatch,
):
    constructions = []
    connection = RecordingConnection((ShutdownCommand(),))
    monkeypatch.setattr(
        "bakery_scanner.e2e.cpu_benchmark_worker.BenchmarkWorker",
        lambda spec: constructions.append(spec),
    )

    with pytest.raises(BenchmarkWorkerFailure, match="first command"):
        worker_process_main(connection)

    assert constructions == []
    assert isinstance(connection.sent[0], ErrorMessage)
    assert connection.sent[0].error.protocol_state.value == "created"
    assert connection.closed


def test_worker_process_target_sanitizes_exception_message(monkeypatch):
    secret = "worker-secret-that-must-not-cross-the-pipe"
    monkeypatch.setenv("BENCHMARK_TEST_SECRET", secret)
    spec = _worker_spec()
    connection = RecordingConnection((PrepareCommand(spec),))

    class FailingWorker:
        def __init__(self, received_spec: WorkerSpec) -> None:
            pass

        def prepare(self):
            raise RuntimeError(f"failed with {secret}")

    monkeypatch.setattr(
        "bakery_scanner.e2e.cpu_benchmark_worker.BenchmarkWorker",
        FailingWorker,
    )

    with pytest.raises(RuntimeError, match="failed with"):
        worker_process_main(connection)

    error = connection.sent[0].error
    assert secret not in error.message
    assert error.exception_type == "RuntimeError"
    assert error.protocol_state.value == "preparing"
    assert error.role == "reference"
    assert error.pass_index is None
