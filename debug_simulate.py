from glob import glob
import os
import matplotlib as mpl
import matplotlib.pyplot as plt
import seaborn as sns

import numpy as np
import pandas as pd
from caiman_main import SimulateAcq
from utils import remove_artifacts, mm3d_to_img, random_view
from caiman_analysis import load_and_parse_json, process_data

import warnings
warnings.filterwarnings('ignore')

# make a structural image
# can do however you want, just needs to be an image that matches the X dims in image_params (100,400)

mm3d_file = glob('E:/caiman_scratch/template/*.mat')[0]
mm3d_img = mm3d_to_img(mm3d_file, chan=0)

# below should work on any image
structural_image = remove_artifacts(mm3d_img, 100, 400)
structural_image = structural_image[0,:,:] # select for only top plane in image



dxy = (1.5, 1.5) # spatial resolution in x and y in (um per pixel)
max_shift_um = (12., 12.) # maximum shift in um
patch_motion_xy = (25., 25.) # patch size for non-rigid correction in um

image_params = {
    'channels': 2,
    'planes': 3,
    'x_start': 100,
    'x_end': 400,
    'folder': 'E:/caiman_scratch/ori/', # this is where the tiffs are
    'chunk_size': 50, # number of tiffs to do at once
    'structural_img': structural_image
}

caiman_params = {
    'fr': 6,  # imaging rate in frames per second, per plane
    'overlaps': (24, 24),
    'max_deviation_rigid': 3,
    'p': 1,  # deconv 0 is off, 1 is slow, 2 is fast
    'nb': 3,  # background compenents -> nb: 3 for complex
    'decay_time': 1.0,  # sensor tau
    'gSig': (7, 7),  # expected half size of neurons in pixels, very important for proper component detection
    'only_init': False,  # has to be `False` when seeded CNMF is used
    'rf': None,  # half-size of the patches in pixels. Should be `None` when seeded CNMF is used.
    'pw_rigid': True,  # piece-wise rigid flag
    'ssub': 1,
    'tsub': 1,
    'merge_thr': 0.99,
    'num_frames_split': 20,
    'border_nan': 'copy',
    'max_shifts': [int(a/b) for a, b in zip(max_shift_um, dxy)],
    'strides': tuple([int(a/b) for a, b in zip(patch_motion_xy, dxy)])
}

def make_outputs(chunk_size):
    
    mpl.rcParams['savefig.dpi'] = 300 # default resolution for saving images in matplotlib
    mpl.rcParams['savefig.format'] = 'png' # defaults to png for saved images (SVG is best, however)
    mpl.rcParams['savefig.bbox'] = 'tight' # so saved graphics don't get chopped
    
    path = f'E:/caiman_scratch/ori/out/{chunk_size}/'
    
    js = glob(path + '*.json')
    jdat_final = load_and_parse_json(js[-1])
    
    # load all the others
    c_trials = [load_and_parse_json(j)['c'] for j in js[:-1]]
    s_trials = [load_and_parse_json(j)['splits'] for j in js[:-1]]
    s_long = np.hstack(s_trials)
    
    # smoosh all the lists of trials into a big array
    trial_dat = []
    for c,s in zip(c_trials, s_trials):
        out = process_data(c,s)
        trial_dat.append(out)
        
    shortest = min([s.shape[2] for s in trial_dat]) # catch for trials of different legnths
    fewest = min([c.shape[1] for c in trial_dat]) # catch for missing cells
    trial_dat = np.concatenate([a[:, :fewest, :shortest] for a in trial_dat])
    
    # proccess the final data set to compare to    
    final_dat = process_data(jdat_final['c'], s_long)
    
    # generate data
    data = np.reshape(trial_dat, (trial_dat.shape[1], -1)) # flatten
    trials = pd.DataFrame(data)
    data = np.reshape(final_dat, (final_dat.shape[1],-1))
    finals = pd.DataFrame(data)

    
    # framewise corr
    fig, ax = plt.subplots(1,2, figsize=(16,3), gridspec_kw=dict(width_ratios = (2.5,1)), constrained_layout=True)

    all_corr = trials.corrwith(finals, axis=0)
    ax[0].plot(all_corr)
    ax[0].set_ylabel('Correlation')
    ax[0].set_xlabel('Frame')
    ax[0].set_title('Framewise Correlation')
    sns.distplot(all_corr, ax=ax[1], kde_kws=dict(lw=2, color='k'))
    ax[1].set_ylabel('KDE')
    ax[1].set_xlabel('Correlation')

    plt.savefig(path + 'frame corr')
    
    # cell corr
    fig, ax = plt.subplots(1,2, figsize=(16,3), gridspec_kw=dict(width_ratios = (2.5,1)), constrained_layout=True)

    cells = np.random.choice(range(trial_dat.shape[1]), 5)

    idx = np.random.permutation(trials.index)
    trials_p = trials.reindex(idx).reset_index()
    finals_p = finals.reindex(idx).reset_index()

    all_corr = trials_p.corrwith(finals_p, axis=1)
    ax[0].plot(all_corr[all_corr >= 0.995], '.', c='grey')
    ax[0].plot(all_corr[all_corr < 0.995], '.', c='r')
    ax[0].plot(all_corr.loc[cells], '.', c='lime')

    ax[0].set_ylabel('Correlation')
    ax[0].set_xlabel('Cell')
    ax[0].set_title('Cellwise Correlation')
            
    sns.distplot(all_corr, ax=ax[1], kde_kws=dict(lw=2, color='k'))
    ax[1].set_ylabel('KDE')
    ax[1].set_xlabel('Correlation')

    plt.savefig(path + 'cell corr')
    
    # example traces
    fig, ax = plt.subplots(5,2, figsize=(16,12))
    colors = ['royalblue', 'seagreen', 'firebrick', 'darkorange', 'darkviolet']

    for i in range(5):
        ax[i,0].plot(trial_dat[:,cells[i],:].flatten(), c=colors[i])
        ax[i,1].plot(final_dat[:,cells[i],:].flatten(), c=colors[i])

    [a.set_ylabel('zdf (from C)') for a in ax[:,0]]
    [a.set_xlabel('Frame Number') for a in ax[-1,:]]
    ax[0,0].set_title('Trial Data')
    ax[0,1].set_title('Final Data')

    plt.savefig(path + 'ex compare')
    
    
    # example trace short
    fig, ax = plt.subplots(5,2, figsize=(16,12))
    
    for i in range(5):
        tdat = random_view(trial_dat[:,cells[i],:].flatten(), 100, 2)
        fdat = random_view(final_dat[:,cells[i],:].flatten(), 100, 2)
        ax[i,0].plot(tdat[0])
        ax[i,1].plot(tdat[1])
        ax[i,0].plot(fdat[0])
        ax[i,1].plot(fdat[0])
        ax[i,0].set_ylabel('zdf')
        ax[i,0].set_xlabel('frames')
        ax[i,1].set_ylabel('zdf')
        ax[i,1].set_xlabel('frames')
        
    ax[0,0].set_title('Random slice 1')
    ax[0,1].set_title('Random slice 2 (same cell each row')
    ax[0,0].legend(['chunked', 'whole expt'])
    ax[0,1].legend(['chunked', 'whole expt'])
    plt.savefig(path + 'short compare ex')
    

    # compare
    fig, ax = plt.subplots(5,2, figsize=(12,10), gridspec_kw={'width_ratios':[2,1]}, constrained_layout=True)

    for i in range(5):
        ax[i,0].plot(trial_dat[:,cells[i],:].flatten())
        ax[i,0].plot(final_dat[:,cells[i],:].flatten())
        ax[i,0].set_ylabel('zdf')
        
        
        ax[i,1].scatter(trial_dat[:,cells[i],:].flatten(), final_dat[:,cells[i],:].flatten(), 
                alpha=0.6, edgecolor='none', facecolor=colors[i])
        ax[i,1].plot([trial_dat[:,cells[i],:].flatten().min(),trial_dat[:,cells[i],:].flatten().max()],
                [final_dat[:,cells[i],:].flatten().min(), final_dat[:,cells[i],:].flatten().max()], 
                c='k', lw=2)
        ax[i,1].set_xlabel('chunks zdff')
        ax[i,1].set_ylabel('whole expt zdff')

    ax[-1,0].set_xlabel('Frame Number')
    ax[0,0].legend(['chunks', 'whole expt'])
    plt.savefig(path + 'corr compare')
    

    plt.close('all')


def main(chunk_size):
    expt = SimulateAcq(caiman_params, **image_params)
    try:
        os.mkdir(f'E:/caiman_scratch/ori/out/{chunk_size}')
    except FileExistsError:
        raise FileExistsError('Need to delete the old folders or move them.')
    expt.save_folder = f'E:/caiman_scratch/ori/out/{chunk_size}/'
    expt.chunk_size = chunk_size
    expt.run_fake_expt()
    del expt
    make_outputs(chunk_size)
    
if __name__ == '__main__':
    chunk_sizes_to_do = [5, 6, 7, 8, 10, 12, 15, 17, 20, 25, 30, 50, 75, 100]
    for c in chunk_sizes_to_do:
        main(c)