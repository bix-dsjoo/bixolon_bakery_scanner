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
    Invoke-Checked { & $Python -m pip install --upgrade "pip==25.1.1" "setuptools==80.9.0" "wheel==0.45.1" } "install packaging tools"
    Invoke-Checked { & $Python -m pip install --index-url https://download.pytorch.org/whl/cpu "torch==2.8.0+cpu" "torchvision==0.23.0+cpu" } "install CPU PyTorch"
    Invoke-Checked { & $Python -m pip install @Packages } "install pinned detector dependencies"
}

Install-CPUEnvironment ".venvs/dfine/Scripts/python.exe" @("-r", "third_party/D-FINE/requirements.txt")
Install-CPUEnvironment ".venvs/rtmdet/Scripts/python.exe" @("mmengine==0.10.7", "mmcv==2.2.0", "mmdet==3.3.0")
Push-Location third_party/D-FINE
Invoke-Checked { & ..\..\.venvs\dfine\Scripts\python.exe -c "import torch, torchvision; from src.core import YAMLConfig; assert torch.__version__ == '2.8.0+cpu'; assert torchvision.__version__ == '0.23.0+cpu'" } "verify pinned D-FINE CPU environment"
Pop-Location
Invoke-Checked { & .venvs/rtmdet/Scripts/python.exe -c "import torch, torchvision, mmengine, mmcv, mmdet; assert torch.__version__ == '2.8.0+cpu'; assert torchvision.__version__ == '0.23.0+cpu'; assert mmengine.__version__ == '0.10.7'; assert mmcv.__version__ == '2.2.0'; assert mmdet.__version__ == '3.3.0'" } "verify pinned MMDetection CPU environment"
if ($LASTEXITCODE -ne 0) { throw "Pinned CPU detector environment import/version verification failed; inspect the venv package constraints." }
