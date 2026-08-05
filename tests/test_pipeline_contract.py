from pathlib import Path


def test_pipeline_contract_names_mobile_first_and_conditional_convnext():
    text = Path("AGENTS.md").read_text(encoding="utf-8")
    assert "MobileNetV4" in text and "conditional ConvNeXt-Tiny" in text


def test_rtx5080_candidate_is_documented_as_external_and_production_unverified():
    text = Path("docs/architecture/pipelines.md").read_text(encoding="utf-8")
    assert "RTX 5080 15+5 candidate" in text
    assert "production-unverified" in text
    assert "scans with 1-2" in text and "8+ objects remain valid" in text
