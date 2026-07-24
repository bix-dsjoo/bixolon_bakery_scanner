import pytest
import subprocess

from bakery_scanner.contracts import Box
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
