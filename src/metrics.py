"""Point and interval metrics, as fixed in PROTOCOL.md."""

import numpy as np


def mae(y, yhat):
    return float(np.mean(np.abs(np.asarray(y) - np.asarray(yhat))))


def rmse(y, yhat):
    return float(np.sqrt(np.mean((np.asarray(y) - np.asarray(yhat)) ** 2)))


def coverage(y, lower, upper):
    y = np.asarray(y)
    return float(np.mean((y >= np.asarray(lower)) & (y <= np.asarray(upper))))


def mean_width(lower, upper):
    return float(np.mean(np.asarray(upper) - np.asarray(lower)))
