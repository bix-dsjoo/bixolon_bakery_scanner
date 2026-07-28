import pytest
import subprocess
import re
import json
import os
from pathlib import Path

from PIL import Image

from bakery_scanner.contracts import Box
from bakery_scanner.data.preprocess import canonicalize_image
from bakery_scanner.detectors.dfine import DFineRunner, parse_dfine_output


def test_dfine_xyxy_is_normalized_to_source_xywh():
    rows = parse_dfine_output(
        image_id=7,
        image_size=(100, 80),
        labels=[0],
        boxes=[[10, 20, 40, 60]],
        scores=[.2],
        source="dfine_n_768",
    )
    assert rows[0].box == Box(10, 20, 30, 40)
    assert rows[0].class_name == "bread"


def test_dfine_parser_rejects_unknown_classes_and_caps_canonical_candidates():
    with pytest.raises(ValueError, match="class"):
        parse_dfine_output(1, (100, 80), [1], [[0, 0, 10, 10]], [.5], "dfine_n_768")
    rows = parse_dfine_output(
        1, (100, 80), [0] * 31,
        [[index, 0, index + 1, 1] for index in range(31)],
        [0.5] * 31, "dfine_n_768",
    )
    assert len(rows) == 30
    assert rows[0].box == Box(0, 0, 1, 1)


def test_runner_uses_injected_command_runner(tmp_path):
    calls = []
    runner = DFineRunner(command_runner=lambda command: calls.append(command) or {"labels": [], "boxes": [], "scores": []}, gpu_probe=lambda: (True, "NVIDIA RTX 5080"))
    assert runner.predict("model.pt", "image.png", image_id=1, image_size=(10, 10), source="dfine_n_640") == ()
    assert calls[0][0] == "dfine-predict"


def test_runner_materializes_canonical_visual_frame_for_detector(tmp_path):
    calls = []

    def run(command):
        path = Path(command[command.index("--image") + 1])
        with Image.open(path) as materialized:
            calls.append(materialized.size)
        return {"labels": [0], "boxes": [[1, 2, 11, 22]], "scores": [0.8]}

    frame = canonicalize_image(Image.new("RGB", (20, 40), "white"))
    runner = DFineRunner(command_runner=run, gpu_probe=lambda: (True, "NVIDIA RTX 5080"))

    rows = runner.predict("model.pt", frame, image_id=1, source="dfine_n_640")

    assert calls == [(20, 40)]
    assert rows[0].image_width == 20
    assert rows[0].image_height == 40
    assert rows[0].box == Box(1, 2, 10, 20)


def test_runner_rejects_cpu_unavailable_and_wrong_gpu():
    runner = DFineRunner(gpu_probe=lambda: (False, ""))
    with pytest.raises(RuntimeError): runner.train("c", "o")
    wrong = DFineRunner(gpu_probe=lambda: (True, "RTX 4090"))
    with pytest.raises(RuntimeError): wrong.train("c", "o")
    allowed = DFineRunner(command_runner=lambda _: {}, gpu_probe=lambda: (True, "RTX 5080"))
    allowed.train("c", "o", device="CUDA:0")
    with pytest.raises(ValueError): allowed.train("c", "o", device="cuda:1")


def test_dfine_overlay_exposes_injectable_640_and_768_input_size_contract():
    overlay = __import__("pathlib").Path("configs/upstream/dfine_bread.yml").read_text(encoding="utf-8")
    assert "__INJECTED_INPUT_SIZE__" in overlay
    assert "base_size" in overlay


def test_dfine_overlay_injects_eval_spatial_size_for_the_selected_variant():
    """A 768 run must not retain the inherited 640 eval anchors."""
    overlay = Path("configs/upstream/dfine_bread.yml").read_text(encoding="utf-8")

    assert "eval_spatial_size: [__INJECTED_INPUT_SIZE__, __INJECTED_INPUT_SIZE__]" in overlay


def test_dfine_matrix_injects_explicit_train_and_validation_batch_sizes():
    """D-FINE must not inherit a multi-GPU total batch size for one RTX 5080."""
    overlay = Path("configs/upstream/dfine_bread.yml").read_text(encoding="utf-8")
    script = Path("scripts/run_detector_matrix.ps1").read_text(encoding="utf-8")

    assert "__INJECTED_DFINE_TRAIN_BATCH__" in overlay
    assert "__INJECTED_DFINE_VAL_BATCH__" in overlay
    assert '.Replace("__INJECTED_DFINE_TRAIN_BATCH__",' in script
    assert '.Replace("__INJECTED_DFINE_VAL_BATCH__",' in script


def test_dfine_matrix_injects_explicit_base_learning_rate():
    """D-FINE must not inherit the upstream multi-GPU learning rate."""
    overlay = Path("configs/upstream/dfine_bread.yml").read_text(encoding="utf-8")
    script = Path("scripts/run_detector_matrix.ps1").read_text(encoding="utf-8")

    assert "__INJECTED_DFINE_BASE_LR__" in overlay
    assert "__INJECTED_DFINE_BACKBONE_LR__" in overlay
    assert '.Replace("__INJECTED_DFINE_BASE_LR__",' in script
    assert '.Replace("__INJECTED_DFINE_BACKBONE_LR__",' in script


def test_dfine_matrix_uses_an_explicit_interpreter_for_cpu_postprocessing():
    """Post-training JSON tools must not depend on the Windows PATH alias."""
    script = Path("scripts/run_detector_matrix.ps1").read_text(encoding="utf-8")

    assert '$HostPython = "C:\\Users\\OMEN\\AppData\\Local\\Programs\\Python\\Python311\\python.exe"' in script
    assert "& $HostPython scripts/canonicalize_validation_predictions.py" in script
    assert "& $HostPython scripts/collect_oof_evidence.py" in script
    assert "& python scripts/canonicalize_validation_predictions.py" not in script
    assert "& python scripts/collect_oof_evidence.py" not in script


def test_dfine_matrix_passes_the_held_out_coco_annotations_to_canonicalization():
    """Canonical OOF boxes must be clipped against the validation image bounds."""
    script = Path("scripts/run_detector_matrix.ps1").read_text(encoding="utf-8")

    canonicalize = next(line for line in script.splitlines() if "canonicalize_validation_predictions.py" in line)
    assert "--annotations $ValidationAnnotations" in canonicalize


def test_dfine_matrix_serializes_small_learning_rates_as_plain_invariant_yaml_decimals(tmp_path):
    """YAML 1.1 must receive a plain decimal, never a scientific-notation string."""
    script = Path("scripts/run_detector_matrix.ps1").read_text(encoding="utf-8")
    helper = re.search(r"(?ms)^function Convert-ToInvariantYamlFloat\b.*?^}\s*$", script)
    assert helper, "matrix script needs a Convert-ToInvariantYamlFloat helper"

    smoke = tmp_path / "invariant-yaml-float.ps1"
    smoke.write_text(
        helper.group(0)
        + "\n$result = Convert-ToInvariantYamlFloat 0.00005"
        + "\nif ($result -cne '0.00005') { Write-Error \"expected plain decimal, got: $result\"; exit 1 }\n",
        encoding="utf-8",
    )
    completed = subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(smoke)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr


@pytest.mark.parametrize("size", (640, 768))
def test_dfine_overlay_keeps_terminal_tensor_and_box_transforms_for_each_input_size(size):
    """Resize must not replace D-FINE's tensor/box terminal transforms."""
    overlay = Path("configs/upstream/dfine_bread.yml").read_text(encoding="utf-8")
    rendered = overlay.replace("__INJECTED_INPUT_SIZE__", str(size))

    assert rendered.count(f"type: Resize, size: [{size}, {size}]") == 2
    assert "type: ConvertPILImage, dtype: 'float32', scale: True" in rendered
    assert "type: ConvertBoxes, fmt: 'cxcywh', normalize: True" in rendered


@pytest.mark.parametrize("size", (640, 768))
def test_dfine_pinned_config_transforms_a_dataset_sample_to_tensor_with_normalized_cxcywh_boxes(tmp_path, size):
    """Exercise the pinned loader and actual configured transforms, not a mock pipeline."""
    checkout = Path("third_party/D-FINE").resolve()
    generated_root = tmp_path / "configs" / "generated" / "detector-matrix"
    generated_root.mkdir(parents=True)
    base_config = Path("third_party/D-FINE/configs/dfine/dfine_hgnetv2_n_coco.yml").resolve()
    overlay = Path("configs/upstream/dfine_bread.yml").read_text(encoding="utf-8")
    config_path = generated_root / f"dfine-{size}.yml"
    config_path.write_text(
        overlay
        .replace("__INJECTED_DFINE_BASE__", os.path.relpath(base_config, generated_root).replace("\\", "/"))
        .replace("__INJECTED_IMAGES_DIR__", "artifacts/box_system/staged/images")
        .replace("__INJECTED_TRAIN_ANNOTATIONS__", "artifacts/box_system/staged/annotations.json")
        .replace("__INJECTED_VALIDATION_ANNOTATIONS__", "artifacts/box_system/staged/annotations.json")
        .replace("__INJECTED_INPUT_SIZE__", str(size))
        .replace("__INJECTED_DFINE_TRAIN_BATCH__", "16")
        .replace("__INJECTED_DFINE_VAL_BATCH__", "16")
        .replace("__INJECTED_DFINE_BASE_LR__", "0.0001")
        .replace("__INJECTED_DFINE_BACKBONE_LR__", "0.00005"),
        encoding="utf-8",
    )
    probe = (
        "import json, sys, torch; "
        f"sys.path.insert(0, r'{checkout}'); "
        "import src; from src.core import YAMLConfig; "
        f"cfg=YAMLConfig(r'{config_path.resolve()}'); "
        "dataset=cfg.train_dataloader.dataset; dataset.set_epoch(72); "
        "[setattr(op, 'p', 0.0) for op in dataset._transforms.transforms if type(op).__name__ == 'RandomHorizontalFlip']; "
        "raw_image, raw_target=dataset.load_item(0); image, target=dataset[0]; "
        "raw_boxes=torch.as_tensor(raw_target['boxes']); width, height=raw_image.size; "
        "expected=torch.stack(((raw_boxes[:, 0] + raw_boxes[:, 2]) / (2 * width), (raw_boxes[:, 1] + raw_boxes[:, 3]) / (2 * height), (raw_boxes[:, 2] - raw_boxes[:, 0]) / width, (raw_boxes[:, 3] - raw_boxes[:, 1]) / height), dim=1); "
        "val_image, _=cfg.val_dataloader.dataset[0]; "
        "payload={'tensor': isinstance(image, torch.Tensor), 'shape': list(image.shape), "
        "'dtype': str(image.dtype), 'scaled': bool(float(image.min()) >= 0 and float(image.max()) <= 1), "
        "'boxes_cxcywh_normalized': bool(torch.allclose(torch.as_tensor(target['boxes']), expected)), "
        "'val_tensor': isinstance(val_image, torch.Tensor), 'val_shape': list(val_image.shape)}; "
        "print(json.dumps(payload))"
    )
    completed = subprocess.run(
        [".venvs/dfine/Scripts/python.exe", "-c", probe],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    result = json.loads(completed.stdout.splitlines()[-1])
    assert result == {
        "tensor": True,
        "shape": [3, size, size],
        "dtype": "torch.float32",
        "scaled": True,
        "boxes_cxcywh_normalized": True,
        "val_tensor": True,
        "val_shape": [3, size, size],
    }


def test_matrix_writes_dfine_include_and_data_paths_relative_to_their_consumers(tmp_path):
    """D-FINE loads includes beside the config but opens dataset fields from repo CWD."""
    script = Path("scripts/run_detector_matrix.ps1").read_text(encoding="utf-8")
    overlay = Path("configs/upstream/dfine_bread.yml").read_text(encoding="utf-8")

    assert "__include__:\n  - __INJECTED_DFINE_BASE__" in overlay
    assert "function Convert-ToPosixRelativePath" in script
    assert "function Convert-ToPosixRepositoryPath" in script
    assert "Convert-ToPosixRelativePath $GeneratedConfigRoot \"third_party/D-FINE/configs/dfine/dfine_hgnetv2_n_coco.yml\"" in script
    assert "Convert-ToPosixRepositoryPath $TrainAnnotations" in script
    assert "Convert-ToPosixRepositoryPath (Join-Path $StagedRoot \"images\")" in script

    generated_root = tmp_path / "configs" / "generated" / "detector-matrix"
    generated_root.mkdir(parents=True)
    base_config = Path("third_party/D-FINE/configs/dfine/dfine_hgnetv2_n_coco.yml").resolve()
    images = Path("artifacts/box_system/staged/images").resolve()
    # The matrix owns generated fold files; use the permanent staged COCO
    # artifact to exercise path conversion without depending on a live run.
    train = Path("artifacts/box_system/staged/annotations.json").resolve()
    validation = Path("artifacts/box_system/staged/annotations.json").resolve()

    helper = re.search(r"(?ms)^function Convert-ToPosixRelativePath\b.*?^}\s*^function Convert-ToPosixRepositoryPath\b.*?^}\s*$", script)
    assert helper, "matrix script needs separate D-FINE include and repository-data path helpers"
    helper_smoke = tmp_path / "relative-paths.ps1"
    helper_smoke.write_text(
        helper.group(0)
        + "\n$include = Convert-ToPosixRelativePath '"
        + str(generated_root)
        + "' '"
        + str(base_config)
        + "'\n$data = @("
        + ", ".join(json.dumps(str(path)) for path in (images, train, validation))
        + ") | ForEach-Object { Convert-ToPosixRepositoryPath $_ }\n(@($include) + @($data)) | ConvertTo-Json -Compress\n",
        encoding="utf-8",
    )
    converted = subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(helper_smoke)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert converted.returncode == 0, converted.stderr
    base_relative, images_relative, train_relative, validation_relative = json.loads(converted.stdout)
    assert all("\\" not in value for value in (base_relative, images_relative, train_relative, validation_relative))
    assert base_relative.startswith("../")
    assert not images_relative.startswith("../")
    assert not train_relative.startswith("../")
    assert not validation_relative.startswith("../")
    assert (Path.cwd() / images_relative).is_dir()
    assert (Path.cwd() / train_relative).is_file()
    assert (Path.cwd() / validation_relative).is_file()

    rendered = (
        overlay.replace("__INJECTED_DFINE_BASE__", base_relative)
        .replace("__INJECTED_IMAGES_DIR__", images_relative)
        .replace("__INJECTED_TRAIN_ANNOTATIONS__", train_relative)
        .replace("__INJECTED_VALIDATION_ANNOTATIONS__", validation_relative)
        .replace("__INJECTED_INPUT_SIZE__", "640")
        .replace("__INJECTED_DFINE_TRAIN_BATCH__", "16")
        .replace("__INJECTED_DFINE_VAL_BATCH__", "16")
        .replace("__INJECTED_DFINE_BASE_LR__", "0.0001")
        .replace("__INJECTED_DFINE_BACKBONE_LR__", "0.00005")
    )
    config_path = generated_root / "dfine.yml"
    config_path.write_text(rendered, encoding="utf-8")

    checkout = Path("third_party/D-FINE").resolve()
    bad_config_path = generated_root / "scalar-windows.yml"
    bad_config_path.write_text(f"__include__: {base_config}\n", encoding="utf-8")
    probe = (
        "import sys; "
        f"sys.path.insert(0, r'{checkout}'); "
        "from src.core.yaml_utils import load_config; "
        f"cfg=load_config(r'{config_path}'); "
        "assert cfg['DFINE']['backbone'] == 'HGNetv2'; "
        f"assert cfg['train_dataloader']['dataset']['img_folder'] == r'{images_relative}'; "
        f"assert cfg['val_dataloader']['dataset']['ann_file'] == r'{validation_relative}'; "
        "assert isinstance(cfg['__include__'], list)"
    )
    completed = subprocess.run(
        [".venvs/dfine/Scripts/python.exe", "-c", probe],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr

    scalar = subprocess.run(
        [".venvs/dfine/Scripts/python.exe", "-c", f"import sys; sys.path.insert(0, r'{checkout}'); from src.core.yaml_utils import load_config; load_config(r'{bad_config_path}')"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert scalar.returncode != 0
    assert scalar.stderr.rstrip().endswith("detector-matrix\\\\C'"), scalar.stderr


def test_matrix_script_generates_every_variant_seed_fold_config_and_receipt():
    script = __import__("pathlib").Path("scripts/run_detector_matrix.ps1").read_text(encoding="utf-8")
    assert "foreach ($Variant in $Variants)" in script
    assert "foreach ($Seed in $Seeds)" in script
    assert "foreach ($Fold in 0..4)" in script
    assert "receipt.json" in script and "validation_predictions.json" in script
    assert "fold-$Fold/manifest.json" in script
    assert "--test-only" in script
    assert "__INJECTED_MMD_BASE__" in script
    assert "canonicalize_validation_predictions.py" in script
    assert "collect_oof_evidence.py" in script
    assert "DFINE_OOF_PREDICTIONS" in script
    overlay = __import__("pathlib").Path("configs/upstream/dfine_bread.yml").read_text(encoding="utf-8")
    assert "img_folder" in overlay and "ann_file" in overlay
    assert "dataset:" in overlay and "base_size:" in overlay
    assert "remap_mscoco_category: true" in overlay
    assert "processed-output" in __import__("pathlib").Path("scripts/canonicalize_validation_predictions.py").read_text(encoding="utf-8")


def test_matrix_generated_artifacts_use_a_reusable_utf8_without_bom_writer(tmp_path):
    """Generated configs, fold COCO, and receipts must decode on Windows Python."""
    script = __import__("pathlib").Path("scripts/run_detector_matrix.ps1").read_text(encoding="utf-8")
    helper = re.search(
        r"(?ms)^function Write-Utf8NoBom\b.*?^}\s*$",
        script,
    )
    assert helper, "matrix script needs a reusable Write-Utf8NoBom helper"
    # One declaration plus train COCO, validation COCO, run config, and receipt.
    assert script.count("Write-Utf8NoBom") >= 5
    assert "Set-Content -NoNewline -Encoding utf8" not in script

    smoke = tmp_path / "utf8-smoke.ps1"
    target = tmp_path / "한글-생성.json"
    smoke.write_text(
        helper.group(0)
        + f"\nWrite-Utf8NoBom -Path '{target}' -Value '{{\"label\":\"빵\"}}'"
        + f"\n$bytes = [IO.File]::ReadAllBytes('{target}')"
        + "\nif ($bytes.Length -lt 3 -or ($bytes[0] -eq 0xEF -and $bytes[1] -eq 0xBB -and $bytes[2] -eq 0xBF)) { exit 1 }\n",
        # Windows PowerShell 5 needs a BOM to parse this *test script*'s Korean
        # literals; the artifact written by the helper is what must have none.
        encoding="utf-8-sig",
    )
    completed = subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(smoke)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    assert target.read_bytes()[:3] != b"\xef\xbb\xbf"


def test_bootstrap_pins_cpu_dependencies_and_patch_gathers_distributed_ids():
    bootstrap = __import__("pathlib").Path("scripts/bootstrap_training.ps1").read_text(encoding="utf-8")
    patch = __import__("pathlib").Path("third_party_patches/dfine_oof_predictions.patch").read_text(encoding="utf-8")
    assert "torch==2.8.0+cu128" in bootstrap and "mmdet==3.3.0" in bootstrap
    assert "import torch, torchvision, mmengine, mmcv, mmdet" in bootstrap
    assert patch.count("all_gather_object") >= 2 and "gathered_oof_predictions" in patch
    assert "Invoke-Checked" in bootstrap and "from src.core import YAMLConfig" in bootstrap
    assert "apply --check $DFinePatch" in bootstrap and "create D-FINE venv" in bootstrap
    assert "torch.version.cuda == '12.8'" in bootstrap and "RTX 5080" in bootstrap and "nvcc" in bootstrap
    assert "FORCE_CUDA" in bootstrap
    assert "Join-Path $env:CUDA_PATH \"bin\\nvcc.exe\"" in bootstrap and "release 12\\.8" in bootstrap
    assert "cuda_runtime.h" in bootstrap and "cudart.lib" in bootstrap and "artifacts\\box_system\\logs\\cuda_12.8.1_windows_network.exe -s -n cudart_12.8" in bootstrap
    assert "if ([string]::IsNullOrWhiteSpace($env:CUDA_PATH))" in bootstrap
    assert "$CudaRoot = (Resolve-Path -LiteralPath $env:CUDA_PATH).Path" in bootstrap
    assert "Split-Path -Leaf $CudaRoot" in bootstrap and "v12.8" in bootstrap
    assert bootstrap.index("if ([string]::IsNullOrWhiteSpace($env:CUDA_PATH))") < bootstrap.index('Join-Path $env:CUDA_PATH "bin\\nvcc.exe"')
    assert 'TORCH_CUDA_ARCH_LIST = "12.0"' in bootstrap
    assert "$PreviousErrorActionPreference" in bootstrap and "$ErrorActionPreference = \"Continue\"" in bootstrap and "finally" in bootstrap
    matrix = __import__("pathlib").Path("scripts/run_detector_matrix.ps1").read_text(encoding="utf-8")
    assert "Invoke-Checked" in matrix and "finally" in matrix and "best_coco_bbox_mAP_*.pth" in matrix
    assert "CUDA_VISIBLE_DEVICES" in matrix and "-d cuda:0" in matrix
    assert "require RTX 5080 CUDA" in matrix
    assert "Refusing stale run-owned artifacts" in matrix and "best_coco_bbox_mAP_*.pth" in matrix
    overlay = __import__("pathlib").Path("configs/upstream/dfine_bread.yml").read_text(encoding="utf-8")
    assert overlay.count("type: Resize") == 2


def test_bootstrap_pins_mmcv_within_mmdetection_330_compatibility_range():
    """MMDetection 3.3.0 rejects MMCV 2.2.0; keep its compatible CUDA source pin."""
    bootstrap = __import__("pathlib").Path("scripts/bootstrap_training.ps1").read_text(encoding="utf-8")
    assert '"mmcv==2.1.0"' in bootstrap
    assert "build CUDA MMCV 2.1.0" in bootstrap
    assert "mmcv.__version__ == '2.1.0'" in bootstrap
    assert "mmcv==2.2.0" not in bootstrap


def test_bootstrap_installs_and_verifies_pinned_dfine_matplotlib():
    """D-FINE validator imports matplotlib although upstream requirements omit it."""
    bootstrap = __import__("pathlib").Path("scripts/bootstrap_training.ps1").read_text(encoding="utf-8")
    assert '"matplotlib==3.10.6"' in bootstrap
    assert "import torch, torchvision, matplotlib" in bootstrap
    assert "matplotlib.__version__ == '3.10.6'" in bootstrap


def test_dfine_oof_patch_is_context_rich_and_exports_once_before_evaluate_return():
    """The pinned D-FINE patch must be unambiguous and cannot append after return."""
    patch = __import__("pathlib").Path("third_party_patches/dfine_oof_predictions.patch").read_text(encoding="utf-8")
    assert "@@ -8,0" not in patch
    assert "@@ -179,0" not in patch
    assert "@@ -207,0" not in patch
    assert "@@ -249,0" not in patch
    assert patch.count("oof_predictions = []") == 1
    assert patch.count("processed_image_ids = []") == 1
    assert patch.count("all_gather_object") == 2
    assert patch.index("results = postprocessor(outputs, orig_target_sizes)") < patch.index("for target, output in zip(targets, results):")
    assert patch.index("json.dump(") < patch.index("# Conf matrix, F1, Precision, Recall, box IoU")


def test_bootstrap_matches_release_in_multiline_nvcc_version_output():
    """CUDA's multi-line ``nvcc -V`` output must be matched as one string."""
    bootstrap = __import__("pathlib").Path("scripts/bootstrap_training.ps1").read_text(encoding="utf-8")
    completed = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-Command",
            "$NvccVersion = @('nvcc: NVIDIA (R) Cuda compiler driver', "
            "'Copyright (c) NVIDIA Corporation', "
            "'Cuda compilation tools, release 12.8, V12.8.93'); "
            "$NvccVersionText = $NvccVersion -join [Environment]::NewLine; "
            "if ($NvccVersionText -notmatch 'release 12\\.8') { exit 1 }",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    assert "$NvccVersion = (& $Nvcc -V) -join [Environment]::NewLine" in bootstrap


def test_bootstrap_requires_cuda_math_development_families_before_pip():
    """A missing CUDA math development family must stop the GPU build up front."""
    bootstrap = __import__("pathlib").Path("scripts/bootstrap_training.ps1").read_text(encoding="utf-8")
    required_headers = (
        "cublas_v2.h",
        "cublasLt.h",
        "cusolverDn.h",
        "cusparse.h",
        "cufft.h",
        "curand.h",
    )
    required_libraries = ("cublas.lib", "cublasLt.lib", "cusolver.lib", "cusparse.lib", "cufft.lib", "curand.lib")
    repair_packages = (
        "cudart_12.8",
        "cudart_dev_12.8",
        "cublas_12.8",
        "cublas_dev_12.8",
        "cusolver_12.8",
        "cusolver_dev_12.8",
        "cusparse_12.8",
        "cusparse_dev_12.8",
        "cufft_12.8",
        "cufft_dev_12.8",
        "curand_12.8",
        "curand_dev_12.8",
    )
    assert all(item in bootstrap for item in required_headers + required_libraries + repair_packages)
    assert "Missing CUDA 12.8 development components" in bootstrap
    assert bootstrap.index("Missing CUDA 12.8 development components") < bootstrap.index("Install-CUDAEnvironment")
