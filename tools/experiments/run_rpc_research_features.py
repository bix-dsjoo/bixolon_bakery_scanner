"""Materialize verified RPC oracle features outside the repository."""

from __future__ import annotations

import argparse
from pathlib import Path

from bakery_scanner.experiments.rpc_manifest import RpcDatasetContract, load_rpc_index
from bakery_scanner.experiments.rpc_research_worker import ResearchArtifacts, extract_oracle_features


_RPC_ROOT = Path(r"C:\workspace\archive")
_RUNS_ROOT = Path(r"C:\workspace\rpc_fewshot_runs")
_DINO_PATH = Path(
    r"C:\workspace\bixolon_bakery_scanner\models\dinov3_vits16_15plus5_v1\dinov3_vits16_pretrain_lvd1689m-08c60483.pth"
)
_REPVIT_PATH = Path(r"C:\workspace\rpc_fewshot_runs\20260803-stage1-prep\artifacts\model.safetensors")


def run(output: Path) -> Path:
    destination = Path(output).resolve()
    root = _RUNS_ROOT.resolve()
    if not destination.is_relative_to(root):
        raise ValueError(f"output must be under {root}")
    index = load_rpc_index(RpcDatasetContract.default(), _RPC_ROOT)
    artifacts = ResearchArtifacts.from_paths(_REPVIT_PATH, _DINO_PATH)
    return extract_oracle_features(index, artifacts, destination)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        print(run(args.output))
    except (OSError, ValueError, FileExistsError) as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
