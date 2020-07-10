"""Backend for handling online analysis of data from caiman."""

import numpy as np
from glob import glob
import h5py
import caiman as cm
# from caiman.source_extraction.cnmf import cnmf as cnmf
import pandas as pd
from scipy.stats.mstats import zscore
import json

def load_json(path):
    with open(path, 'r') as file:
        data_json = json.load(file)
    return data_json

def load_data(caiman_data_path):
    with h5py.File(caiman_data_path) as f:
        traces = f['estimates']['C'][()]
    return traces

def load_as_obj(caiman_data_path):
    return cm.source_extraction.cnmf.cnmf.load_CNMF(caiman_data_path)

def make_trialwise(traces, splits):
    """Returns trial x cell x time."""
    traces = np.split(traces, np.cumsum(splits[:-1]), axis=1)
    shortest = min([s.shape[1] for s in traces])
    return np.array([a[:, :shortest] for a in traces])

def find_com(A, dims, x_1stPix):
    XYcoords= cm.base.rois.com(A, *dims)
    XYcoords[:,1] = XYcoords[:,1] + x_1stPix #add the dX from the cut FOV
    i = [1, 0]
    return XYcoords[:,i] #swap them

def process_data(c, splits):
    # do zscore and subtract off min
    zscore_data = zscore(c)
    zscore_data -= zscore_data.min(0, keepdims=True)
    
    # make trialwise -> trials x cell x time
    traces = make_trialwise(zscore_data, splits)
    
    return traces

def concat_chunked_data(jsons):
    """
    Takes chunks of data and combines them into a numpy array
    of shape trial x cells x time, concatendated over trials, and
    clips the trials at shortest frame number and fewest cells.

    Args:
        jsons (list): list of jsons to process

    Returns:
        trial_dat: 3D numpy array, (trials, cells, time)
    """
    # load and format
    c_trials = [load_and_parse_json(j)['c'] for j in jsons]
    s_trials = [load_and_parse_json(j)['splits'] for j in jsons]

    # smoosh all the lists of trials into a big array
    trial_dat = []
    for c,s in zip(c_trials, s_trials):
        out = process_data(c,s)
        trial_dat.append(out)
    
    # ensure that trials are the same length and have same 
    shortest = min([s.shape[2] for s in trial_dat]) # shortest trial
    fewest = min([c.shape[1] for c in trial_dat]) # fewest cells
    trial_dat = np.concatenate([a[:, :fewest, :shortest] for a in trial_dat])
    
    return trial_dat