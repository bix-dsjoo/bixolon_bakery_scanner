from pathlib import Path

import pytest

from bakery_scanner.classification.config import (
    ClassifierConfig,
    ClassifierRuntimeConfig,
    preprocess_sha256,
)
from bakery_scanner.classification.runtime import configure_cpu_process


def test_classifier_config_resolves_paths_and_pins_artifacts():
    config = ClassifierConfig.load(Path("configs/classifier_policy.yaml"))
    assert config.repvit.artifact_id == "repvit_m1_15plus5_v1"
    assert config.dinov3.artifact_id == "dinov3_vits16_15plus5_v1"
    assert config.dinov3.local_bank is not None
    assert config.dinov3.local_bank_sha256 == "79886645009a3109ee605afac54e4613750d4e9b03119102fb761b9660393694"
    assert config.preprocess.paddings == (0.05, 0.10, 0.15)
    assert config.runtime.device == "CUDA:0"
    assert config.runtime.precision == "FP32"
    assert preprocess_sha256(config.preprocess) == "69857c8c27bfc654207969c372f114569a8ce81f1040b27f47ec2613287ae73b"


def test_classifier_config_allows_explicit_cpu_smoke_runtime(tmp_path):
    source = Path("configs/classifier_policy.yaml").read_text(encoding="utf-8")
    path = tmp_path / "classifier_policy.yaml"
    path.write_text(source.replace("device: CUDA:0", "device: CPU"), encoding="utf-8")

    config = ClassifierConfig.load(path)

    assert config.runtime.device == "CPU"


def test_cpu_runtime_accepts_batch_compile_options():
    runtime = ClassifierRuntimeConfig(
        device="CPU",
        precision="FP32",
        mode="batch_pytorch_compile",
        repvit_microbatch_objects=4,
        dinov3_microbatch_objects="all",
        intra_op_threads=8,
        inter_op_threads=1,
        cpu_affinity=[0, 1, 2, 3],
        compile_models=["repvit", "dinov3"],
    )

    assert runtime.repvit_microbatch_objects == 4
    assert runtime.compile_models == ("repvit", "dinov3")


@pytest.mark.parametrize("value", [0, -1, 3, 16])
def test_runtime_rejects_unsupported_microbatch_sizes(value):
    with pytest.raises(ValueError, match="microbatch"):
        ClassifierRuntimeConfig(
            device="CPU",
            precision="FP32",
            mode="batch_pytorch",
            repvit_microbatch_objects=value,
        )


@pytest.mark.parametrize(
    "overrides",
    [
        {"compile_models": ["repvit"]},
        {"mode": "batch_pytorch_compile", "device": "CUDA:0", "compile_models": ["repvit"]},
        {"mode": "batch_pytorch", "inter_op_threads": 2},
        {"mode": "batch_pytorch", "cpu_affinity": []},
        {"mode": "batch_pytorch", "cpu_affinity": [-1]},
        {"mode": "batch_pytorch", "cpu_affinity": [1, 1]},
        {"mode": "batch_pytorch", "compile_models": ["repvit", "repvit"]},
    ],
)
def test_runtime_rejects_incompatible_cpu_options(overrides):
    with pytest.raises(ValueError):
        values = {"device": "CPU", "precision": "FP32"}
        values.update(overrides)
        ClassifierRuntimeConfig(**values)


def test_cpu_process_configuration_is_idempotent_and_rejects_conflicts(monkeypatch):
    import bakery_scanner.classification.runtime as runtime_module

    calls: list[object] = []
    monkeypatch.setattr(runtime_module, "_CPU_PROCESS_CONFIGURATION", None)
    monkeypatch.setattr(runtime_module, "_get_process_affinity_mask", lambda: 0b1111)
    monkeypatch.setattr(
        runtime_module, "_set_process_affinity_mask", lambda mask: calls.append(("affinity", mask))
    )
    monkeypatch.setattr(
        runtime_module.torch, "set_num_threads", lambda count: calls.append(("intra", count))
    )
    monkeypatch.setattr(
        runtime_module.torch, "set_num_interop_threads", lambda count: calls.append(("inter", count))
    )
    configured = ClassifierRuntimeConfig(
        device="CPU",
        precision="FP32",
        mode="batch_pytorch",
        intra_op_threads=2,
        cpu_affinity=[0, 2],
    )

    configure_cpu_process(configured)
    configure_cpu_process(configured)

    assert calls == [("intra", 2), ("inter", 1), ("affinity", 0b0101)]
    with pytest.raises(RuntimeError, match="fresh worker"):
        configure_cpu_process(configured.model_copy(update={"intra_op_threads": 4}))


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
