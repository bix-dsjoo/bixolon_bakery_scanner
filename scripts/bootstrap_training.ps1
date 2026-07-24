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
git -C third_party/D-FINE apply --check ..\..\third_party_patches\dfine_oof_predictions.patch
git -C third_party/D-FINE apply ..\..\third_party_patches\dfine_oof_predictions.patch
Get-PinnedRepository "https://github.com/open-mmlab/mmdetection.git" "third_party/mmdetection" "ecac3a77becc63f23d9f6980b2a36f86acd00a8a"
Get-PinnedRepository "https://github.com/open-mmlab/mmdeploy.git" "third_party/mmdeploy" "3f8604bd72e8e15d06b2e0552fe2fdb8f8de33c4"
py -3.11 -m venv .venvs/dfine
py -3.11 -m venv .venvs/rtmdet
