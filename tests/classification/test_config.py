from pathlib import Path

import pytest

from bakery_scanner.classification.config import ClassifierConfig, preprocess_sha256


def test_classifier_config_resolves_paths_and_pins_artifacts():
    config = ClassifierConfig.load(Path("configs/classifier_policy.yaml"))
    assert config.repvit.artifact_id == "repvit_m1_15plus5_v1"
    assert config.dinov3.artifact_id == "dinov3_vits16_15plus5_v1"
    assert config.dinov3.local_bank is not None
    assert config.dinov3.local_bank_sha256 == "8e490f78e40601bc409952460ccd4343faa6525ea6bb4c88dedc042cf36ae0a6"
    assert config.preprocess.paddings == (0.05, 0.10, 0.15)
    assert config.runtime.device == "CUDA:0"
    assert config.runtime.precision == "FP32"
    assert preprocess_sha256(config.preprocess) == "69857c8c27bfc654207969c372f114569a8ce81f1040b27f47ec2613287ae73b"


@pytest.mark.parametrize(
    ("replacement", "message"),
    [
        ("unknown_key: true\n", "Extra inputs are not permitted"),
        ("checkpoint_sha256: bad\n", "SHA-256"),
        ("paddings: [0.10, 0.05, 0.15]\n", "in ascending order"),
        ("paddings: [0.05, 0.05, 0.15]\n", "unique"),
        ("input_size: 256\n", "224"),
        ("artifact: ../artifacts/locked_acceptance/policy.json\n", "locked acceptance"),
    ],
)
def test_classifier_config_rejects_invalid_values(tmp_path, replacement, message):
    source = Path("configs/classifier_policy.yaml").read_text(encoding="utf-8")
    key, value = replacement.split(": ", 1)
    if key == "unknown_key":
        payload = source + replacement
    else:
        payload = source.replace(f"{key}: " + _value_for_key(source, key), replacement.rstrip("\n"))
    path = tmp_path / "classifier_policy.yaml"
    path.write_text(payload, encoding="utf-8")
    with pytest.raises(ValueError, match=message):
        ClassifierConfig.load(path)


def _value_for_key(payload: str, key: str) -> str:
    for line in payload.splitlines():
        if line.lstrip().startswith(f"{key}: "):
            return line.split(": ", 1)[1]
    raise AssertionError(f"missing {key}")
