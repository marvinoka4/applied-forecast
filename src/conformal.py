"""Split conformal half-widths, as fixed in PROTOCOL.md."""

import math

import numpy as np


def conformal_rank(n, alpha):
    """The rank k = ceil((n + 1)(1 - alpha)), counted from 1 for the smallest score."""
    return math.ceil((n + 1) * (1 - alpha))


def conformal_halfwidth(scores, alpha):
    """The k-th smallest absolute score, or infinity when k exceeds n."""
    scores = np.sort(np.asarray(scores, dtype=float))
    if np.isnan(scores).any():
        raise ValueError("Calibration scores contain missing values")
    k = conformal_rank(len(scores), alpha)
    if k > len(scores):
        return math.inf
    return float(scores[k - 1])
