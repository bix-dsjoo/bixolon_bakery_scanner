"""Fail-closed construction of the real CPU functional-smoke pipeline."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import hashlib
import importlib
from pathlib import Path
import subprocess
import sys

import torch
import yaml
from PIL import Image

from bakery_scanner.classification.runtime import ClassifierPipeline
from bakery_scanner.classification.config import ClassifierConfig, preprocess_sha256
from bakery_scanner.classification.contracts import ModelProvenance
from bakery_scanner.classification.policy import DecisionPolicy, PolicyCalibration
from bakery_scanner.detectors.dfine import JsonLineDFineTransport, PersistentDFineRunner
from bakery_scanner.verifier.assurance import (
    AssuranceBackend,
    BoxAssurancePrediction,
    _assurance_crop,
)
from bakery_scanner.verifier.model import build_mobilenetv4_verifier

from .runtime import MobileOnlyE2EPipeline


@dataclass(frozen=True, slots=True)
class CpuSmokeAssets:
    """All package-relative assets required by the CPU smoke execution path."""

    root: Path
    dfine_worker: Path
    dfine_checkout: Path
    dfine_config: Path
    dfine_checkpoint: Path
    verifier_checkpoint: Path
    classifier_config: Path
    repvit_checkpoint: Path
    repvit_manifest: Path
    repvit_prototype: Path
    dino_weights: Path
    dino_support: Path
    dino_local_bank: Path
    calibration: Path

    @classmethod
    def from_root(cls, root: Path) -> "CpuSmokeAssets":
        package_root = Path(root).resolve()
        classification = package_root / "artifacts" / "e2e_current_source" / "classification"
        return cls(
            root=package_root,
            dfine_worker=package_root / "scripts" / "dfine_jsonl_server.py",
            dfine_checkout=package_root / "third_party" / "D-FINE",
            dfine_config=package_root / "configs" / "generated" / "e2e-current-detector" / "dfine_n_640-seed20260724-fold0.yml",
            dfine_checkpoint=package_root / "artifacts" / "e2e_current_source" / "detectors" / "dfine_n_640-seed20260724-fold0" / "best_stg1.pth",
            verifier_checkpoint=package_root / "artifacts" / "e2e_current_source" / "verifiers" / "mobilenetv4_conv_small-seed20260724-fold0" / "verifier.pt",
            classifier_config=package_root / "configs" / "cpu_smoke_classifier_policy.yaml",
            repvit_checkpoint=package_root / "models" / "repvit_m1_15plus5_v1" / "repvit_m1_15plus5_v1.pt",
            repvit_manifest=package_root / "models" / "repvit_m1_15plus5_v1" / "repvit_m1_15plus5_v1.manifest.json",
            repvit_prototype=classification / "repvit_m1_15plus5_prototypes.pt",
            dino_weights=package_root / "models" / "dinov3_vits16_15plus5_v1" / "dinov3_vits16_pretrain_lvd1689m-08c60483.pth",
            dino_support=classification / "dinov3_vits16_support.pt",
            dino_local_bank=classification / "dinov3_vits16_local_patch_bank.pt",
            calibration=classification / "policy_v2_manifest_rebound_cpu_smoke.json",
        )


class LegacyFourStateAssuranceRunner:
    """CPU-smoke adapter for the historical four-logit MobileNetV4 checkpoint.

    The checkpoint has no learned box-quality or box-delta heads.  It exposes
    only trained state evidence: EXACTLY_ONE probability is quality and the
    correction is identically zero.  Recheck-required cases remain Unknown in
    ``MobileOnlyE2EPipeline``.
    """

    def __init__(self, model: torch.nn.Module, *, device: str, batch_size: int = 64) -> None:
        if device != "cpu":
            raise ValueError("legacy CPU smoke assurance runner requires device cpu")
        if batch_size <= 0:
            raise ValueError("batch_size must be positive")
        self.model = model.to(device).eval()
        self.device = torch.device(device)
        self.batch_size = batch_size
        self.backend = AssuranceBackend.MOBILENETV4

    def predict(
        self,
        candidates: tuple[object, ...],
        image: object,
    ) -> tuple[BoxAssurancePrediction, ...]:
        if not candidates:
            return ()
        frame = image.image if hasattr(image, "image") and isinstance(getattr(image, "image"), Image.Image) else image
        if not isinstance(frame, Image.Image):
            raise TypeError("legacy assurance runner requires a PIL or CanonicalImage frame")
        crops = tuple(_assurance_crop(frame, candidate) for candidate in candidates)
        rows: list[BoxAssurancePrediction] = []
        with torch.inference_mode():
            for start in range(0, len(candidates), self.batch_size):
                batch = torch.stack(crops[start : start + self.batch_size]).to(self.device)
                logits = self.model(batch)
                if not isinstance(logits, torch.Tensor) or logits.shape != (len(batch), 4):
                    raise ValueError("legacy MobileNetV4 verifier must return [N,4] state logits")
                probabilities = torch.softmax(logits, dim=1).cpu()
                for offset, candidate in enumerate(candidates[start : start + self.batch_size]):
                    state_probabilities = tuple(float(value) for value in probabilities[offset].tolist())
                    rows.append(
                        BoxAssurancePrediction(
                            candidate,
                            self.backend,
                            state_probabilities,
                            state_probabilities[1],
                            (0.0, 0.0, 0.0, 0.0),
                        )
                    )
        return tuple(rows)


def preflight_cpu_assets(assets: CpuSmokeAssets) -> dict[str, str]:
    """Validate every input before a worker process or output directory exists."""
    missing: list[str] = []
    if not assets.dfine_checkout.is_dir():
        missing.append(assets.dfine_checkout.relative_to(assets.root).as_posix())
    required = {
        "dfine_worker": assets.dfine_worker,
        "dfine_config": assets.dfine_config,
        "dfine_checkpoint": assets.dfine_checkpoint,
        "verifier_checkpoint": assets.verifier_checkpoint,
        "classifier_config": assets.classifier_config,
        "repvit_checkpoint": assets.repvit_checkpoint,
        "repvit_manifest": assets.repvit_manifest,
        "repvit_prototype": assets.repvit_prototype,
        "dino_weights": assets.dino_weights,
        "dino_support": assets.dino_support,
        "dino_local_bank": assets.dino_local_bank,
        "calibration": assets.calibration,
    }
    missing.extend(
        path.relative_to(assets.root).as_posix()
        for path in required.values()
        if not path.is_file()
    )
    if missing:
        raise FileNotFoundError("CPU smoke assets are missing: " + ", ".join(missing))
    for module in ("torch", "torchvision", "PIL", "timm", "yaml"):
        if importlib.util.find_spec(module) is None:
            raise RuntimeError(f"CPU smoke dependency is unavailable: {module}")
    _validate_dfine_worker_imports(assets)

    config = _load_classifier_config(assets.classifier_config)
    configured = {
        "repvit_checkpoint": (config["repvit"]["checkpoint"], config["repvit"]["checkpoint_sha256"]),
        "repvit_manifest": (config["repvit"]["manifest"], config["repvit"]["manifest_sha256"]),
        "repvit_prototype": (config["repvit"]["prototype_bank"], config["repvit"]["prototype_bank_sha256"]),
        "dino_weights": (config["dinov3"]["weights"], config["dinov3"]["weights_sha256"]),
        "dino_support": (config["dinov3"]["support"], config["dinov3"]["support_sha256"]),
        "dino_local_bank": (config["dinov3"]["local_bank"], config["dinov3"]["local_bank_sha256"]),
    }
    for name, (configured_path, expected_hash) in configured.items():
        expected_path = required[name].resolve()
        actual_path = (assets.classifier_config.parent / configured_path).resolve()
        if actual_path != expected_path:
            raise ValueError(f"classifier config {name} does not point to the CPU smoke asset")
        if _sha256(expected_path) != expected_hash:
            raise ValueError(f"classifier config {name} SHA-256 does not match")
    calibration = _validate_calibration_provenance(assets.classifier_config)

    result: dict[str, str] = {"package_root": str(assets.root)}
    for name, path in required.items():
        result[f"{name}_path"] = str(path.resolve())
        result[f"{name}_sha256"] = _sha256(path)
    result["calibration_id"] = calibration.calibration_id
    result["calibration_sha256"] = hashlib.sha256(calibration.to_json_bytes()).hexdigest()
    result["assurance_mode"] = "legacy_four_state_zero_delta"
    return result


def build_cpu_pipeline(assets: CpuSmokeAssets) -> tuple[MobileOnlyE2EPipeline, Callable[[], None]]:
    """Build the live CPU-only composition after ``preflight_cpu_assets`` succeeds."""
    preflight_cpu_assets(assets)
    transport = JsonLineDFineTransport(
        (
            sys.executable,
            str(assets.dfine_worker),
            "--config",
            str(assets.dfine_config),
            "--checkpoint",
            str(assets.dfine_checkpoint),
            "--device",
            "cpu",
        )
    )
    try:
        detector = PersistentDFineRunner(transport, source="dfine_n_640", device="cpu")
        payload = torch.load(assets.verifier_checkpoint, map_location="cpu", weights_only=True)
        if not isinstance(payload, dict) or not isinstance(payload.get("state_dict"), dict):
            raise ValueError("MobileNetV4 verifier checkpoint must contain a state_dict")
        model = build_mobilenetv4_verifier(pretrained=False)
        model.load_state_dict(payload["state_dict"])
        mobile = LegacyFourStateAssuranceRunner(model.eval(), device="cpu")
        classifier = ClassifierPipeline.load(assets.classifier_config)
    except Exception:
        transport.close()
        raise

    pipeline = MobileOnlyE2EPipeline(detector, mobile, classifier)

    def warmup() -> None:
        classifier._get_dino()
        classifier._get_local_bank()
        classifier.clock.synchronize()

    def close() -> None:
        transport.close()

    setattr(pipeline, "close", close)
    return pipeline, warmup


def _load_classifier_config(path: Path) -> dict[str, object]:
    with path.open("r", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle)
    if not isinstance(payload, dict):
        raise ValueError("classifier config must be a mapping")
    return payload


def _validate_calibration_provenance(config_path: Path) -> PolicyCalibration:
    """Prove policy calibration binds exactly the hash-pinned model evidence."""
    config = ClassifierConfig.load(config_path)
    calibration = PolicyCalibration.from_json_bytes(config.calibration.artifact.read_bytes())
    provenance = ModelProvenance(
        repvit_artifact_id=config.repvit.artifact_id,
        repvit_sha256=config.repvit.checkpoint_sha256,
        dinov3_artifact_id=config.dinov3.artifact_id,
        dinov3_sha256=config.dinov3.weights_sha256,
        dinov3_support_sha256=config.dinov3.support_sha256,
        calibration_id=calibration.calibration_id,
        calibration_sha256=hashlib.sha256(calibration.to_json_bytes()).hexdigest(),
        preprocess_sha256=preprocess_sha256(config.preprocess),
        repvit_manifest_sha256=config.repvit.manifest_sha256,
        repvit_prototype_sha256=config.repvit.prototype_bank_sha256 or "0" * 64,
    )
    DecisionPolicy(calibration, provenance=provenance)
    return calibration


def _validate_dfine_worker_imports(assets: CpuSmokeAssets) -> None:
    """Verify the worker's pinned-checkout imports before starting its JSONL process."""
    probe = (
        "import sys; from pathlib import Path; "
        "checkout = Path(sys.argv[1]); "
        "import torch; import torchvision; from PIL import Image; "
        "sys.path.insert(0, str(checkout)); "
        "from src.core import YAMLConfig"
    )
    try:
        completed = subprocess.run(
            (sys.executable, "-c", probe, str(assets.dfine_checkout)),
            cwd=assets.root,
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError(f"D-FINE worker imports could not be verified: {exc}") from exc
    if completed.returncode != 0:
        detail = completed.stderr.strip() or "unknown import failure"
        raise RuntimeError(f"D-FINE worker imports failed: {detail}")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()
