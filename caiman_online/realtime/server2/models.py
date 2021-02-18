from pathlib import Path
import json

import numpy as np
import scipy.io as sio

from ...analysis import process_data
from ..server import Alert


class Experiment:
    def __init__(self, output_folder, params, 
                 Ain_path=None, num_frames_max=10000):
        
        self.output_folder = Path(output_folder)
        self.params = params
        self.Ain_path = Ain_path
        self.num_frames_max = num_frames_max
        
        self.init_files = None
        self.lengths = []
        
        self.nchannels = None
        self.nplanes = None
        self.fr = None
    
    def __setattr__(self, key, item):
        super().__setattr__(key, item)
        Alert(f'{key} set to {item}')
    
    def process_and_save(self, results):
        c_list = [r['C'] for r in results]
        c_all = np.concatenate(c_list, axis=0)
        out = {
            'c': c_all.tolist(),
            'splits': self.lengths
        }
        
        # first save the raw data in case it fails (concatentated)
        fname = self.output_folder/'raw_data.json'
        with open(fname, 'w') as f:
            json.dump(out, f)
        
        # do proccessing and save trialwise json
        traces = process_data(**out, normalizer='scale')
        out = {
            'traces': traces.tolist()
        }
        fname = self.output_folder/'traces_data.json'
        with open(fname, 'w') as f:
            json.dump(out, f)
            
        # save it as a npy also
        fname = self.output_folder/'traces.npy'
        np.save(fname, c_all)
        fname = self.output_folder/'psths.npy'
        np.save(fname, traces)
        
        # save as matlab
        fname = self.output_folder/'data.mat'
        mat = {
            'tracesCaiman': c_all,
            'psthsCaiman': traces,
            'trialLengths': self.lengths
        }
        sio.savemat(fname, mat)