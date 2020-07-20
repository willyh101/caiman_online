import numpy as np
import scipy.stats as stats


def ci(data, confidence=0.95):
    a = 1.0 * np.array(data)
    n = len(a)
    m = np.mean(a)
    e = stats.sem(a)
    h = se * stats.t.ppf((1 + confidence) / 2., n-1)
    return m, m-h, m+h

# def bootstrap_ci(data, confidence=0.95, nboot=1000):
#     stat = []