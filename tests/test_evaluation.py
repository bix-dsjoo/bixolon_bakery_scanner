from bakery_scanner.contracts import Box
from bakery_scanner.evaluation import evaluate_scans, match_boxes


def test_duplicate_fails_scan_with_complete_recall():
    report = evaluate_scans(
        gt={1: (Box(0, 0, 10, 10),)},
        predictions={1: (Box(0, 0, 10, 10), Box(1, 1, 10, 10))},
        scenarios={1: frozenset({"touching"})},
    )

    assert report.sem_exact == 0.0
    assert report.duplicates == 1
    assert report.misses == 0


def test_matching_maximizes_valid_pairs_before_iou_tie_breaking():
    result = match_boxes(
        (Box(0, 0, 10, 10), Box(20, 0, 10, 10)),
        (Box(0, 0, 10, 10), Box(20, 0, 10, 10)),
        0.5,
    )

    assert result.pairs == ((0, 0), (1, 1))
    assert result.misses == ()
    assert result.false_positives == ()


def test_scenario_strata_are_evaluated_from_same_scan_outcomes():
    report = evaluate_scans(
        gt={1: (Box(0, 0, 10, 10),), 2: (Box(0, 0, 10, 10),)},
        predictions={1: (Box(0, 0, 10, 10),), 2: ()},
        scenarios={1: frozenset({"clean"}), 2: frozenset({"touching"})},
    )

    assert report.sem_exact == 0.5
    assert report.scenarios["clean"].sem_exact == 1.0
    assert report.scenarios["touching"].misses == 1


def test_all_required_iou_thresholds_include_error_counts_and_scenarios():
    report = evaluate_scans(
        gt={1: (Box(0, 0, 10, 10),)},
        predictions={1: (Box(0, 0, 10, 10), Box(0, 0, 10, 10))},
        scenarios={1: frozenset({"touching"})},
    )

    assert report.by_iou[0.50].duplicates == 1
    assert report.by_iou[0.75].duplicates == 1
    assert report.by_iou[0.90].duplicates == 1
    assert report.by_iou[0.90].scenarios["touching"].duplicates == 1
