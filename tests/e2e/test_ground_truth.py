from pathlib import Path

import pytest

from bakery_scanner.config import ScannerConfig
from bakery_scanner.e2e.ground_truth import load_source_sku_ground_truth


def test_source_sku_loader_rejects_staging_and_sku_annotation_count_mismatch():
    root = Path(__file__).resolve().parents[2]
    with pytest.raises(ValueError, match="source SKU annotations contain 1409 boxes but staging expects 1410"):
        load_source_sku_ground_truth(
            ScannerConfig.load(root / "configs" / "box_system.yaml"),
            classes_path=root / "datasets" / "classes.json",
        )
