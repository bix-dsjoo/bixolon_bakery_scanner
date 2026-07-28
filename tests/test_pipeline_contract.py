from pathlib import Path


def test_pipeline_contract_names_mobile_first_and_conditional_convnext():
    text = Path("AGENTS.md").read_text(encoding="utf-8")
    assert "MobileNetV4" in text and "conditional ConvNeXt-Tiny" in text
