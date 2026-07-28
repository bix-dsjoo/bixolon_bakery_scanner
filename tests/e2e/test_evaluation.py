import json

from bakery_scanner.contracts import Box
from bakery_scanner.e2e.contracts import FinalObject, SkuGroundTruth
from bakery_scanner.e2e.evaluation import evaluation_payload, write_evaluation_report
from bakery_scanner.e2e.metrics import E2EImageResult, evaluate_run


def test_canonical_evaluation_payload_contains_requested_metrics(tmp_path):
    report = evaluate_run(
        {1: (SkuGroundTruth(1, Box(0, 0, 10, 10), 6),)},
        (E2EImageResult(1, (FinalObject(Box(0, 0, 10, 10), None, 0.6, "unknown_top3", (6, 3, 2)),), 25.0),),
    )

    payload = evaluation_payload(report, scope="grouped_oof_development_only")
    path = write_evaluation_report(tmp_path / "evaluation.json", payload)

    persisted = json.loads(path.read_text(encoding="utf-8"))
    assert persisted["scope"] == "grouped_oof_development_only"
    assert persisted["metrics"]["iou_0.50"]["unknown_count"] == 1
    assert persisted["metrics"]["iou_0.50"]["top3_accuracy"] == 1.0
    assert persisted["latency_ms"]["mean"] == 25.0
