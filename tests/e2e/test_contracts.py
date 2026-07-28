import math

import pytest

from bakery_scanner.contracts import Box
from bakery_scanner.e2e.contracts import FinalObject


def test_unknown_final_object_requires_three_distinct_ranked_skus():
    with pytest.raises(ValueError, match="three distinct"):
        FinalObject(
            box=Box(10, 20, 30, 40),
            sku_id=None,
            confidence=0.4,
            decision_path="unknown_top3",
            top3=(6, 6, 19),
        )


def test_sku_final_object_rejects_unknown_path_and_top3():
    with pytest.raises(ValueError, match="SKU decision"):
        FinalObject(
            box=Box(10, 20, 30, 40),
            sku_id=6,
            confidence=0.9,
            decision_path="unknown_top3",
            top3=(6, 5, 19),
        )


def test_final_object_rejects_non_finite_confidence():
    with pytest.raises(ValueError, match="confidence"):
        FinalObject(
            box=Box(10, 20, 30, 40),
            sku_id=6,
            confidence=math.nan,
            decision_path="repvit_direct",
            top3=(),
        )
