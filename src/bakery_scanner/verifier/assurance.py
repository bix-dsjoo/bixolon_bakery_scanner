"""Fail-closed box-assurance contracts and component resolution."""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Protocol

import numpy as np
import torch
from PIL import Image
from torch import nn

from bakery_scanner.contracts import Box, BreadProposal, VerifierState
from bakery_scanner.detectors.proposal_graph import box_iou

if TYPE_CHECKING:
    from bakery_scanner.detectors.proposal_graph import ProposalComponent


class AssuranceBackend(str, Enum):
    MOBILENETV4 = "mobilenetv4"
    CONVNEXT_TINY = "convnext_tiny"


class ResolutionOutcome(str, Enum):
    RESOLVED = "resolved"
    UNKNOWN = "unknown"


class AssuranceRunner(Protocol):
    def predict(self, candidates: tuple[BreadProposal, ...], image: object) -> tuple["BoxAssurancePrediction", ...]: ...


@dataclass(frozen=True, slots=True)
class BoxAssurancePrediction:
    proposal: BreadProposal
    backend: AssuranceBackend
    state_probabilities: tuple[float, float, float, float]
    quality: float
    box_delta: tuple[float, float, float, float]

    def __post_init__(self) -> None:
        if not isinstance(self.proposal, BreadProposal) or not isinstance(self.backend, AssuranceBackend):
            raise ValueError("proposal and backend must be valid assurance inputs")
        values = tuple(float(value) for value in self.state_probabilities)
        if len(values) != 4 or not all(math.isfinite(value) and value >= 0.0 for value in values) or sum(values) <= 0.0:
            raise ValueError("state probabilities must be four finite non-negative values with positive sum")
        total = sum(values)
        object.__setattr__(self, "state_probabilities", tuple(value / total for value in values))
        quality = float(self.quality)
        if not math.isfinite(quality) or not 0.0 <= quality <= 1.0:
            raise ValueError("quality must be finite in [0, 1]")
        object.__setattr__(self, "quality", quality)
        delta = tuple(float(value) for value in self.box_delta)
        if len(delta) != 4 or not all(math.isfinite(value) for value in delta):
            raise ValueError("delta must contain four finite values")
        object.__setattr__(self, "box_delta", delta)

    @property
    def predicted_state(self) -> VerifierState:
        return VerifierState(max(range(4), key=self.state_probabilities.__getitem__))

    @property
    def state_margin(self) -> float:
        ranked = sorted(self.state_probabilities, reverse=True)
        return ranked[0] - ranked[1]

    @property
    def corrected_box(self) -> Box:
        base = self.proposal.box
        dx, dy, dw, dh = self.box_delta
        raw_left = base.x + dx * base.width
        raw_top = base.y + dy * base.height
        raw_right = base.x + base.width + dw * base.width
        raw_bottom = base.y + base.height + dh * base.height
        left = min(max(raw_left, 0.0), float(self.proposal.image_width - 1))
        top = min(max(raw_top, 0.0), float(self.proposal.image_height - 1))
        right = min(max(raw_right, left + 1e-6), float(self.proposal.image_width))
        bottom = min(max(raw_bottom, top + 1e-6), float(self.proposal.image_height))
        return Box(left, top, right - left, bottom - top)


@dataclass(frozen=True, slots=True)
class AssurancePolicy:
    minimum_exact_quality: float = 0.5
    minimum_partial_quality: float = 0.7
    duplicate_iou: float = 0.85

    def __post_init__(self) -> None:
        for value in (self.minimum_exact_quality, self.minimum_partial_quality, self.duplicate_iou):
            if not math.isfinite(value) or not 0.0 <= value <= 1.0:
                raise ValueError("assurance policy thresholds must be finite in [0, 1]")


class AssuranceModel(nn.Module):
    """Shared three-head architecture for first-pass and recheck assurance."""

    def __init__(self, backend: AssuranceBackend, *, pretrained: bool = False) -> None:
        super().__init__()
        import timm

        name = "mobilenetv4_conv_small" if backend is AssuranceBackend.MOBILENETV4 else "convnext_tiny"
        self.backbone = timm.create_model(name, pretrained=pretrained, num_classes=0, global_pool="avg")
        # Some timm MobileNetV4 variants expose a pre-pooling ``num_features``
        # that differs from their actual pooled forward output.
        self.state_head = nn.LazyLinear(4)
        self.quality_head = nn.LazyLinear(1)
        self.delta_head = nn.LazyLinear(4)

    def forward(self, image: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        features = self.backbone(image)
        return self.state_head(features), self.quality_head(features).squeeze(1), self.delta_head(features)


def build_assurance_model(backend: AssuranceBackend, *, pretrained: bool = False) -> AssuranceModel:
    if not isinstance(backend, AssuranceBackend):
        raise ValueError("backend must be an AssuranceBackend")
    return AssuranceModel(backend, pretrained=pretrained)


class TorchAssuranceRunner:
    """Batch a three-head assurance model over detector candidates."""

    def __init__(
        self,
        model: nn.Module,
        backend: AssuranceBackend,
        *,
        device: str = "cuda:0",
        batch_size: int = 64,
    ) -> None:
        if not isinstance(backend, AssuranceBackend):
            raise ValueError("backend must be an AssuranceBackend")
        if batch_size <= 0:
            raise ValueError("batch_size must be positive")
        self.model = model.to(device).eval()
        self.backend = backend
        self.device = torch.device(device)
        self.batch_size = batch_size

    def predict(
        self,
        candidates: tuple[BreadProposal, ...],
        image: object,
    ) -> tuple[BoxAssurancePrediction, ...]:
        if not candidates:
            return ()
        frame = image.image if hasattr(image, "image") and isinstance(getattr(image, "image"), Image.Image) else image
        if not isinstance(frame, Image.Image):
            raise TypeError("assurance runner requires a PIL or CanonicalImage frame")
        crops = tuple(_assurance_crop(frame, candidate) for candidate in candidates)
        rows: list[BoxAssurancePrediction] = []
        with torch.inference_mode():
            for start in range(0, len(candidates), self.batch_size):
                batch = torch.stack(crops[start : start + self.batch_size]).to(self.device)
                state_logits, quality_logits, deltas = self.model(batch)
                if state_logits.shape != (len(batch), 4) or quality_logits.shape != (len(batch),) or deltas.shape != (len(batch), 4):
                    raise ValueError("assurance model must return [N,4], [N], and [N,4] heads")
                probabilities = torch.softmax(state_logits, dim=1).cpu()
                qualities = torch.sigmoid(quality_logits).cpu()
                corrections = deltas.cpu()
                for offset, candidate in enumerate(candidates[start : start + self.batch_size]):
                    rows.append(
                        BoxAssurancePrediction(
                            candidate,
                            self.backend,
                            tuple(float(value) for value in probabilities[offset].tolist()),
                            float(qualities[offset]),
                            tuple(float(value) for value in corrections[offset].tolist()),
                        )
                    )
        return tuple(rows)


def _assurance_crop(frame: Image.Image, candidate: BreadProposal) -> torch.Tensor:
    if frame.size != (candidate.image_width, candidate.image_height):
        raise ValueError("assurance frame dimensions must match detector candidate coordinates")
    box = candidate.box
    left, top = math.floor(box.x), math.floor(box.y)
    right, bottom = math.ceil(box.x + box.width), math.ceil(box.y + box.height)
    crop = frame.convert("RGB").crop((left, top, right, bottom)).resize((224, 224), Image.Resampling.BICUBIC)
    values = torch.from_numpy(np.asarray(crop, dtype=np.float32).copy()).permute(2, 0, 1) / 255.0
    mean = torch.tensor((0.485, 0.456, 0.406), dtype=values.dtype).view(3, 1, 1)
    std = torch.tensor((0.229, 0.224, 0.225), dtype=values.dtype).view(3, 1, 1)
    return (values - mean) / std


@dataclass(frozen=True, slots=True)
class AssuranceCascadeResult:
    predictions: tuple["BoxAssurancePrediction", ...]
    convnext_invocations: int

    def __post_init__(self) -> None:
        if self.convnext_invocations not in (0, 1):
            raise ValueError("convnext_invocations must be zero or one per image")
        object.__setattr__(self, "predictions", tuple(self.predictions))


def run_assurance_cascade(
    mobile: AssuranceRunner,
    convnext: AssuranceRunner,
    candidates: tuple[BreadProposal, ...],
    image: object,
    *,
    policy: AssurancePolicy | None = None,
    minimum_state_margin: float = 0.15,
) -> AssuranceCascadeResult:
    """Run ConvNeXt once only for ambiguous or graph-conflicting candidates."""
    chosen_policy = policy or AssurancePolicy()
    first = tuple(mobile.predict(candidates, image))
    recheck = select_convnext_rechecks(
        candidates,
        first,
        policy=chosen_policy,
        minimum_state_margin=minimum_state_margin,
    )
    if not recheck:
        return AssuranceCascadeResult(first, 0)
    second = tuple(convnext.predict(recheck, image))
    _require_prediction_coverage(recheck, second)
    replacements = {prediction.proposal: prediction for prediction in second}
    return AssuranceCascadeResult(tuple(replacements.get(prediction.proposal, prediction) for prediction in first), 1)


def select_convnext_rechecks(
    candidates: tuple[BreadProposal, ...],
    predictions: tuple[BoxAssurancePrediction, ...],
    *,
    policy: AssurancePolicy,
    minimum_state_margin: float = 0.15,
) -> tuple[BreadProposal, ...]:
    """Return candidates requiring conditional ConvNeXt-Tiny assurance."""
    if not math.isfinite(minimum_state_margin) or not 0.0 <= minimum_state_margin <= 1.0:
        raise ValueError("minimum_state_margin must be finite in [0, 1]")
    _require_prediction_coverage(candidates, predictions)
    from bakery_scanner.detectors.proposal_graph import build_proposal_components

    conflicts = {
        proposal
        for component in build_proposal_components(candidates)
        if len(component.members) > 1
        for proposal in component.members
    }
    return tuple(
        prediction.proposal
        for prediction in predictions
        if prediction.proposal in conflicts
        or prediction.predicted_state in (VerifierState.PARTIAL, VerifierState.MULTIPLE)
        or prediction.quality < policy.minimum_exact_quality
        or prediction.state_margin < minimum_state_margin
    )


@dataclass(frozen=True, slots=True)
class ResolvedAssuranceObject:
    outcome: ResolutionOutcome
    box: Box
    confidence: float
    sources: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.outcome, ResolutionOutcome) or not isinstance(self.box, Box):
            raise ValueError("resolution outcome and box must be valid")
        confidence = float(self.confidence)
        if not math.isfinite(confidence) or not 0.0 <= confidence <= 1.0:
            raise ValueError("resolution confidence must be finite in [0, 1]")
        object.__setattr__(self, "confidence", confidence)
        if not self.sources or tuple(sorted(set(self.sources))) != self.sources:
            raise ValueError("resolution sources must be unique canonical names")


def resolve_component(
    component: ProposalComponent,
    predictions: tuple[BoxAssurancePrediction, ...],
    policy: AssurancePolicy,
) -> tuple[ResolvedAssuranceObject, ...]:
    """Resolve one relation component without hard NMS or silent merging."""
    expected = set(component.members)
    by_proposal = {prediction.proposal: prediction for prediction in predictions}
    if set(by_proposal) != expected or len(by_proposal) != len(predictions):
        raise ValueError("assurance predictions must cover each component member exactly once")
    selected: list[BoxAssurancePrediction] = []
    has_multiple = False
    for proposal in component.members:
        prediction = by_proposal[proposal]
        state = prediction.predicted_state
        if state is VerifierState.EXACTLY_ONE and prediction.quality >= policy.minimum_exact_quality:
            selected.append(prediction)
        elif state is VerifierState.PARTIAL and prediction.quality >= policy.minimum_partial_quality:
            selected.append(prediction)
        elif state is VerifierState.MULTIPLE:
            has_multiple = True
    resolved = _deduplicate(selected, policy.duplicate_iou)
    if resolved:
        return tuple(
            ResolvedAssuranceObject(
                ResolutionOutcome.RESOLVED,
                prediction.corrected_box if prediction.predicted_state is VerifierState.PARTIAL else prediction.proposal.box,
                prediction.quality,
                (prediction.proposal.source,),
            )
            for prediction in resolved
        )
    if has_multiple:
        return (ResolvedAssuranceObject(ResolutionOutcome.UNKNOWN, _component_box(component), max(prediction.quality for prediction in predictions), tuple(sorted({prediction.proposal.source for prediction in predictions}))),)
    return ()


def _deduplicate(predictions: list[BoxAssurancePrediction], duplicate_iou: float) -> tuple[BoxAssurancePrediction, ...]:
    retained: list[BoxAssurancePrediction] = []
    for prediction in sorted(predictions, key=lambda row: (-row.quality, -row.proposal.score, row.proposal.box.y, row.proposal.box.x)):
        candidate_box = prediction.corrected_box if prediction.predicted_state is VerifierState.PARTIAL else prediction.proposal.box
        if all(box_iou(candidate_box, row.corrected_box if row.predicted_state is VerifierState.PARTIAL else row.proposal.box) < duplicate_iou for row in retained):
            retained.append(prediction)
    return tuple(sorted(retained, key=lambda row: (row.proposal.box.y, row.proposal.box.x, row.proposal.box.height, row.proposal.box.width)))


def _require_prediction_coverage(
    candidates: tuple[BreadProposal, ...],
    predictions: tuple[BoxAssurancePrediction, ...],
) -> None:
    if len({row.proposal for row in predictions}) != len(predictions) or {row.proposal for row in predictions} != set(candidates):
        raise ValueError("assurance runner must produce exactly one prediction per candidate")


def _component_box(component: ProposalComponent) -> Box:
    left = min(row.box.x for row in component.members)
    top = min(row.box.y for row in component.members)
    right = max(row.box.x + row.box.width for row in component.members)
    bottom = max(row.box.y + row.box.height for row in component.members)
    return Box(left, top, right - left, bottom - top)
