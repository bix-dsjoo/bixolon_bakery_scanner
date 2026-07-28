from types import SimpleNamespace

from bakery_scanner.contracts import Box
from bakery_scanner.e2e.contracts import FinalObject, SkuGroundTruth
from bakery_scanner.e2e.runner import execute_e2e_evaluation


def test_execute_e2e_evaluation_measures_and_evaluates_all_images(monkeypatch):
    monkeypatch.setattr("bakery_scanner.e2e.runner._require_rtx5080", lambda: None)
    monkeypatch.setattr("bakery_scanner.e2e.runner.time.perf_counter", iter(range(10_000)).__next__)
    labels = {
        image_id: (SkuGroundTruth(image_id, Box(0, 0, 10, 10), 6),)
        for image_id in range(1, 300)
    }

    class Pipeline:
        def __init__(self):
            self.calls = 0

        def infer(self, image_id, image):
            self.calls += 1
            return SimpleNamespace(
                image_id=image_id,
                final_objects=(FinalObject(Box(0, 0, 10, 10), 6, 0.9, "repvit_direct", ()),),
                convnext_invocations=0,
                dino_invocations=0,
            )

    pipeline = Pipeline()
    execution = execute_e2e_evaluation(
        pipeline,
        labels,
        lambda image_id: object(),
        warmup_count=10,
        synchronize=lambda: None,
    )

    assert pipeline.calls == 309
    assert execution.benchmark.image_count == 299
    assert execution.evaluation.iou50.top1_accuracy == 1.0
    assert execution.evaluation.iou75.false_positive_count == 0
    assert execution.evaluation.latency.mean_ms == execution.benchmark.total_mean_ms
