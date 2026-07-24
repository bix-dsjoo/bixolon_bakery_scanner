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

Install-CUDAEnvironment ".venvs/dfine/Scripts/python.exe" @("-r", "third_party/D-FINE/requirements.txt")
Install-CUDAEnvironment ".venvs/rtmdet/Scripts/python.exe" @("mmengine==0.10.7", "mmdet==3.3.0")
# OpenMMLab currently provides no pinned prebuilt mmcv wheel contract here for
# torch 2.8/cu128. Refuse CPU fallback; require a local CUDA toolkit to build.
if (-not (Get-Command nvcc -ErrorAction SilentlyContinue)) { throw "MMCV for torch 2.8 CUDA 12.8 requires a CUDA toolkit (nvcc) for source build; install a matching toolkit, then rerun." }
$env:FORCE_CUDA = "1"
Invoke-Checked { & .venvs/rtmdet/Scripts/python.exe -m pip install --no-binary mmcv "mmcv==2.2.0" } "build CUDA MMCV 2.2.0"
Push-Location third_party/D-FINE
Invoke-Checked { & ..\..\.venvs\dfine\Scripts\python.exe -c "import torch, torchvision; from src.core import YAMLConfig; assert torch.__version__ == '2.8.0+cu128'; assert torchvision.__version__ == '0.23.0+cu128'; assert torch.version.cuda == '12.8'; assert torch.cuda.is_available(); assert 'RTX 5080' in torch.cuda.get_device_name(0)" } "verify pinned D-FINE CUDA environment"
Pop-Location
Invoke-Checked { & .venvs/rtmdet/Scripts/python.exe -c "import torch, torchvision, mmengine, mmcv, mmdet; assert torch.__version__ == '2.8.0+cu128'; assert torchvision.__version__ == '0.23.0+cu128'; assert torch.version.cuda == '12.8'; assert torch.cuda.is_available(); assert 'RTX 5080' in torch.cuda.get_device_name(0); assert mmengine.__version__ == '0.10.7'; assert mmcv.__version__ == '2.2.0'; assert mmdet.__version__ == '3.3.0'" } "verify pinned MMDetection CUDA environment"
if ($LASTEXITCODE -ne 0) { throw "Pinned CPU detector environment import/version verification failed; inspect the venv package constraints." }
