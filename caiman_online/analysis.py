"""Backend for handling online analysis of data from caiman."""

import warnings
import numpy as np
import pandas as pd
import scipy.stats as stats
import json
import sklearn
import numpy as np

with warnings.catch_warnings():
    warnings.simplefilter('ignore', category=FutureWarning)
    import caiman as cm

def load_json(path):
    with open(path, 'r') as file:
        data_json = json.load(file)
    return data_json

def load_as_obj(caiman_data_path):
    """hdf5 -> caiman object"""
    return cm.source_extraction.cnmf.cnmf.load_CNMF(caiman_data_path)

def make_traces_from_json(path, *args, **kwargs):
    """
    Short cut for loading a json from path and making it into 
    traces=(trials x cell x time). Passes any args and kwargs to process_data.
    """
    data = load_json(path)
    traces = process_data(data['c'], data['splits'], *args, **kwargs)
    return traces

def make_trialwise(traces, splits):
    """Returns trial x cell x time."""
    traces = np.split(traces, np.cumsum(splits[:-1]).astype(np.uint), axis=1)
    shortest = min([s.shape[1] for s in traces])
    return np.array([a[:, :shortest] for a in traces])

def stim_align_trialwise(traces, times):
    """
    Make stim-aligned PSTHs from trialwise data (eg. trial x cell x time array). The 
    advantage of doing it this way (trialwise) is the trace for each cell gets rolled around
    to the other side of the array, thus eliminating the need for nan padding.

    Args:
        traces (array-like): trial x cell x time array of traces data, typicall from make_trialwise
        times (array-like): list of stim times for each cell, must match exactly, not sure how it
                            handles nans yet...
    """
    psth = np.zeros_like(traces)

    for i in range(traces.shape[0]):
        psth[i,:,:] = np.array([np.roll(cell_trace, amt) for cell_trace, amt in zip(traces[i,:,:], times)])

    return psth

def make_images(caiman_obj):
    Yr, dims, T = cm.load_memmap(caiman_obj.mmap_file)
    return np.reshape(Yr, [T] + list(dims), order='F')

def find_com(A, dims, x_1stPix):
    XYcoords= cm.base.rois.com(A, *dims)
    XYcoords[:,1] = XYcoords[:,1] + x_1stPix #add the dX from the cut FOV
    i = [1, 0]
    return XYcoords[:,i] #swap them

def process_data(c, splits, stim_times=None, normalizer='scale', func=None, *args, **kwargs):
    """
    Processes temporal data (taken from C) by subtracting off min for each cell and then 
    optionally normalizing it on axis=1 (aka cells). Can use minmax (default), zscore, 
    normalize, or scale. See sklearn.preprocessing for more info. Alternatively can pass
    'other' to use a custom function (func) and passes *args and **kwargs to that function.
    Finally, uses splits to make the data trialwise into trial x cells x time numpy array.

    Args:
        c (array-like): temporal data from caiman
        splits (list): file lengths per tiff/trial, taken from memmap file name
        stim_times (array-like): cellwise list of stim times, defaults to None.
        normalizer (str, optional): Method to normalize traces by. Defaults to 'minmax'.
        func (function): if normalizer is 'other', can pass in a function here (don't call)
        *args and **kwargs get passed to func if 'other'
    """
    
    if normalizer == 'other' and func is None:
        raise Exception('You provided normalizer type other but no function')
    if normalizer != 'other' and func is not None:
        warnings.warn('Both named normalizer type and alternate function were provided. Defaulting to named.')
    
    c = np.array(c)
    data = c - c.min(axis=1).reshape(-1,1)
    
    # normalization routines
    if normalizer == 'other':
        normed_data = func(data, *args, **kwargs)
    else:
        norm_routines = {
            'none': data, # nothing done...
            'minmax': sklearn.preprocessing.minmax_scale(data, axis=1), # scaled to min max (not abs)
            'zscore': stats.zscore(data, axis=1), # old fashion zscoring
            'norm': sklearn.preprocessing.normalize(data, axis=1), # L2 norm
            'scale': sklearn.preprocessing.scale(data, axis=1), # mean subtracted, divided by standard dev
        }
        
        normed_data = norm_routines[normalizer]
    
    traces = make_trialwise(normed_data, splits)
    
    if stim_times:
        assert len(stim_times) == c.shape[0] # must have same length/size as the number of cells
        traces = stim_align_trialwise(traces, stim_times)
    
    return traces

def concat_chunked_data(jsons, f_src='c', *args, **kwargs):
    """
    Takes chunks of data and combines them into a numpy array
    of shape trial x cells x time, concatendated over trials, and
    clips the trials at shortest frame number and fewest cells. Args and
    kwargs are passed to process_data.

    Args:
        jsons (list): list of jsons to process
        f_src (str): key to F data to load ('c' or 'dff'). Defaults to 'c'.

    Returns:
        trial_dat: 3D numpy array, (trials, cells, time)
    """
    # load and format
    c_trials = [load_json(j)[f_src] for j in jsons]
    s_trials = [load_json(j)['splits'] for j in jsons]

    # smoosh all the lists of trials into a big array
    trial_dat = []
    for c,s in zip(c_trials, s_trials):
        out = process_data(c, s, *args, **kwargs)
        trial_dat.append(out)
    
    # ensure that trials are the same length and have same 
    shortest = min([s.shape[2] for s in trial_dat]) # shortest trial
    # fewest = min([c.shape[1] for c in trial_dat]) # fewest cells
    # trial_dat = np.concatenate([a[:, :fewest, :shortest] for a in trial_dat])
    try:
        trial_dat = np.concatenate([a[:, :, :shortest] for a in trial_dat])
    except:
        print('WARNING LOST A CELL(S)!!!!')
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
        
    cell_coords = cm.utils.visualization.get_contours(cm_obj.estimates.A, dims=cm_obj.estimates.dims)
    df = pd.DataFrame(cell_coords)
    
     # x and y are flipped here bc rows x cols
    df = pd.concat([df, df.loc[:, 'CoM'].agg(lambda x: x[0]).rename('y')], axis=1)
    df = pd.concat([df, df.loc[:, 'CoM'].agg(lambda x: x[1]).rename('x')], axis=1)
    
    return df

# DEPRECATED
# def cell_locs_multifile(cm_objs):
#     """
#     Get mean and variance of cell locations across multiple hdf5 outputs for all cells in 
#     each FOV. Calculates across files. Returns mean and variance for each cell in df.

#     Args:
#         cm_objs (list): list of caiman objects or path to caiman objs to mean over

#     Returns:
#         pd.DataFrame of cell location data mean and variance grouped by cells
#     """
    
#     data = [pd.DataFrame(extract_cell_locs(cm_obj)) for cm_obj in cm_objs]
#     df = pd.concat(data)
    
#     # x and y are flipped here bc rows x cols
#     df = pd.concat([df, df.loc[:, 'CoM'].agg(lambda x: x[0]).rename('y')], axis=1)
#     df = pd.concat([df, df.loc[:, 'CoM'].agg(lambda x: x[1]).rename('x')], axis=1)
    
#     out_df =  df.groupby('neuron_id').agg(['mean', 'var'])
#     out_df.columns = out_df.columns.map('_'.join) # flatten
#     out_df['sum_var'] = out_df['y_var'] + out_df['x_var']
    
#     return out_df.reset_index()