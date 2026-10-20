import math

import numpy as np
import pytest

from src.conformal import conformal_halfwidth, conformal_rank


def test_protocol_ranks_for_56_calibration_days():
    assert conformal_rank(56, 0.20) == 46
    assert conformal_rank(56, 0.05) == 55


def test_halfwidth_is_kth_smallest_score_regardless_of_order():
    scores = np.arange(1, 57, dtype=float)[::-1]  # 56 down to 1
    assert conformal_halfwidth(scores, 0.20) == 46.0
    assert conformal_halfwidth(scores, 0.05) == 55.0


def test_too_few_scores_give_an_infinite_interval():
    assert conformal_halfwidth(np.arange(10.0), 0.05) == math.inf


def test_missing_scores_are_rejected():
    with pytest.raises(ValueError):
        conformal_halfwidth([1.0, np.nan, 3.0], 0.2)


@pytest.mark.parametrize("alpha", [0.20, 0.05])
def test_marginal_coverage_holds_for_exchangeable_scores(alpha):
    rng = np.random.default_rng(42)
    trials = 4000
    hits = 0
    for _ in range(trials):
        draws = np.abs(rng.standard_t(df=4, size=57))
        hits += draws[56] <= conformal_halfwidth(draws[:56], alpha)
    # Split conformal guarantees coverage of at least 1 - alpha.
    assert hits / trials >= 1 - alpha - 0.015
