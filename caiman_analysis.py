"""Backend for handling online analysis of data from caiman."""

import numpy as np
from glob import glob
import h5py
import caiman as cm
# from caiman.source_extraction.cnmf import cnmf as cnmf
import pandas as pd
from scipy.stats.mstats import zscore
import json
import matplotlib.pyplot as plt

def load_json(path):
    with open(path, 'r') as file:
        data_json = json.load(file)
    return data_json

def make_traces_from_json(path):
    """Short cut for loading a json from path and 
    making it into traces=(trials x cell x time)."""
    data = load_json(path)
    traces = make_trialwise(data['c'], data['splits'])
    return traces

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
    # zscore_data = zscore(c)
    # zscore_data -= zscore_data.min(0, keepdims=True)
    
    # make trialwise -> trials x cell x time
    # traces = make_trialwise(zscore_data, splits)
    c = np.array(c)
    traces = make_trialwise(c, splits)
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
    c_trials = [load_json(j)['c'] for j in jsons]
    s_trials = [load_json(j)['splits'] for j in jsons]

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

def posthoc_dff_and_coords(cm_obj):
    cm_obj.estimates.detrend_df_f()
    dff = cm_obj.estimates.F_dff
    
    coords = cm.utils.visualization.get_contours(cm_obj.estimates.A, dims=cm_obj.dims)
    
    return dff, coords


def extract_cell_locs(cm_obj):
    """
    Get the neuron ID, center-of-mass, and coordinates(countors) of all cells from a caiman object. 
    Loads directly from caiman obj or from a string/path and loads the caiman obj.

    Args:
        cm_obj ([caiman, str]): caiman object or path to caiman object

    Returns:
        pd.DataFrame of data
    """
    
    if isinstance(cm_obj, str):
        cm_obj = load_as_obj(cm_obj)
    cell_coords = cm.utils.visualization.get_contours(cm_obj.estimates.A, dims=cm_obj.dims)
    return pd.DataFrame(cell_coords)
    
def cell_locs_multifile(cm_objs):
    """
    Get mean and variance of cell locations across multiple hdf5 outputs for all cells in 
    each FOV. Calculates across files. Returns mean and variance for each cell in df.

    Args:
        cm_objs (list): list of caiman objects or path to caiman objs to mean over

    Returns:
        pd.DataFrame of cell location data mean and variance grouped by cells
    """
    
    data = [pd.DataFrame(extract_cell_locs(cm_obj)) for cm_obj in cm_objs]
    df = pd.concat(data)
    
    # x and y are flipped here bc rows x cols
    df = pd.concat([df, df.loc[:, 'CoM'].agg(lambda x: x[0]).rename('y')], axis=1)
    df = pd.concat([df, df.loc[:, 'CoM'].agg(lambda x: x[1]).rename('x')], axis=1)
    
    out_df =  df.groupby('neuron_id').agg(['mean', 'var'])
    out_df.columns = out_df.columns.map('_'.join) # flatten
    out_df['sum_var'] = out_df['y_var'] + out_df['x_var']
    
    return out_df.reset_index()
    
# def extract_cell_locs(cm_obj):
#     """
#     Get the center-of-mass and coordinates(countors) of all cells from a caiman object. Loads
#     directly from caiman obj or from a string/path and loads the caiman obj.

#     Args:
#         cm_obj ([caiman, str]): caiman object or path to caiman object

#     Returns:
#         center of mass, coordinates (aka countours/cell edges)
#     """
#     if isinstance(cm_obj, str):
#         cm_obj = load_as_obj(cm_obj)
#     cell_coords = cm.utils.visualization.get_contours(cm_obj.estimates.A, dims=cm_obj.dims)
    
#     coms = np.array([c['CoM'] for c in cell_coords])
#     coords = np.array([c['coordinates'] for c in cell_coords])
#     ids = np.array([c['neuron_id']])
    
#     return coms, coords

# def mean_and_var_locs(cm_objs):
#     """
#     Get mean and variance of cell locations across multiple hdf5 outputs for all cells in 
#     each FOV. Calculates across files. Returns sum variance per target (x.var() + y.var())

#     Args:
#         cm_objs (list): list of caiman objects or path to caiman objs to mean over

#     Returns:
#         mean: np.array (cells x xy)
#         variance: np.array(cells x var)
#     """
    
#     coms = []
#     for c in cm_objs:
#         com_temp, _ = extract_cell_locs(c)
#         coms.append(com_temp)

#     coms = np.array(coms)
#     means = coms.mean(axis=0)
#     varis = coms.var(axis=0).sum(axis=1)

#     return means, varis