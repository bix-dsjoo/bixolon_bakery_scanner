$ErrorActionPreference = "Stop"

function Invoke-Checked([scriptblock]$Command, [string]$Description) {
    & $Command
    if ($LASTEXITCODE -ne 0) { throw "Failed: $Description (exit $LASTEXITCODE)" }
}

function Get-PinnedRepository([string]$Url, [string]$Destination, [string]$Commit) {
    if (Test-Path $Destination) {
        $head = & git -C $Destination rev-parse HEAD; if ($LASTEXITCODE -ne 0) { throw "Failed to inspect $Destination" }
        if ($head -ne $Commit) { throw "Pinned checkout mismatch: $Destination is $head, expected $Commit" }
        return
    }
    Invoke-Checked { git clone $Url $Destination } "clone $Url"
    Invoke-Checked { git -C $Destination checkout $Commit } "checkout $Commit"
}

$CudaRuntimeRepair = "MMCV CUDA build requires CUDA 12.8 development headers and libraries. Install artifacts\box_system\logs\cuda_12.8.1_windows_network.exe -s -n cudart_12.8,cudart_dev_12.8,cublas_12.8,cublas_dev_12.8,cusolver_12.8,cusolver_dev_12.8,cusparse_12.8,cusparse_dev_12.8,cufft_12.8,cufft_dev_12.8,curand_12.8,curand_dev_12.8, then rerun."

function Assert-CudaBuildPrerequisites() {
    if ([string]::IsNullOrWhiteSpace($env:CUDA_PATH)) { throw $CudaRuntimeRepair }
    if (-not (Test-Path -LiteralPath $env:CUDA_PATH -PathType Container)) { throw $CudaRuntimeRepair }
    $CudaRoot = (Resolve-Path -LiteralPath $env:CUDA_PATH).Path
    if ((Split-Path -Leaf $CudaRoot) -ine "v12.8") { throw $CudaRuntimeRepair }
    $Nvcc = Join-Path $env:CUDA_PATH "bin\nvcc.exe"
    if (-not (Test-Path $Nvcc)) { throw "$CudaRuntimeRepair Expected CUDA 12.8 compiler: $Nvcc" }
    if (-not ((Resolve-Path $Nvcc).Path.StartsWith($CudaRoot, [StringComparison]::OrdinalIgnoreCase))) { throw "$CudaRuntimeRepair nvcc must resolve beneath CUDA_PATH" }
    $NvccVersion = (& $Nvcc -V) -join [Environment]::NewLine
    if ($LASTEXITCODE -ne 0 -or $NvccVersion -notmatch "release 12\.8") { throw "$CudaRuntimeRepair CUDA_PATH nvcc must report release 12.8" }

    $RequiredCudaFamilies = @(
        @{ Name = "CUDA runtime"; Files = @("include\cuda_runtime.h", "lib\x64\cudart.lib") },
        @{ Name = "cuBLAS"; Files = @("include\cublas_v2.h", "include\cublasLt.h", "lib\x64\cublas.lib", "lib\x64\cublasLt.lib") },
        @{ Name = "cuSOLVER"; Files = @("include\cusolverDn.h", "lib\x64\cusolver.lib") },
        @{ Name = "cuSPARSE"; Files = @("include\cusparse.h", "lib\x64\cusparse.lib") },
        @{ Name = "cuFFT"; Files = @("include\cufft.h", "lib\x64\cufft.lib") },
        @{ Name = "cuRAND"; Files = @("include\curand.h", "lib\x64\curand.lib") }
    )
    $MissingFamilies = @(
        $RequiredCudaFamilies | Where-Object {
            $Family = $_
            @($Family.Files | Where-Object { -not (Test-Path (Join-Path $CudaRoot $_)) }).Count -gt 0
        } | ForEach-Object { $_.Name }
    )
    if ($MissingFamilies.Count -gt 0) {
        throw "Missing CUDA 12.8 development components: $($MissingFamilies -join ', '). $CudaRuntimeRepair"
    }
}

Assert-CudaBuildPrerequisites

Get-PinnedRepository "https://github.com/Peterande/D-FINE.git" "third_party/D-FINE" "7fe2f8889f0b7b817f20c315b40fc15a4fb64ae6"
$DFinePatch = "..\..\third_party_patches\dfine_oof_predictions.patch"
$ReversePatchApplied = $false
$PreviousErrorActionPreference = $ErrorActionPreference
try {
    # A nonzero reverse check means the patch has not yet been applied.
    $ErrorActionPreference = "Continue"
    & git -C third_party/D-FINE apply --reverse --check $DFinePatch 2>$null
    $ReversePatchApplied = ($LASTEXITCODE -eq 0)
} finally {
    $ErrorActionPreference = $PreviousErrorActionPreference
}
if (-not $ReversePatchApplied) {
    Invoke-Checked { git -C third_party/D-FINE apply --check $DFinePatch } "check D-FINE OOF patch"
    Invoke-Checked { git -C third_party/D-FINE apply $DFinePatch } "apply D-FINE OOF patch"
}
Get-PinnedRepository "https://github.com/open-mmlab/mmdetection.git" "third_party/mmdetection" "ecac3a77becc63f23d9f6980b2a36f86acd00a8a"
Get-PinnedRepository "https://github.com/open-mmlab/mmdeploy.git" "third_party/mmdeploy" "3f8604bd72e8e15d06b2e0552fe2fdb8f8de33c4"
Invoke-Checked { py -3.11 -m venv .venvs/dfine } "create D-FINE venv"
Invoke-Checked { py -3.11 -m venv .venvs/rtmdet } "create RTMDet venv"

function Install-CUDAEnvironment([string]$Python, [string[]]$Packages) {
    Invoke-Checked { & $Python -m pip install --upgrade "pip==25.1.1" "setuptools==80.9.0" "wheel==0.45.1" } "install packaging tools"
    Invoke-Checked { & $Python -m pip install --index-url https://download.pytorch.org/whl/cu128 "torch==2.8.0+cu128" "torchvision==0.23.0+cu128" } "install CUDA 12.8 PyTorch"
    Invoke-Checked { & $Python -m pip install @Packages } "install pinned detector dependencies"
}

Install-CUDAEnvironment ".venvs/dfine/Scripts/python.exe" @("-r", "third_party/D-FINE/requirements.txt", "matplotlib==3.10.6")
Install-CUDAEnvironment ".venvs/rtmdet/Scripts/python.exe" @("mmengine==0.10.7", "mmdet==3.3.0")
# OpenMMLab currently provides no pinned prebuilt mmcv wheel contract here for
# torch 2.8/cu128. The CUDA build prerequisites above prohibit CPU fallback.
$env:FORCE_CUDA = "1"
$env:TORCH_CUDA_ARCH_LIST = "12.0"
Invoke-Checked { & .venvs/rtmdet/Scripts/python.exe -m pip install --no-binary mmcv "mmcv==2.2.0" } "build CUDA MMCV 2.2.0"
Push-Location third_party/D-FINE
Invoke-Checked { & ..\..\.venvs\dfine\Scripts\python.exe -c "import torch, torchvision, matplotlib; from src.core import YAMLConfig; assert torch.__version__ == '2.8.0+cu128'; assert torchvision.__version__ == '0.23.0+cu128'; assert matplotlib.__version__ == '3.10.6'; assert torch.version.cuda == '12.8'; assert torch.cuda.is_available(); assert 'RTX 5080' in torch.cuda.get_device_name(0)" } "verify pinned D-FINE CUDA environment"
Pop-Location
Invoke-Checked { & .venvs/rtmdet/Scripts/python.exe -c "import torch, torchvision, mmengine, mmcv, mmdet; assert torch.__version__ == '2.8.0+cu128'; assert torchvision.__version__ == '0.23.0+cu128'; assert torch.version.cuda == '12.8'; assert torch.cuda.is_available(); assert 'RTX 5080' in torch.cuda.get_device_name(0); assert mmengine.__version__ == '0.10.7'; assert mmcv.__version__ == '2.2.0'; assert mmdet.__version__ == '3.3.0'" } "verify pinned MMDetection CUDA environment"
if ($LASTEXITCODE -ne 0) { throw "Pinned CPU detector environment import/version verification failed; inspect the venv package constraints." }
