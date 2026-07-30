from pathlib import Path

import pytest

from bakery_scanner.e2e.cpu_dataset import (
    _profile_from_name,
    load_cpu_evaluation_samples,
)


@pytest.mark.artifact
def test_cpu_dataset_has_fixed_counts_profiles_and_unique_keys():
    samples = load_cpu_evaluation_samples(Path("."))

    assert len(samples) == 299
    assert sum(len(sample.targets) for sample in samples) == 1406
    assert {profile: sum(s.profile == profile for s in samples) for profile in "EMH"} == {
        "E": 100,
        "M": 99,
        "H": 100,
    }
    assert len({sample.key for sample in samples}) == 299


def test_profile_is_found_by_token_not_fixed_filename_position():
    assert _profile_from_name("g15_e_0302.jpg") == "E"
    assert _profile_from_name("g20_b01_m_0702.jpg") == "M"
    assert _profile_from_name("g20_b02_h_0714.jpg") == "H"
