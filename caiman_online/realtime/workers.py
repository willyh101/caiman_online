import json
import os
import logging
from queue import Queue
from caiman.source_extraction.cnmf import estimates

import numpy as np
from caiman.source_extraction import cnmf
from caiman.source_extraction.cnmf.params import CNMFParams

from ..utils import make_ain

log = logging.getLogger('caiman_online')
        
class RealTimeWorker:
    def __init__(self, q, plane, params_dict, Ain_path, max_num_frame = 10000):
        """
        [summary]

        Args:
            q (Queue): queue that the worker will pull from
            plane (int): z-plane to process (as an index)
            params_dict (dict): caiman settings dictionary used to make params object
            Ain_path (str, optional): path to makeMasks3D file. Defaults to None.
            max_num_frame (int, optional): the longest the experiment could run for in franes/plane. Defaults to 10000.
        """

        self.q = q
        self.plane = plane
        self.params_dict = params_dict
        self.max_frame_buffer = max_num_frame
        
        # ! fix this to function like other workers
        os.chdir('e:/caiman_scratch/realtime')
        
        if Ain_path is not None:
            self.Ain = make_ain(Ain_path, self.plane, 120, 392)
            self.acid.estimates.A = self.Ain
        else:
            self.Ain = None 
        
        # not yet set (requires init_online)
        self.frame_start = None
        self.t = None
        
        
    def initialize(self, mmap_file):
        self.params_dict['fnames'] = mmap_file
        params = CNMFParams(params_dict=self.params_dict)
        self.acid = cnmf.online_cnmf.OnACID(dview=None, params=params)
        log.info('Initializing CaImAn OnACID.')
        self.acid.initialize_online(T=self.max_frames)
        # ? can self.t be captured from self.acid after the init?
   

    def process_frame_from_queue(self):
        while True:
            frame = self.q.get()
            
            if isinstance(frame, np.ndarray):
                print(f'Processing frame: {self.t}', end=' \r', flush=True)
                frame = self.acid.mc_next(self.t, frame)
                self.acid.fit_next(self.t, frame.ravel(order='F'))
                self.t += 1
                
            elif isinstance(frame, str):
                if frame == 'stop':
                    print('Stopping realtime caiman....')
                    print('Getting final results...')
                    # self.acid.estimates.A = self.acid.estimates.Ab[:, self.acid.params.get('init', 'nb'):]
                    # self.acid.estimates.b = self.acid.estimates.Ab[:, :self.acid.params.get('init', 'nb')].toarray()
                    # self.acid.estimates.C = self.acid.estimates.C_on[self.acid.params.get('init', 'nb'):self.acid.M, self.frame_start:self.t]
                    # self.acid.estimates.f = self.acid.estimates.C_on[:self.acid.params.get('init', 'nb'), self.frame_start:self.t]
                    # noisyC = self.acid.estimates.noisyC[self.acid.params.get('init', 'nb'):self.acid.M, self.frame_start:self.t]
                    # self.acid.estimates.YrA = noisyC - self.acid.estimates.C
                    (self.acid.estimates.A, 
                     self.acid.estimates.b, 
                     self.acid.estimates.C,
                     self.acid.estimates.f,
                     self.acid.estimates.noisyC,
                     self.acid.estimates.YrA) = self.update_model()
                    
                    self.acid.estimates.detrend_df_f()
                    
                    out = {
                        'c': self.acid.estimates.C.tolist(),
                    }
                    
                    with open('online.json', 'w') as f:
                        json.dump(out, f)
                    
                    self.acid.save('online_results.hdf5')
                    
                    print('done!')
                    
                    break
                else:
                    continue
                
    def update_model(self):
        # A = spatial component (cells)
        A = self.acid.estimates.Ab[:, self.acid.params.get('init', 'nb'):]
        # b = background components (neuropil)
        b = self.acid.estimates.Ab[:, :self.acid.params.get('init', 'nb')].toarray()
        # C = denoised trace for cells
        C = self.acid.estimates.C_on[self.acid.params.get('init', 'nb'):self.acid.M, self.frame_start:self.t]
        # f = denoised neuropil signal
        f = self.acid.estimates.C_on[:self.acid.params.get('init', 'nb'), self.frame_start:self.t]
        # nC a.k.a noisyC is ??
        nC = self.acid.estimates.noisyC[self.acid.params.get('init', 'nb'):self.acid.M, self.frame_start:self.t]
        # YrA = signal noise 
        YrA = nC - self.acid.estimates.C
        
        return A, b, C, f, nC, YrA


def load_init(file_path):
    """
    Concatenate a few tiffs for caiman to seed off of for online processing.

    Args:
        file_path (str): path to the tiffs to make the init
    """
    
    log.debug('Making an init...')
    file_path = Path(file_path)
    init_tiffs = list(file_path.glob('*.tif'))[:20]
    mov = tiffs2array(init_tiffs,
                      x_slice=slice(120,392),
                      y_slice=slice(0,512),
                      t_slice=slice(PLANE2USE*NCHANNELS,-1,NCHANNELS*NPLANES)
                      )
    log.info(f'Movie dims are {mov.shape}')
    m = cm.movie(mov.astype('float32'))
    fname_init = m.save('init.mmap', order='C')
    return fname_init