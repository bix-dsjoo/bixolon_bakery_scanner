import os

import pytest


@pytest.mark.gpu
def test_admitted_rtx5080_engines_are_explicitly_required():
    if os.environ.get("BIXOLON_RTX5080_ENGINE_BUNDLE") is None:
        pytest.skip("unverified: BIXOLON_RTX5080_ENGINE_BUNDLE is not configured")
    pytest.fail("external admitted-engine harness is not configured in this checkout")
