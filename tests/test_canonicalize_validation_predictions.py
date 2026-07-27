import json
import subprocess
import sys
from pathlib import Path


_SCRIPT = Path("scripts/canonicalize_validation_predictions.py")


def _write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value), encoding="utf-8")


def _run_canonicalizer(tmp_path: Path, raw: Path, annotations: Path, output: Path, processed: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(_SCRIPT),
            "--backend",
            "dfine",
            "--source",
            "dfine_n_640",
            "--input",
            str(raw),
            "--input-format",
            "dfine-coco-json",
            "--annotations",
            str(annotations),
            "--output",
            str(output),
            "--processed-output",
            str(processed),
        ],
        cwd=Path.cwd(),
        text=True,
        capture_output=True,
        check=False,
    )


def test_dfine_canonicalizer_clips_to_annotation_dimensions_and_drops_empty_boxes(tmp_path):
    raw, annotations = tmp_path / "raw.json", tmp_path / "annotations.json"
    output, processed = tmp_path / "predictions.json", tmp_path / "processed.json"
    _write_json(
        raw,
        {
            "predictions": [
                {"image_id": 1, "bbox": [-2, 3, 17, 9], "score": 0.9},
                {"image_id": 1, "bbox": [12, 0, 2, 2], "score": 0.8},
            ],
            "processed_image_ids": [1],
        },
    )
    _write_json(annotations, {"images": [{"id": 1, "width": 10, "height": 10}]})

    completed = _run_canonicalizer(tmp_path, raw, annotations, output, processed)

    assert completed.returncode == 0, completed.stderr
    assert json.loads(output.read_text(encoding="utf-8")) == [
        {"bbox": [0.0, 3.0, 10.0, 7.0], "image_id": 1, "score": 0.9, "source": "dfine_n_640"}
    ]
    assert json.loads(processed.read_text(encoding="utf-8")) == [1]
