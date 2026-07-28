"""Keep one pinned D-FINE model warm and serve single-image JSONL requests.

Run this only with ``.venvs/dfine/Scripts/python.exe``.  Stdout is reserved
for one JSON response per request; diagnostics go to stderr.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import sys
from pathlib import Path


def _load_model(config_path: Path, checkpoint_path: Path, device: str):
    import torch
    from torch import nn

    checkout = Path(__file__).resolve().parents[1] / "third_party" / "D-FINE"
    sys.path.insert(0, str(checkout))
    from src.core import YAMLConfig

    with contextlib.redirect_stdout(sys.stderr):
        cfg = YAMLConfig(str(config_path), resume=str(checkpoint_path))
        if "HGNetv2" in cfg.yaml_cfg:
            cfg.yaml_cfg["HGNetv2"]["pretrained"] = False
        checkpoint = torch.load(checkpoint_path, map_location="cpu")
        state = checkpoint.get("ema", {}).get("module") if isinstance(checkpoint, dict) else None
        if state is None:
            state = checkpoint["model"]
        cfg.model.load_state_dict(state)

        class _Model(nn.Module):
            def __init__(self) -> None:
                super().__init__()
                self.model = cfg.model.deploy()
                self.postprocessor = cfg.postprocessor.deploy()

            def forward(self, images, original_sizes):
                return self.postprocessor(self.model(images), original_sizes)

        model = _Model().to(device).eval()
    return model


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--device", default="cuda:0")
    args = parser.parse_args()
    if args.device != "cuda:0":
        raise ValueError("D-FINE JSONL server requires cuda:0")

    import torch
    from PIL import Image
    import torchvision.transforms as transforms

    if not torch.cuda.is_available() or "RTX 5080" not in torch.cuda.get_device_name(0):
        raise RuntimeError("D-FINE JSONL server requires RTX 5080 cuda:0")
    model = _load_model(args.config.resolve(), args.checkpoint.resolve(), args.device)
    preprocess = transforms.Compose((transforms.Resize((640, 640)), transforms.ToTensor()))
    for line in sys.stdin:
        try:
            request = json.loads(line)
            image_id = request["image_id"]
            image_path = Path(request["image"])
            if type(image_id) is not int or image_id <= 0 or not image_path.is_file():
                raise ValueError("invalid image request")
            with Image.open(image_path) as loaded:
                image = loaded.convert("RGB")
            width, height = image.size
            tensor = preprocess(image).unsqueeze(0).to(args.device)
            original_sizes = torch.tensor([[width, height]], device=args.device)
            with torch.inference_mode():
                labels, boxes, scores = model(tensor, original_sizes)
            response = {
                "labels": labels[0].detach().cpu().tolist(),
                "boxes": boxes[0].detach().cpu().tolist(),
                "scores": scores[0].detach().cpu().tolist(),
            }
        except Exception as exc:  # keep request framing intact for the host
            response = {"error": f"{type(exc).__name__}: {exc}"}
        print(json.dumps(response, allow_nan=False, separators=(",", ":")), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
