import base64
import json
import subprocess
from pathlib import Path


def _run_runner_definitions(command: str) -> subprocess.CompletedProcess[str]:
    script = Path("scripts/run_dfine640_oof.ps1").read_text(encoding="utf-8")
    definitions = script.split("\nif (-not (Test-Path -LiteralPath $StagedAnnotations", maxsplit=1)[0]
    encoded = base64.b64encode((definitions + "\n" + command).encode("utf-16-le")).decode("ascii")
    return subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-EncodedCommand", encoded], check=False, capture_output=True, text=True)


def _powershell_literal(path: Path) -> str:
    return str(path).replace("'", "''")


def test_runner_requires_completed_fold0_handoff(tmp_path):
    result = _run_runner_definitions(f"$ArtifactRoot = '{_powershell_literal(tmp_path / 'detectors')}'\nAssert-RequiredFoldZero")

    assert result.returncode != 0
    assert "required completed fold 0" in (result.stdout + result.stderr).lower()


def test_runner_rejects_capture_scene_split_across_fold_partitions(tmp_path):
    annotations, staged_manifest, manifest = tmp_path / "annotations.json", tmp_path / "staged_manifest.json", tmp_path / "fold.json"
    train, validation = tmp_path / "train.json", tmp_path / "validation.json"
    annotations.write_text(json.dumps({"annotations": [], "categories": [], "images": [{"id": image_id, "width": 30, "height": 20} for image_id in (1, 2, 3)]}), encoding="utf-8")
    staged_manifest.write_text(json.dumps([{"image_id": 1, "scene": {"capture_batch": "g15", "scene_number": 1}}, {"image_id": 2, "scene": {"capture_batch": "g15", "scene_number": 1}}, {"image_id": 3, "scene": {"capture_batch": "g15", "scene_number": 3}}]), encoding="utf-8")
    manifest.write_text(json.dumps({"validation_image_ids": [1], "training_image_ids": [3]}), encoding="utf-8")

    result = _run_runner_definitions(f"$StagedAnnotations = '{_powershell_literal(annotations)}'\n$StagedManifest = '{_powershell_literal(staged_manifest)}'\nWrite-FoldAnnotations '{_powershell_literal(manifest)}' '{_powershell_literal(train)}' '{_powershell_literal(validation)}'")

    assert result.returncode != 0
    assert "whole capture scene" in (result.stdout + result.stderr).lower()


def test_runner_rejects_staged_manifest_missing_a_coco_image(tmp_path):
    """Scene isolation is meaningful only when the staged manifest covers every COCO image."""
    annotations, staged_manifest, manifest = tmp_path / "annotations.json", tmp_path / "staged_manifest.json", tmp_path / "fold.json"
    train, validation = tmp_path / "train.json", tmp_path / "validation.json"
    annotations.write_text(json.dumps({"annotations": [], "categories": [], "images": [{"id": image_id, "width": 30, "height": 20} for image_id in (1, 2, 3)]}), encoding="utf-8")
    staged_manifest.write_text(json.dumps([{"image_id": 1, "scene": {"capture_batch": "g15", "scene_number": 1}}, {"image_id": 3, "scene": {"capture_batch": "g15", "scene_number": 3}}]), encoding="utf-8")
    manifest.write_text(json.dumps({"validation_image_ids": [1], "training_image_ids": [3]}), encoding="utf-8")

    result = _run_runner_definitions(f"$StagedAnnotations = '{_powershell_literal(annotations)}'\n$StagedManifest = '{_powershell_literal(staged_manifest)}'\nWrite-FoldAnnotations '{_powershell_literal(manifest)}' '{_powershell_literal(train)}' '{_powershell_literal(validation)}'")

    assert result.returncode != 0
    assert "exactly cover coco image ids" in (result.stdout + result.stderr).lower()


def test_runner_writes_only_manifest_training_ids(tmp_path):
    annotations, staged_manifest, manifest = tmp_path / "annotations.json", tmp_path / "staged_manifest.json", tmp_path / "fold.json"
    train, validation = tmp_path / "train.json", tmp_path / "validation.json"
    annotations.write_text(json.dumps({"annotations": [], "categories": [], "images": [{"id": image_id, "width": 30, "height": 20} for image_id in (1, 2, 3)]}), encoding="utf-8")
    staged_manifest.write_text(json.dumps([{"image_id": image_id, "scene": {"capture_batch": "g15", "scene_number": image_id}} for image_id in (1, 2, 3)]), encoding="utf-8")
    manifest.write_text(json.dumps({"validation_image_ids": [1], "training_image_ids": [2]}), encoding="utf-8")

    result = _run_runner_definitions(f"$StagedAnnotations = '{_powershell_literal(annotations)}'\n$StagedManifest = '{_powershell_literal(staged_manifest)}'\nWrite-FoldAnnotations '{_powershell_literal(manifest)}' '{_powershell_literal(train)}' '{_powershell_literal(validation)}'")

    assert result.returncode == 0, result.stderr
    assert [row["id"] for row in json.loads(train.read_text(encoding="utf-8"))["images"]] == [2]
