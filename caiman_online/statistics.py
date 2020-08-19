import numpy as np
import scipy

def ci(data, confidence=0.95):
    """
    Calculates the confidence intervals for a given 1D dataset. Calculated by multiplying standard
    error of the mean and percent point function (inverse CDF) for a given confidence and sample
    size. Then +/- mean.

    Args:
        data (array-like): 1D array of input data
        confidence (float, optional): CI bounds to use. Defaults to 0.95.

    Returns:
        low and high CI bounds
    """

    mean = np.mean(data)
    err = scipy.stats.sem(data)
    n = data.size
    h = err * scipy.stats.t.ppf((1+confidence)/2, n-1)
    high = mean + h
    low = mean - h
    return low, high

def traces_ci(traces, *args, **kwargs):
    """Does CI for a time series."""
    func = lambda x: ci(x, *args, **kwargs)
    return np.apply_along_axis(func, 0, traces)