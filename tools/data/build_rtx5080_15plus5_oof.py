"""Build immutable 15+5 OOF split identities from the external dataset root."""

from __future__ import annotations

import argparse
from pathlib import Path

from bakery_scanner.data.oof15plus5 import build_oof_folds, write_oof_manifests
from bakery_scanner.data.sku_scene import load_inventory


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=20260803)
    arguments = parser.parse_args()
    inventory = load_inventory(arguments.dataset_root)
    folds = build_oof_folds(inventory, seed=arguments.seed)
    write_oof_manifests(folds, inventory, arguments.output)
    for fold in folds:
        role_sizes = (len(fold.training_scene_ids), len(fold.calibration_scene_ids), len(fold.evaluation_scene_ids))
        if not all(role_sizes):
            raise RuntimeError(f"fold {fold.fold_index} has an empty role")
    print(f"{inventory.scene_count} scenes, {inventory.box_count} boxes, {len(inventory.isolated_by_sku)} SKUs, five disjoint role manifests")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
