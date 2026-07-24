param([Parameter(Mandatory = $true)][string]$Config = "configs/box_system.yaml")
$ErrorActionPreference = "Stop"
# Invokes only local pinned environments. This script never creates physical data.
& .venvs/dfine/Scripts/python.exe third_party/D-FINE/train.py --config $Config
& .venvs/rtmdet/Scripts/python.exe third_party/mmdetection/tools/train.py configs/upstream/rtmdet_tiny_bread.py
