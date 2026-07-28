from bakery_scanner.contracts import Box, BreadProposal, VerifierState
from bakery_scanner.detectors.proposal_graph import build_proposal_components
from bakery_scanner.verifier.assurance import (
    AssuranceBackend,
    AssurancePolicy,
    BoxAssurancePrediction,
    ResolutionOutcome,
    resolve_component,
    run_assurance_cascade,
)


def _proposal(x: float, width: float = 30.0) -> BreadProposal:
    return BreadProposal(1, "dfine_n_640", 0.8, Box(x, 10, width, 30), 120, 100)


def _prediction(proposal: BreadProposal, state: VerifierState, quality: float = 0.9) -> BoxAssurancePrediction:
    values = [0.0] * 4
    values[int(state)] = 1.0
    return BoxAssurancePrediction(proposal, AssuranceBackend.MOBILENETV4, tuple(values), quality, (0, 0, 0, 0))


def test_overlap_does_not_delete_either_candidate():
    left, right = _proposal(10), _proposal(30)

    components = build_proposal_components((left, right))
    outcome = resolve_component(components[0], (_prediction(left, VerifierState.EXACTLY_ONE), _prediction(right, VerifierState.EXACTLY_ONE)), AssurancePolicy())

    assert components[0].members == (left, right)
    assert len(outcome) == 2
    assert all(item.outcome is ResolutionOutcome.RESOLVED for item in outcome)


def test_unresolved_multiple_becomes_unknown_not_merged():
    proposal = _proposal(10, 60)
    component = build_proposal_components((proposal,))[0]

    outcome = resolve_component(component, (_prediction(proposal, VerifierState.MULTIPLE),), AssurancePolicy())

    assert len(outcome) == 1
    assert outcome[0].outcome is ResolutionOutcome.UNKNOWN


def test_confident_mobile_skips_convnext():
    proposal = _proposal(10)

    class Mobile:
        def predict(self, candidates, image):
            return (_prediction(candidates[0], VerifierState.EXACTLY_ONE),)

    class ConvNext:
        calls = 0

        def predict(self, candidates, image):
            self.calls += 1
            return tuple(_prediction(candidate, VerifierState.EXACTLY_ONE) for candidate in candidates)

    convnext = ConvNext()
    result = run_assurance_cascade(Mobile(), convnext, (proposal,), object())

    assert result.convnext_invocations == 0
    assert result.predictions[0].backend is AssuranceBackend.MOBILENETV4
