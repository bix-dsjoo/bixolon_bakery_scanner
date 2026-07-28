from types import SimpleNamespace

from bakery_scanner.classification.contracts import DecisionPath
from bakery_scanner.contracts import Box, BreadProposal, VerifierState
from bakery_scanner.e2e.runtime import E2EPipeline, MobileOnlyE2EPipeline
from bakery_scanner.verifier.assurance import AssuranceBackend, BoxAssurancePrediction


def _proposal() -> BreadProposal:
    return BreadProposal(1, "dfine_n_640", 0.9, Box(10, 10, 30, 30), 100, 100)


def _prediction(proposal: BreadProposal, state: VerifierState) -> BoxAssurancePrediction:
    values = [0.0] * 4
    values[int(state)] = 1.0
    return BoxAssurancePrediction(proposal, AssuranceBackend.MOBILENETV4, tuple(values), 0.9, (0, 0, 0, 0))


def test_pipeline_classifies_only_resolved_boxes():
    trace: list[str] = []
    proposal = _proposal()

    class Detector:
        def predict(self, image_id, image):
            trace.append("detector")
            return (proposal,)

    class Mobile:
        def predict(self, candidates, image):
            trace.append("mobile")
            return (_prediction(candidates[0], VerifierState.EXACTLY_ONE),)

    class ConvNext:
        def predict(self, candidates, image):
            trace.append("convnext")
            return tuple(_prediction(candidate, VerifierState.EXACTLY_ONE) for candidate in candidates)

    class Classifier:
        def infer(self, image, box):
            trace.append("classifier")
            return SimpleNamespace(sku_id=6, confidence=0.9, box=box, decision_path=DecisionPath.REPVIT_DIRECT, top3=())

    output = E2EPipeline(Detector(), Mobile(), ConvNext(), Classifier()).infer(1, object())

    assert trace == ["detector", "mobile", "classifier"]
    assert output.final_objects[0].sku_id == 6


def test_multiple_assurance_result_becomes_unknown_without_classifier_call():
    proposal = _proposal()

    class Detector:
        def predict(self, image_id, image):
            return (proposal,)

    class Mobile:
        def predict(self, candidates, image):
            return (_prediction(candidates[0], VerifierState.MULTIPLE),)

    class ConvNext:
        def predict(self, candidates, image):
            return (_prediction(candidates[0], VerifierState.MULTIPLE),)

    class Classifier:
        calls = 0

        def infer(self, image, box):
            self.calls += 1
            raise AssertionError("unknown assurance component must not be classified")

    classifier = Classifier()
    output = E2EPipeline(Detector(), Mobile(), ConvNext(), classifier).infer(1, object())

    assert classifier.calls == 0
    assert output.final_objects[0].sku_id is None
    assert output.final_objects[0].decision_path == "assurance_unknown"
    assert output.final_objects[0].top3 == ()


def test_mobile_only_pipeline_returns_unknown_when_convnext_recheck_would_be_required():
    proposal = _proposal()

    class Detector:
        def predict(self, image_id, image):
            return (proposal,)

    class Mobile:
        def predict(self, candidates, image):
            values = (0.0, 1.0, 0.0, 0.0)
            return (BoxAssurancePrediction(candidates[0], AssuranceBackend.MOBILENETV4, values, 0.1, (0, 0, 0, 0)),)

    class Classifier:
        calls = 0

        def infer(self, image, box):
            self.calls += 1
            raise AssertionError("recheck-required CPU candidate must not be classified")

    classifier = Classifier()
    output = MobileOnlyE2EPipeline(Detector(), Mobile(), classifier).infer(1, object())

    assert classifier.calls == 0
    assert output.convnext_invocations == 0
    assert output.final_objects[0].sku_id is None
    assert output.final_objects[0].decision_path == "assurance_unknown"


def test_mobile_only_pipeline_records_live_stage_timing_mapping(monkeypatch):
    """Each live E2E stage contributes its measured duration to the public mapping."""
    proposal = _proposal()
    clock = iter((0.0, 0.0, 0.001, 0.001, 0.003, 0.003, 0.006, 0.010))
    monkeypatch.setattr("bakery_scanner.e2e.runtime.time.perf_counter", lambda: next(clock))

    class Detector:
        def predict(self, image_id, image):
            return (proposal,)

    class Mobile:
        def predict(self, candidates, image):
            return (_prediction(candidates[0], VerifierState.EXACTLY_ONE),)

    class Classifier:
        def infer(self, image, box):
            return SimpleNamespace(
                sku_id=6,
                confidence=0.9,
                box=box,
                decision_path=DecisionPath.REPVIT_DIRECT,
                top3=(),
                timings=SimpleNamespace(repvit_ms=7.0, dinov3_ms=11.0),
            )

    output = MobileOnlyE2EPipeline(Detector(), Mobile(), Classifier()).infer(1, object())

    assert output.stage_timings_ms == {
        "detector": 1.0,
        "mobile_assurance": 2.0,
        "resolver": 3.0,
        "repvit": 7.0,
        "dinov3": 11.0,
        "total": 10.0,
    }
