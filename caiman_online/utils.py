"""
Generic utilities for online analysis.
"""

import numpy as np
import scipy.io as sio
import time
from glob import glob
import os
from ScanImageTiffReader import ScanImageTiffReader
import tifffile

def mm3d_to_img(path, chan=0):
    """
    Gets the img data from a makeMasks3D file and flips it into a (512,512,z-depth) ndarray.

    Args:
        path (str): location of matlab file
        chan (int, optional): RGB channel to index into. Defaults to 0 (aka 'red').

    Returns:
        ndarray: (512,512,z-depth) image
    """
    mat = sio.loadmat(path)
    img = mat['img'].squeeze()

    img = np.array([i[:,:,chan] for i in img])

    return img

def load_sources(path):
    mat = sio.loadmat(path)
    srcs = mat['sources'].squeeze()
    srcs = np.array([i.max(2) for i in srcs])
    return srcs

def make_ain(path, plane, left_crop, right_crop):
    mat = sio.loadmat(path)
    srcs = mat['sources'].squeeze()
    
    srcs = srcs[plane]
    srcs = srcs[:, left_crop:right_crop, :]
    
    A = np.zeros((np.prod(srcs.shape[:2]), srcs.shape[2]), dtype=bool)
    
    for i in range(srcs.shape[2]):
        A[:,i] = srcs[:,:,i].flatten('F')
        
    print(f'Plane {plane}: Found {srcs.shape[2]} sources from MM3D...')
        
    return A
    

def remove_artifacts(img, left_crop, right_crop):
    """
    Clips off the stim laser artifacts from the mean tiff.

    Args:
        img (array): n,512,512 image where n is planes
    """
    
    return img[:, :, left_crop:right_crop]

def tic():
    """Records the time in highest resolution possible for timing code."""
    return time.perf_counter()

def toc(tic):
    """Returns the time since 'tic' was called."""
    return time.perf_counter() - tic

def ptoc(tic, start_string='Time elapsed:', end_string='s'):
    """
    Print a default or custom print statement with elapsed time. Both the start_string
    and end_string can be customized. Autoformats with single space between start, time, 
    stop. Returns the time elapsed.

    Format -> 'start_string' + 'elapsed time in seconds' + 'end_string'.
    Default -> start_string = 'Time elapsed:', end_string = 's'.
    """
    t = toc(tic)
    pstring = ' '.join([start_string, f'{t:.4f}', end_string])
    print(pstring)
    return t

def cleanup(folder, filetype, verbose=True):
    files = glob(folder + '*.' + filetype)
    if files:
        for f in files:
            os.remove(f)
            if verbose:
                print('Removed ' + f)
    else:
        if verbose:
            print('Nothing to remove!')

def crop_movie(mov_path, x_slice, t_slice):
    with ScanImageTiffReader(mov_path) as reader:
        data = reader.data()
        data = data[t_slice, :, x_slice]
    return data

def crop_and_save_multiplane(mov_path, x_slice, n_planes, n_chans):
    skip = n_planes * n_chans
    for mov in mov_path:
        for plane in list(range(n_planes)):
            cropped_mov = crop_movie(mov_path, x_slice, slice(n_chans*plane, -1, skip))
            tif_name = mov_path.split('.')[0] + '_plane' + str(plane) + '.tif'
            tifffile.imsave(tif_name, cropped_mov)
            
def get_nchannels(file):
    with ScanImageTiffReader(file) as reader:
        metadata = reader.metadata()
    channel_pass_1 = metadata.split('channelSave = [')
    if len(channel_pass_1)==1:
        nchannels = 1
    else:
        nchannels = len(metadata.split('channelSave = [')[1].split(']')[0].split(';'))
    return nchannels

def get_nvols(file):
    with ScanImageTiffReader(file) as reader:
        metadata = reader.metadata()
    if metadata.split('hStackManager.zs = ')[1][0]=='0':
        return 1
    nvols = len(metadata.split('hStackManager.zs = [')[1].split(']')[0].split(' '))
    return nvols

def random_view(arr, length, n=1):
    """
    Generates a random view from an (1D) array without shuffling any of the data.

    Args:
        arr (np.array): array to use
        length (int): length of slice to take
        n (int): number of slices to return
        
    Returns:
        random views into array arr.
    """
    assert arr.ndim == 1, 'Must pass 1D array.'
    
    out = []
    for i in range(n):
    # choose random starting point
        start_idx = np.random.randint(arr.size - length)
        rand_slice = arr[start_idx:start_idx + length]
        out.append(rand_slice)
    
    return np.array(out)
    
    
    
    