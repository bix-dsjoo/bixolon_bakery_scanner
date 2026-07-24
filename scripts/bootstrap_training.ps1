$ErrorActionPreference = "Stop"

function Get-PinnedRepository([string]$Url, [string]$Destination, [string]$Commit) {
    if (Test-Path $Destination) {
        $head = git -C $Destination rev-parse HEAD
        if ($head -ne $Commit) { throw "Pinned checkout mismatch: $Destination is $head, expected $Commit" }
        return
    }
    git clone $Url $Destination
    git -C $Destination checkout $Commit
}

Get-PinnedRepository "https://github.com/Peterande/D-FINE.git" "third_party/D-FINE" "7fe2f8889f0b7b817f20c315b40fc15a4fb64ae6"
$DFinePatch = "..\..\third_party_patches\dfine_oof_predictions.patch"
git -C third_party/D-FINE apply --reverse --check $DFinePatch 2>$null
if ($LASTEXITCODE -ne 0) {
    git -C third_party/D-FINE apply --check $DFinePatch
    git -C third_party/D-FINE apply $DFinePatch
}
Get-PinnedRepository "https://github.com/open-mmlab/mmdetection.git" "third_party/mmdetection" "ecac3a77becc63f23d9f6980b2a36f86acd00a8a"
Get-PinnedRepository "https://github.com/open-mmlab/mmdeploy.git" "third_party/mmdeploy" "3f8604bd72e8e15d06b2e0552fe2fdb8f8de33c4"
py -3.11 -m venv .venvs/dfine
py -3.11 -m venv .venvs/rtmdet

function Install-CPUEnvironment([string]$Python, [string[]]$Packages) {
    & $Python -m pip install --upgrade "pip==25.1.1" "setuptools==80.9.0" "wheel==0.45.1"
    & $Python -m pip install --index-url https://download.pytorch.org/whl/cpu "torch==2.8.0+cpu" "torchvision==0.23.0+cpu"
    & $Python -m pip install @Packages
}

Install-CPUEnvironment ".venvs/dfine/Scripts/python.exe" @("-r", "third_party/D-FINE/requirements.txt")
Install-CPUEnvironment ".venvs/rtmdet/Scripts/python.exe" @("mmengine==0.10.7", "mmcv==2.2.0", "mmdet==3.3.0")
& .venvs/dfine/Scripts/python.exe -c "import torch, torchvision; import src; print(torch.__version__, torchvision.__version__)"
& .venvs/rtmdet/Scripts/python.exe -c "import torch, torchvision, mmengine, mmcv, mmdet; print(torch.__version__, mmengine.__version__, mmcv.__version__, mmdet.__version__)"
if ($LASTEXITCODE -ne 0) { throw "Pinned CPU detector environment import/version verification failed; inspect the venv package constraints." }
