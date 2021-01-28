import json
import os
from queue import Queue

import numpy as np
from caiman.source_extraction import cnmf
from caiman.source_extraction.cnmf.params import CNMFParams

from ..utils import make_ain
        
class RealTimeWorker:
    def __init__(self, q, plane, params_dict, Ain_path, max_num_frame = 10000):
        """
        [summary]

        Args:
            q (Queue): [description]
            plane (int): [description]
            params_dict (dict): [description]
            Ain_path (str, optional): [description]. Defaults to None.
            max_num_frame (int, optional): [description]. Defaults to 10000.
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
            
        self.frame_start = 255
        self.t = 255
        
        
    def init_online(self):
        params = CNMFParams(params_dict=self.params_dict)
        self.acid = cnmf.online_cnmf.OnACID(dview=None, params=params)
        self.acid.initialize_online(T=self.max_frames)
   

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
                    self.acid.estimates.A = self.acid.estimates.Ab[:, self.acid.params.get('init', 'nb'):]
                    self.acid.estimates.b = self.acid.estimates.Ab[:, :self.acid.params.get('init', 'nb')].toarray()
                    self.acid.estimates.C = self.acid.estimates.C_on[self.acid.params.get('init', 'nb'):self.acid.M, self.frame_start:self.t]
                    self.acid.estimates.f = self.acid.estimates.C_on[:self.acid.params.get('init', 'nb'), self.frame_start:self.t]
                    noisyC = self.acid.estimates.noisyC[self.acid.params.get('init', 'nb'):self.acid.M, self.frame_start:self.t]
                    self.acid.estimates.YrA = noisyC - self.acid.estimates.C
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