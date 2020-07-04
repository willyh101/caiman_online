"""Backend for handling online analysis of data from caiman."""

import numpy as np
from glob import glob
import h5py
import caiman as cm
# from caiman.source_extraction.cnmf import cnmf as cnmf
import pandas as pd
from scipy.stats.mstats import zscore
import json

def load_and_parse_json(path):
    with open(path, 'r') as file:
        data_json = json.load(file)
        out = dict(dff = np.array(data_json['dff']),
                   C = np.array(data_json['C']),
                   splits = np.array(data_json['splits']), 
                   centers = np.array(data_json['center']))
    return out


def load_data(caiman_data_path):
    with h5py.File(caiman_data_path) as f:
        traces = f['estimates']['C'][()]
        # dff = f['estimates']['F_dff'][()]
        # splits = f['splits'][()]
    return traces

def load_as_obj(caiman_data_path):
    return cm.source_extraction.cnmf.cnmf.load_CNMF(caiman_data_path)

def make_trialwise(traces, splits):
    """Returns trial x cell x time."""
    traces = np.split(traces, splits[:-1], axis=1)
    shortest = min([s.shape[1] for s in traces])
    return np.array([a[:, :shortest] for a in traces])

def do_pre_dfof(traces, dfof_method, do_zscore, period=200):
    """do fluorescence calculations that should occur before chopping into PSTHS
    This occurs for percentile, rolling_percentile, and z scoring.
    """
    
    if dfof_method == 'percentile':
        f0=np.nanpercentile(traces,30, axis=1)
        f0 = np.reshape(f0,(f0.shape[0],1))
        traces = (traces-f0)/f0
    if dfof_method == 'rolling_percentile':
        f0s = pd.DataFrame(np.transpose(traces)).rolling(period, min_periods=1,center=True).quantile(.20)
        f0s = np.transpose(f0s.values)
        traces = (traces-f0s)/f0s
    if do_zscore:
        traces = zscore(traces, axis=1)
    return traces

def find_com(A, dims, x_1stPix):
    XYcoords= cm.base.rois.com(A, *dims)
    XYcoords[:,1] = XYcoords[:,1] + x_1stPix #add the dX from the cut FOV
    i = [1, 0]
    return XYcoords[:,i] #swap them