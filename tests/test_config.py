from pathlib import Path

from bakery_scanner.config import ScannerConfig


def test_config_loads_current_dataset_paths():
    config = ScannerConfig.load(Path("configs/box_system.yaml"))

    assert len(config.dataset.sources) == 3
    assert config.dataset.expected_images == 299
    assert config.dataset.expected_boxes == 1406
    assert {row.input_size for row in config.detectors.variants} == {640, 768}
    assert config.canonical_frame.width == 1152
    assert config.canonical_frame.height == 1536
    assert not hasattr(config, "camera")
    repository = Path(".").resolve()
    assert [source.images for source in config.dataset.sources] == [
        repository / "datasets" / "detection" / name / "images"
        for name in (
            "group_15class",
            "group_20class_batch01",
            "group_20class_batch02",
        )
    ]
    assert [source.annotations for source in config.dataset.sources] == [
        repository
        / "datasets"
        / "detection"
        / name
        / "annotations"
        / "instances.json"
        for name in (
            "group_15class",
            "group_20class_batch01",
            "group_20class_batch02",
        )
    ]
    assert config.artifact_root == Path("artifacts/box_system").resolve()
    assert config.runtime.device == "CUDA:0"


def test_config_resolves_paths_from_config_location(tmp_path: Path):
    config_path = tmp_path / "nested" / "scanner.yaml"
    config_path.parent.mkdir()
    config_path.write_text(
        """
seed: 1
artifact_root: artifacts
canonical_frame: {width: 10, height: 20}
dataset:
  sources:
    - {name: source, images: images, annotations: annotations.json}
  expected_images: 1
  expected_boxes: 1
  folds: 2
detectors:
  seeds: [1]
  variants:
    - {name: dfine_n_640, backend: dfine, input_size: 640, role: audit}
runtime: {device: CUDA:0, precision: FP32, proposal_limit: 30}
""".strip(),
        encoding="utf-8",
    )

    config = ScannerConfig.load(config_path)

    assert config.dataset.sources[0].images == config_path.parent / "images"
    assert config.artifact_root == config_path.parent / "artifacts"
