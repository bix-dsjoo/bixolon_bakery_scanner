import pytest
import torch
from PIL import Image

from bakery_scanner.contracts import Box, BreadProposal, VerifierState
from bakery_scanner.verifier.assurance import (
    AssuranceBackend,
    BoxAssurancePrediction,
    TorchAssuranceRunner,
    build_assurance_model,
)


def _proposal() -> BreadProposal:
    return BreadProposal(1, "dfine_n_640", 0.8, Box(10, 20, 30, 40), 100, 100)


def test_assurance_normalizes_state_probabilities_and_clips_partial_correction():
    prediction = BoxAssurancePrediction(
        proposal=_proposal(),
        backend=AssuranceBackend.MOBILENETV4,
        state_probabilities=(0.0, 2.0, 2.0, 0.0),
        quality=0.8,
        box_delta=(-20.0, -20.0, 100.0, 100.0),
    )

    assert prediction.state_probabilities == pytest.approx((0.0, 0.5, 0.5, 0.0))
    assert prediction.predicted_state is VerifierState.EXACTLY_ONE
    assert prediction.corrected_box == Box(0, 0, 100, 100)


def test_assurance_rejects_non_finite_delta():
    with pytest.raises(ValueError, match="delta"):
        BoxAssurancePrediction(
            proposal=_proposal(),
            backend=AssuranceBackend.MOBILENETV4,
            state_probabilities=(0.0, 1.0, 0.0, 0.0),
            quality=0.8,
            box_delta=(0.0, 0.0, float("nan"), 0.0),
        )


def test_model_has_state_quality_and_delta_heads():
    model = build_assurance_model(AssuranceBackend.MOBILENETV4, pretrained=False)

    state, quality, delta = model(torch.zeros(2, 3, 224, 224))

    assert state.shape == (2, 4)
    assert quality.shape == (2,)
    assert delta.shape == (2, 4)


def test_torch_runner_converts_batched_heads_to_assurance_predictions():
    class Model(torch.nn.Module):
        def forward(self, images):
            return (
                torch.tensor([[0.0, 3.0, 0.0, 0.0]], device=images.device),
                torch.tensor([0.0], device=images.device),
                torch.tensor([[0.1, 0.2, 0.3, 0.4]], device=images.device),
            )

    runner = TorchAssuranceRunner(Model(), AssuranceBackend.MOBILENETV4, device="cpu")
    predictions = runner.predict((_proposal(),), Image.new("RGB", (100, 100), "white"))

    assert predictions[0].predicted_state is VerifierState.EXACTLY_ONE
    assert predictions[0].quality == pytest.approx(0.5)
    assert predictions[0].box_delta == pytest.approx((0.1, 0.2, 0.3, 0.4))
