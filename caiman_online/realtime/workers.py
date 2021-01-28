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
        
        
    def init_online(self, mmap_file):
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
                
                
        # def process_frame_verbose(self, frame):
    #     t = tic()
    #     frame = self.acid.mc_next(self.t, frame)
    #     mt = toc(t)
    #     self.t_motion.append(mt)
    #     t2 = tic()
    #     self.acid.fit_next(self.t, frame.ravel(order='F'))
    #     ft = toc(t2)
    #     self.t_fit.append(ft)
    #     self.t += 1

    #     tt = mt + ft
    #     if tt < self.realtime:
    #         print('Realtime:  \x1b[32mTrue\x1b[0m', end=' \r', flush=True)
    #     else:
    #         print('Realtime:  \x1b[31mFalse\x1b[0m', end=' \r', flush=True)
            
    # def process_frame(self, frame):
    #     """Applies motion correction and CNMF fit."""
    #     frame = self.acid.mc_next(self.t, frame)
    #     self.acid.fit_next(self.t, frame.ravel(order='F'))

    # def process_frame_from_queue_verbose(self):
    #     while True:
    #         frame = self.q.get()
    #         if isinstance(frame, np.ndarray):
    #             tt = tic()
    #             frame = self.acid.mc_next(self.t, frame)
    #             self.acid.fit_next(self.t, frame.ravel(order='F'))
    #             t2 = toc(tt)
    #             if t2 < self.realtime:
    #                 print(f'Frame done in {t2:.3f}s. Realtime:  \x1b[32mTrue\x1b[0m')
    #             else:
    #                 print(f'Frame done in {t2:.3f}s. Realtime:  \x1b[31mFalse\x1b[0m')
    #             self.t += 1
    #         elif isinstance(frame, str):
    #             if frame == 'stop':
    #                 print('Stopping realtime caiman.')
    #                 # self.acid.estimates.A = self.acid.estimates.Ab
    #                 # self.acid.estimates.C = self.acid.estimates.C_on
    #                 # self.acid.estimates.YrA = self.acid.estimates.noisyC-self.acid.estimates.C
    #                 self.acid.estimates.A = self.acid.estimates.Ab
    #                 self.acid.estimates.C = self.acid.estimates.C_on[:self.acid.N]
    #                 self.acid.estimates.YrA = self.acid.estimates.noisyC[:self.acid.N]-self.acid.estimates.C
                    
    #                 out = {
    #                     'C': self.acid.estimates.C.tolist(),
    #                 }
                    
    #                 with open('online.json', 'w') as f:
    #                     json.dump(out, f)
                    
    #                 self.acid.save('online_results.hdf5')
                    
    #                 break
                
    #             else:
    #                 continue
# def process_frame(q, acid, T):
#     while True:
#         tt = tic()
#         frame = q.get()
#         frame = acid.mc_next(T, frame)
#         acid.fit_next(T, frame.ravel(order='F'))
#         ptoc(tt, start_string='Frame Processed in:')