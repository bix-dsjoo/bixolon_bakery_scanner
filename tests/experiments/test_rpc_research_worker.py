"""Focused contracts for the external-only RPC oracle feature worker."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pytest
import torch
from PIL import Image

import bakery_scanner.experiments.rpc_research_worker as worker
from bakery_scanner.experiments.rpc_manifest import (
    RpcDatasetContract,
    RpcImage,
    RpcIndex,
    RpcObject,
    write_new_json,
)
from bakery_scanner.experiments.rpc_research_worker import (
    FeatureExample,
    FeatureProvenance,
    OracleFeatureRow,
    ResearchArtifacts,
    extract_oracle_features,
    fit_m0_head,
    score_m1,
    score_m2,
)


def test_research_artifacts_reject_wrong_dino_digest(tmp_path: Path):
    """Changing the DINO file must prevent its features from being materialized."""
    with pytest.raises(ValueError, match="DINOv3 SHA-256 mismatch"):
        ResearchArtifacts.from_paths(tmp_path / "repvit.safetensors", tmp_path / "dino.pth")


def test_oracle_feature_row_is_bound_to_source_and_box():
    """An annotation ID distinguishes separate oracle boxes in one source image."""
    row = OracleFeatureRow("val2019:7:item.jpg", 11, 7, (1.0, 2.0, 3.0, 4.0), "E")

    assert row.identity == "val2019:7:item.jpg:11"


class _RepVitFeatureFixture(torch.nn.Module):
    def forward_features(self, batch: torch.Tensor) -> torch.Tensor:
        values = torch.arange(1, 385, dtype=torch.float32, device=batch.device)
        return values.reshape(1, 384, 1, 1).expand(batch.shape[0], -1, -1, -1)


class _DinoFeatureFixture(torch.nn.Module):
    def forward_features(self, batch: torch.Tensor) -> dict[str, torch.Tensor]:
        global_values = torch.arange(384, 0, -1, dtype=torch.float32, device=batch.device)
        patch_values = torch.arange(1, 385, dtype=torch.float32, device=batch.device)
        return {
            "x_norm_clstoken": global_values.reshape(1, 384).expand(batch.shape[0], -1),
            "x_norm_patchtokens": patch_values.reshape(1, 1, 384).expand(batch.shape[0], 196, -1),
        }


def _one_image_index(tmp_path: Path) -> RpcIndex:
    source = tmp_path / "item.jpg"
    Image.new("RGB", (12, 9), (20, 30, 40)).save(source)
    source_bytes = source.read_bytes()
    contract = RpcDatasetContract(
        annotation_sha256={split: hashlib.sha256(split.encode()).hexdigest() for split in ("train2019", "val2019", "test2019")},
        image_counts={split: 1 for split in ("train2019", "val2019", "test2019")},
    )
    image = RpcImage(
        split="val2019",
        image_id=7,
        source_identity="val2019:7:item.jpg",
        source_path=source,
        byte_size=len(source_bytes),
        sha256=hashlib.sha256(source_bytes).hexdigest(),
        level="easy",
    )
    return RpcIndex(contract, (image,), (RpcObject("val2019", 11, 7, 7, (1.0, 2.0, 3.0, 4.0)),))


def _fixture_artifacts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> ResearchArtifacts:
    repvit = tmp_path / "repvit.safetensors"
    dino = tmp_path / "dino.pth"
    repvit.write_bytes(b"repvit-fixture")
    dino.write_bytes(b"dino-fixture")
    monkeypatch.setattr(worker, "_REPVIT_SHA256", hashlib.sha256(repvit.read_bytes()).hexdigest())
    monkeypatch.setattr(worker, "_DINO_SHA256", hashlib.sha256(dino.read_bytes()).hexdigest())
    return ResearchArtifacts.from_paths(repvit, dino)


def test_extract_oracle_features_records_two_globals_and_196_patches(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    """Removing a global branch or any patch row leaves an incomplete research cache."""
    monkeypatch.setattr(worker, "_load_feature_models", lambda _artifacts: (_RepVitFeatureFixture(), _DinoFeatureFixture()))
    artifacts = _fixture_artifacts(tmp_path, monkeypatch)
    monkeypatch.setattr(worker, "_RESEARCH_RUNS_ROOT", tmp_path)
    output = tmp_path / "features"

    manifest_path = extract_oracle_features(_one_image_index(tmp_path), artifacts, output)

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["rows"] == [{
        "annotation_id": 11,
        "bbox_xywh": [1.0, 2.0, 3.0, 4.0],
        "category_id": 7,
        "difficulty": "E",
        "identity": "val2019:7:item.jpg:11",
        "source_identity": "val2019:7:item.jpg",
    }]
    repvit = np.load(output / "repvit_global.float16.npy")
    dino = np.load(output / "dinov3_global.float16.npy")
    patches = np.load(output / "dinov3_patches.float16.npy")
    assert repvit.dtype == dino.dtype == patches.dtype == np.float16
    assert repvit.shape == dino.shape == (1, 384)
    assert patches.shape == (1, 196, 384)
    assert np.linalg.norm(repvit.astype(np.float32), axis=1) == pytest.approx([1.0], abs=2e-3)
    assert np.linalg.norm(dino.astype(np.float32), axis=1) == pytest.approx([1.0], abs=2e-3)
    assert manifest["execution"] == {
        "determinism": "cpu-float32-inference-mode-model-eval-v1",
        "device": "cpu",
    }
    assert manifest["preprocessing"]["input_size"] == [224, 224]
    assert len(manifest["code_sha256"]) == 64
    assert manifest["runtime"]["torch"] == torch.__version__
    with pytest.raises(FileExistsError):
        extract_oracle_features(_one_image_index(tmp_path), artifacts, output)


def test_extract_revalidates_artifacts_before_loading_models(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    """A checkpoint replaced after construction must fail before any encoder loads."""
    artifacts = _fixture_artifacts(tmp_path, monkeypatch)
    artifacts.repvit_path.write_bytes(b"substituted")
    monkeypatch.setattr(worker, "_load_feature_models", lambda _artifacts: pytest.fail("loaded stale model"))
    monkeypatch.setattr(worker, "_RESEARCH_RUNS_ROOT", tmp_path)

    with pytest.raises(ValueError, match="RepViT SHA-256 mismatch"):
        extract_oracle_features(_one_image_index(tmp_path), artifacts, tmp_path / "features")


def test_canonical_oracle_crop_transforms_orientation_six_bbox(tmp_path: Path):
    """A raw top-left COCO box becomes the top-right pixel after EXIF rotation 6."""
    source = tmp_path / "oriented.png"
    raw = Image.new("RGB", (3, 2))
    raw.putdata([
        (255, 0, 0), (0, 255, 0), (0, 0, 255),
        (0, 255, 255), (255, 0, 255), (255, 255, 0),
    ])
    exif = Image.Exif()
    exif[274] = 6
    raw.save(source, exif=exif)
    content = source.read_bytes()
    image = RpcImage(
        split="val2019", image_id=7, source_identity="val2019:7:oriented.png",
        source_path=source, byte_size=len(content), sha256=hashlib.sha256(content).hexdigest(), level="easy",
    )

    crop = worker._canonical_oracle_crop(image, (0.0, 0.0, 1.0, 1.0))

    assert crop.size == (1, 1)
    assert crop.getpixel((0, 0)) == (255, 0, 0)


def test_extract_rejects_output_outside_research_runs_root(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    """The producer itself prevents a caller from writing generated payloads into Git."""
    artifacts = _fixture_artifacts(tmp_path, monkeypatch)
    monkeypatch.setattr(worker, "_RESEARCH_RUNS_ROOT", tmp_path / "allowed")

    with pytest.raises(ValueError, match="output must be under"):
        extract_oracle_features(_one_image_index(tmp_path), artifacts, tmp_path / "outside")


def test_extract_has_no_caller_controlled_output_root(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    """A caller cannot bypass the external-research storage boundary with a keyword."""
    artifacts = _fixture_artifacts(tmp_path, monkeypatch)
    monkeypatch.setattr(worker, "_load_feature_models", lambda _artifacts: (_RepVitFeatureFixture(), _DinoFeatureFixture()))

    with pytest.raises(TypeError, match="unexpected keyword argument"):
        extract_oracle_features(
            _one_image_index(tmp_path), artifacts, tmp_path / "features", allowed_output_root=tmp_path
        )


def _support_row(
    source_identity: str,
    category_id: int,
    dino_global: tuple[float, float],
    capture_stratum: str,
) -> OracleFeatureRow:
    vector = [0.0] * 384
    vector[:2] = dino_global
    return OracleFeatureRow(
        source_identity,
        annotation_id=category_id * 100 + len(source_identity),
        category_id=category_id,
        bbox_xywh=(1.0, 2.0, 3.0, 4.0),
        difficulty="E",
        source_byte_size=123,
        source_sha256=hashlib.sha256(source_identity.encode("utf-8")).hexdigest(),
        dino_global=tuple(vector),
        capture_stratum=capture_stratum,
        feature_array_sha256="f" * 64,
    )


def test_random_support_prefixes_are_seeded_and_nested():
    """Resampling a larger shot condition would break the frozen-prefix contract."""
    rows = (
        _support_row("rnd-a.jpg", 7, (1.0, 0.0), "camera-a"),
        _support_row("rnd-b.jpg", 7, (0.0, 1.0), "camera-b"),
        _support_row("rnd-c.jpg", 7, (-1.0, 0.0), "camera-c"),
        _support_row("rnd-d.jpg", 7, (0.0, -1.0), "camera-d"),
        _support_row("rnd-e.jpg", 7, (0.5, 0.5), "camera-e"),
    )

    bank = worker.materialize_support_bank(rows, selector="rnd", seed=101, maximum_shots=5)

    assert bank.prefix(1) == bank.prefix(5)[:1]
    assert bank.prefix(3) == bank.prefix(5)[:3]
    assert bank.feature_array_sha256 == "f" * 64
    assert bank == worker.materialize_support_bank(rows, selector="rnd", seed=101, maximum_shots=5)


def test_diverse_one_shot_uses_dino_global_centroid_medoid():
    """Replacing DINO globals with another feature branch selects the wrong first support."""
    rows = (
        _support_row("left.jpg", 7, (1.0, 0.0), "camera-a"),
        _support_row("top.jpg", 7, (0.0, 1.0), "camera-b"),
        _support_row("centroid-medoid.jpg", 7, (0.8, 0.2), "camera-c"),
    )

    bank = worker.materialize_support_bank(rows, selector="div", seed=101, maximum_shots=1)

    assert bank.prefix(1)[0].source_identity == "centroid-medoid.jpg"


def test_support_bank_rejects_duplicate_sources_and_classes_without_full_prefixes():
    """A duplicate source or undersupplied class must not yield a nominal support bank."""
    duplicate = _support_row("same.jpg", 7, (1.0, 0.0), "camera-a")
    with pytest.raises(ValueError, match="duplicate source identity"):
        worker.materialize_support_bank((duplicate, duplicate), selector="rnd", seed=101, maximum_shots=1)

    with pytest.raises(ValueError, match="insufficient support candidates"):
        worker.materialize_support_bank(
            (
                _support_row("class-seven-a.jpg", 7, (1.0, 0.0), "camera-a"),
                _support_row("class-seven-b.jpg", 7, (0.0, 1.0), "camera-b"),
                _support_row("class-eight-a.jpg", 8, (1.0, 0.0), "camera-a"),
            ),
            selector="rnd",
            seed=101,
            maximum_shots=2,
        )


def _task1_feature_manifest(tmp_path: Path) -> Path:
    """Build a canonical Task 1-shaped cache without adding generated payloads to Git."""
    feature_root = tmp_path / "features"
    feature_root.mkdir()
    names = (
        "roll_camera1-top.jpg",
        "roll_camera2-top.jpg",
        "roll_camera1-bottom.jpg",
        "roll_camera2-bottom.jpg",
    )
    globals_array = np.zeros((4, 384), dtype=np.float16)
    globals_array[:, 0] = (1.0, 0.0, -1.0, 0.5)
    globals_array[:, 1] = (0.0, 1.0, 0.0, 0.5)
    array_path = feature_root / "dinov3_global.float16.npy"
    np.save(array_path, globals_array)
    array_bytes = array_path.read_bytes()
    rows = [
        {
            "identity": f"train2019:{index + 1}:{name}:{100 + index}",
            "source_identity": f"train2019:{index + 1}:{name}",
            "annotation_id": 100 + index,
            "category_id": 7,
            "bbox_xywh": [1.0, 2.0, 3.0, 4.0],
            "difficulty": "E",
        }
        for index, name in enumerate(names)
    ]
    manifest = {
        "schema_version": 1,
        "kind": "rpc-research-oracle-features",
        "canonical_frame": "exif_visual_rgb_v1",
        "feature_dtype": "float16",
        "execution": {"device": "cpu", "determinism": "cpu-float32-inference-mode-model-eval-v1"},
        "preprocessing": {},
        "code_sha256": "a" * 64,
        "runtime": {},
        "artifacts": {},
        "arrays": {
            "repvit_global": {"file": "repvit_global.float16.npy", "byte_size": 1, "sha256": "b" * 64, "shape": [4, 384]},
            "dinov3_global": {
                "file": array_path.name,
                "byte_size": len(array_bytes),
                "sha256": hashlib.sha256(array_bytes).hexdigest(),
                "shape": [4, 384],
            },
            "dinov3_patches": {"file": "dinov3_patches.float16.npy", "byte_size": 1, "sha256": "c" * 64, "shape": [4, 196, 384]},
        },
        "images": [
            {
                "source_identity": row["source_identity"],
                "source_byte_size": 100 + index,
                "source_sha256": hashlib.sha256(row["source_identity"].encode()).hexdigest(),
            }
            for index, row in enumerate(rows)
        ],
        "rows": rows,
    }
    manifest_path = feature_root / "manifest.json"
    write_new_json(manifest_path, manifest)
    return manifest_path


def test_support_bank_consumes_verified_task1_dino_global_artifact(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    """An ad-hoc row payload cannot replace the hash-verified Task 1 feature cache."""
    monkeypatch.setattr(worker, "_RESEARCH_RUNS_ROOT", tmp_path)
    manifest_path = _task1_feature_manifest(tmp_path)

    bank = worker.materialize_support_bank_from_feature_manifest(
        manifest_path, selector="rnd", seed=101, maximum_shots=2
    )

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert bank.feature_array_sha256 == manifest["arrays"]["dinov3_global"]["sha256"]
    assert bank.prefix(1)[0].source_sha256 == manifest["images"][0]["source_sha256"]
    with (manifest_path.parent / "dinov3_global.float16.npy").open("ab") as handle:
        handle.write(b"forged")
    with pytest.raises(ValueError, match="DINO global feature array SHA-256 mismatch"):
        worker.materialize_support_bank_from_feature_manifest(
            manifest_path, selector="rnd", seed=101, maximum_shots=2
        )


def test_support_prefixes_are_globally_nested_for_multiple_classes():
    """A class-grouped flattening would make one-shot output differ from a larger prefix."""
    rows = (
        _support_row("seven-a.jpg", 7, (1.0, 0.0), "camera-a"),
        _support_row("seven-b.jpg", 7, (0.0, 1.0), "camera-b"),
        _support_row("eight-a.jpg", 8, (1.0, 0.0), "camera-a"),
        _support_row("eight-b.jpg", 8, (0.0, 1.0), "camera-b"),
    )
    bank = worker.materialize_support_bank(rows, selector="rnd", seed=101, maximum_shots=2)

    assert bank.prefix(1) == bank.prefix(2)[:2]


def test_diverse_multi_seed_banks_are_distinct_or_rejected():
    """Seeds that only change metadata must not masquerade as independent DIV draws."""
    rows = tuple(
        _support_row(f"same-stratum-{index}.jpg", 7, (1.0, 0.0), "camera-a")
        for index in range(8)
    )

    banks = worker.materialize_support_banks(rows, selector="div", seeds=(5, 10), maximum_shots=3)

    assert banks[0].ordered_support_identities != banks[1].ordered_support_identities
    with pytest.raises(ValueError, match="same ordered support draw"):
        worker.materialize_support_banks(
            (_support_row("only.jpg", 7, (1.0, 0.0), "camera-a"),),
            selector="div",
            seeds=(5, 10),
            maximum_shots=1,
        )


def test_support_selection_rejects_non_384_dino_global_vectors():
    """Allowing any feature width would decouple support selection from Task 1 DINO globals."""
    with pytest.raises(ValueError, match="DINO global feature must have dimension 384"):
        OracleFeatureRow(
            "wrong-width.jpg", 11, 7, (1.0, 2.0, 3.0, 4.0), "E",
            source_byte_size=123,
            source_sha256="a" * 64,
            dino_global=tuple([1.0] * 383),
            capture_stratum="camera-a",
            feature_array_sha256="f" * 64,
        )


def _scoring_vector(first: float, second: float) -> tuple[float, ...]:
    return (first, second, *([0.0] * 382))


def _scoring_example(
    category_id: int,
    source: str,
    *,
    repvit: tuple[float, float] = (0.0, 1.0),
    dino: tuple[float, float] = (0.0, 1.0),
) -> FeatureExample:
    digest = hashlib.sha256(source.encode("utf-8")).hexdigest()
    provenance = FeatureProvenance(
        source_identity=source,
        annotation_id=category_id * 1000 + len(source),
        source_sha256=digest,
        repvit_global_array_sha256=hashlib.sha256(f"repvit:{source}".encode()).hexdigest(),
        dinov3_global_array_sha256=hashlib.sha256(f"dino-global:{source}".encode()).hexdigest(),
        dinov3_patches_array_sha256=hashlib.sha256(f"dino-local:{source}".encode()).hexdigest(),
    )
    dino_vector = _scoring_vector(*dino)
    return FeatureExample(
        category_id=category_id,
        provenance=provenance,
        repvit_global=_scoring_vector(*repvit),
        dinov3_global=dino_vector,
        dinov3_patches=(dino_vector,),
    )


def _complete_scoring_supports(*, duplicate_seven: bool = False) -> dict[int, tuple[FeatureExample, ...]]:
    supports = {
        category_id: (_scoring_example(category_id, f"support-{category_id}"),)
        for category_id in range(1, 201)
    }
    supports[7] = (_scoring_example(7, "support-seven-a", repvit=(3.0, 0.0), dino=(3.0, 0.0)),)
    if duplicate_seven:
        supports[7] = (
            supports[7][0],
            _scoring_example(7, "support-seven-b", repvit=(3.0, 0.0), dino=(3.0, 0.0)),
        )
    return supports


def _scoring_query(*, source: str = "query") -> FeatureExample:
    return _scoring_example(7, source, repvit=(1.0, 0.0), dino=(1.0, 0.0))


def test_m1_scores_normalized_class_means():
    """Skipping per-support normalization makes a high-magnitude support win incorrectly."""
    supports = _complete_scoring_supports()
    supports[7] = (
        _scoring_example(7, "support-seven-a", repvit=(3.0, 0.0), dino=(3.0, 0.0)),
        _scoring_example(7, "support-seven-b", repvit=(1.0, 0.0), dino=(1.0, 0.0)),
    )

    prediction = score_m1(supports, supports, _scoring_query())

    assert prediction.repvit_top1 == 7
    assert prediction.dinov3_global_top1 == 7
    assert prediction.dinov3_local_top1 == 7


def test_m2_normalizes_each_class_cache_count():
    """Summing a class cache would let duplicated identical exemplars inflate its score."""
    query = _scoring_query()

    one_exemplar = score_m2(_complete_scoring_supports(), _complete_scoring_supports(), query)
    duplicated_exemplars = score_m2(
        _complete_scoring_supports(duplicate_seven=True),
        _complete_scoring_supports(duplicate_seven=True),
        query,
    )

    assert one_exemplar.dinov3_global_scores[6] == duplicated_exemplars.dinov3_global_scores[6]
    assert one_exemplar.dinov3_local_scores[6] == duplicated_exemplars.dinov3_local_scores[6]


def test_m0_keeps_frozen_base_rows_unchanged():
    """Updating an old classifier row during novel training invalidates the frozen base control."""
    base_features = tuple(
        _scoring_example(category_id, f"base-{category_id}", repvit=(1.0, 0.0), dino=(1.0, 0.0))
        for category_id in range(1, 161)
    )
    novel_features = tuple(
        _scoring_example(category_id, f"novel-{category_id}", repvit=(0.0, 1.0), dino=(0.0, 1.0))
        for category_id in range(161, 201)
    )
    base_rows_before_fit = torch.arange(160 * 384, dtype=torch.float32).reshape(160, 384)
    snapshot = base_rows_before_fit.clone()

    head = fit_m0_head(base_features, novel_features, base_rows_before_fit)

    assert torch.equal(head.base_rows, snapshot)
    assert torch.equal(base_rows_before_fit, snapshot)


def test_branch_predictions_have_sorted_catalog_scores_and_provenance():
    """A partial or differently ordered score vector cannot cross the shared fusion boundary."""
    supports = _complete_scoring_supports()
    query = _scoring_query()

    prediction = score_m1(supports, supports, query)

    assert prediction.score_category_ids == tuple(range(1, 201))
    assert len(prediction.repvit_global_scores) == 200
    assert len(prediction.dinov3_global_scores) == 200
    assert len(prediction.dinov3_local_scores) == 200
    assert prediction.provenance.query == query.provenance
    assert prediction.provenance.repvit_support[6] == supports[7][0].provenance
    assert prediction.provenance.dinov3_support[6] == supports[7][0].provenance


def test_branch_scorers_reject_missing_class_and_query_support_overlap():
    """A malformed 200-SKU universe or query leaked into supports must abort scoring."""
    supports = _complete_scoring_supports()
    supports.pop(200)
    with pytest.raises(ValueError, match="registered 200-class catalog"):
        score_m1(supports, supports, _scoring_query())

    complete = _complete_scoring_supports()
    with pytest.raises(ValueError, match="query provenance is present in support"):
        score_m2(complete, complete, _scoring_query(source="support-seven-a"))
