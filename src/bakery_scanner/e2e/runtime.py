"""Detector-to-SKU runtime composition with fail-closed assurance handling."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from bakery_scanner.contracts import Box, BreadProposal
from bakery_scanner.detectors.proposal_graph import build_proposal_components
from bakery_scanner.verifier.assurance import (
    AssurancePolicy,
    AssuranceRunner,
    ResolutionOutcome,
    resolve_component,
    run_assurance_cascade,
)

from .contracts import FinalObject


class DetectorRunner(Protocol):
    def predict(self, image_id: int, image: object) -> tuple[BreadProposal, ...]: ...


class SkuClassifier(Protocol):
    def infer(self, image: object, box: Box) -> object: ...


@dataclass(frozen=True, slots=True)
class E2EInference:
    image_id: int
    final_objects: tuple[FinalObject, ...]
    convnext_invocations: int
    dino_invocations: int = 0

    def __post_init__(self) -> None:
        if type(self.image_id) is not int or self.image_id <= 0:
            raise ValueError("image_id must be a positive integer")
        object.__setattr__(self, "final_objects", tuple(self.final_objects))
        if any(not isinstance(item, FinalObject) for item in self.final_objects):
            raise ValueError("final_objects must contain FinalObject values")
        if type(self.dino_invocations) is not int or self.dino_invocations < 0:
            raise ValueError("dino_invocations must be a non-negative integer")


class E2EPipeline:
    """Compose detector, conditional assurance, resolver, and SKU classifier."""

    def __init__(
        self,
        detector: DetectorRunner,
        mobile_assurance: AssuranceRunner,
        convnext_assurance: AssuranceRunner,
        classifier: SkuClassifier,
        *,
        assurance_policy: AssurancePolicy | None = None,
    ) -> None:
        self.detector = detector
        self.mobile_assurance = mobile_assurance
        self.convnext_assurance = convnext_assurance
        self.classifier = classifier
        self.assurance_policy = assurance_policy or AssurancePolicy()

    def infer(self, image_id: int, image: object) -> E2EInference:
        proposals = tuple(self.detector.predict(image_id, image))
        if any(proposal.image_id != image_id for proposal in proposals):
            raise ValueError("detector proposals must belong to the requested image")
        cascade = run_assurance_cascade(
            self.mobile_assurance,
            self.convnext_assurance,
            proposals,
            image,
            policy=self.assurance_policy,
        )
        predictions = {prediction.proposal: prediction for prediction in cascade.predictions}
        final: list[FinalObject] = []
        dino_invocations = 0
        for component in build_proposal_components(proposals):
            for resolved in resolve_component(
                component,
                tuple(predictions[proposal] for proposal in component.members),
                self.assurance_policy,
            ):
                if resolved.outcome is ResolutionOutcome.UNKNOWN:
                    final.append(FinalObject(resolved.box, None, resolved.confidence, "assurance_unknown", ()))
                else:
                    decision = self.classifier.infer(image, resolved.box)
                    final.append(_final_from_classifier(decision))
                    if getattr(getattr(decision, "timings", None), "dinov3_ms", 0.0) > 0.0:
                        dino_invocations += 1
        return E2EInference(
            image_id,
            tuple(sorted(final, key=lambda row: (row.box.y, row.box.x, row.box.height, row.box.width, row.sku_id or 0))),
            cascade.convnext_invocations,
            dino_invocations,
        )


def _final_from_classifier(decision: object) -> FinalObject:
    sku_id = getattr(decision, "sku_id", None)
    confidence = getattr(decision, "confidence", None)
    box = getattr(decision, "box", None)
    decision_path = getattr(decision, "decision_path", None)
    path = getattr(decision_path, "value", decision_path)
    if sku_id is not None:
        return FinalObject(box, sku_id, confidence, path, ())
    top3 = tuple(getattr(candidate, "sku_id") for candidate in getattr(decision, "top3", ()))
    return FinalObject(box, None, confidence, path, top3)
