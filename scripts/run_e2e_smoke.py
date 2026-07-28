"""Run the fixed nine-image CPU functional smoke profile transactionally."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import sys
from typing import Sequence

from PIL import Image, ImageDraw

from bakery_scanner.data.preprocess import canonicalize_image
from bakery_scanner.e2e.cpu_factory import CpuSmokeAssets, build_cpu_pipeline, preflight_cpu_assets
from bakery_scanner.e2e.cpu_profile import resolve_batch2_e3_m3_h3
from bakery_scanner.e2e.cpu_smoke import run_cpu_smoke


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package-root", type=Path, default=Path("."))
    parser.add_argument("--profile", default="batch2_e3_m3_h3")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--device", default="cpu")
    args = parser.parse_args(argv)
    if args.device != "cpu" or args.profile != "batch2_e3_m3_h3":
        _error("arguments", ValueError("device must be cpu and profile must be batch2_e3_m3_h3"))
        return 2
    output = args.output.resolve()
    if output.exists():
        _error("arguments", FileExistsError(f"refusing to overwrite existing output: {output}"))
        return 2
    created = False
    close = None
    try:
        assets = CpuSmokeAssets.from_root(args.package_root)
        provenance = preflight_cpu_assets(assets)
        images = resolve_batch2_e3_m3_h3(assets.root / "samples" / "batch2_e3_m3_h3")
        pipeline, warmup = build_cpu_pipeline(assets)
        close = getattr(pipeline, "close", None)
        warmup()
        pipeline.infer(1, _load_image(images[0]))
        output.mkdir(parents=True)
        created = True
        report = run_cpu_smoke(pipeline, images, load_image=_load_image, provenance=provenance)
        overlays = output / "overlays"
        overlays.mkdir()
        for path, row in zip(images, report["images"], strict=True):
            _write_overlay(_load_image(path), row["final_objects"], overlays / f"{path.stem}.png")
        (output / "inference.json").write_text(json.dumps(report, allow_nan=False, indent=2), encoding="utf-8")
        totals = [float(row["total_ms"]) for row in report["images"]]
        summary = {"E": sum(totals[:3]) / 3, "M": sum(totals[3:6]) / 3, "H": sum(totals[6:]) / 3}
        (output / "report.json").write_text(json.dumps(summary, allow_nan=False, indent=2), encoding="utf-8")
        return 0
    except Exception as exc:
        if created:
            shutil.rmtree(output)
        _error("inference", exc)
        return 1
    finally:
        if callable(close):
            close()


def _load_image(path: Path):
    with Image.open(path) as image:
        return canonicalize_image(image)


def _write_overlay(image, objects, path: Path) -> None:
    frame = image.image.copy()
    draw = ImageDraw.Draw(frame)
    for item in objects:
        left, top, right, bottom = item["box_xyxy"]
        draw.rectangle((left, top, right, bottom), outline="red", width=3)
    frame.save(path, format="PNG")


def _error(stage: str, exc: Exception) -> None:
    print(json.dumps({"stage": stage, "exception": type(exc).__name__, "message": str(exc)}), file=sys.stderr)


if __name__ == "__main__":
    raise SystemExit(main())
