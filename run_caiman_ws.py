"""
Websocket server for handling communication between ScanImage and Caiman.
Requires websockets (pip install websockets)
"""

import websockets
import asyncio
import json
import warnings
import os
import scipy.io as sio
import warnings
import numpy as np

from glob import glob
from termcolor import cprint

from caiman_main import OnlineAnalysis
from caiman_main import MakeMasks3D
from caiman_analysis import process_data
from wrappers import run_in_executor
from wscomm.alerts import WebSocketAlert


warnings.filterwarnings(
    action='ignore',
    lineno=1969, 
    module='scipy')

warnings.filterwarnings(
    action='ignore',
    lineno=535, 
    module='tensorflow')

class SISocketServer:
    """
    Runs the websocket server for communication with ScanImage. Also maybe will eventually run the 
    live plotting to the DAQ.
    
    ip = IP address to serve on, defaults to 'localhost'
    port = port to serve on, defaults to 5000
    expt = online experiment object
    """
    def __init__(self, ip, port, expt, srv_folder):
        self.ip = ip
        self.port = port
        self.expt = expt
        self.url = f'ws://{ip}:{port}'
        self.srv_folder = srv_folder
        
        self.acqs_done = 0
        self.acqs_this_batch = 0
        self.acq_per_batch = 10
        self.iters = 0
        self.expt.batch_size = self.acq_per_batch
        
        self.trial_lengths = []
        self.traces = []
        self.stim_times = []
        self.stim_conds = []

        self.data = []
        
        cprint(f'[INFO] Starting WS server ({self.url})...', 'yellow', end = ' ')
        self.start_server()
        
    def start_server(self):
        """
        Starts the WS server.
        """
        serve = websockets.serve(self.handle_incoming, self.ip, self.port)
        asyncio.get_event_loop().run_until_complete(serve)
        cprint('ready to launch!', 'yellow')
        self.loop = asyncio.get_event_loop()
        self.loop.run_forever()
    
    async def handle_incoming(self, websocket, path):
        """
        Handles data incoming over the websocket and dispatches 
        to specific handle functions.
        """
        
        data = await websocket.recv()
        data = json.loads(data)
        
        if isinstance(data, dict):
            # handle the data if it's a dict
            # kind = data['kind']
            self.handle_json(data)
             
        elif isinstance(data, str):
            # handle the data for simple strings
            if data == 'acq done':
                await self.handle_acq_done()
            
            elif data == 'session done':
                self.handle_session_end()
            
            elif data == 'uhoh':
                print('uhoh!')
                self.loop.stop()
                
            elif data == 'hi':
                print('SI computer says hi!')
                
            elif data == 'wtf':
                print('BAD ERROR IN CAIMAN_MAIN (self.everything_is_ok == False)')
                print('quitting...')
                self.loop.stop()

            elif data == 'reset':
                self.acqs_done = 0
            
            else:
                # event not specified
                print('unknown event!')
                print(data)
                
        else:
            # otherwise we don't know what it is
            print('unknown str data!')
            print(data)
    
    def handle_json(self, data):
        kind = data['kind']
        
        if kind == 'setup':
            WebSocketAlert('Recieved setup data from SI', 'success')
            self.expt.channels = int(data['nchannels'])
            print(f'nchannels set to: {self.expt.channels}')
            self.expt.planes = int(data['nplanes'])
            print(f'nchannels set to: {self.expt.planes}')
            self.expt.opts.change_params(dict(fr = data['frameRate']))
            print(f'frame rate set to: {self.expt.opts.data["fr"]}')

        elif kind == 'daq_data':
            cprint('[INFO] Recieved trial data from DAQ', 'yellow')
            # appends in a trialwise manner
            self.stim_conds.append(data['condition'])
            self.stim_times.append(data['stim_times'])
            print(self.stim_conds)
            
        else:
            print('unknown json data!')
            print(data)
          
    async def handle_acq_done(self):
        """
        Handles the SI 'acq done' message event. Send when a tiff/acquistion is completed. Calls
        a new caiman fit after acq_per_batch is satisfied.
        """
        self.update()
        print(f'SI says acq done. ({self.acqs_this_batch})')
        
        if self.acqs_this_batch >= self.acq_per_batch:
            self.acqs_this_batch = 0

            WebSocketAlert('Starting caiman fit', 'info')
            await self._do_next_group()

            # save the data
            self.data.append(self.expt.data_this_round)
            # self.trial_lengths.append(self.expt.splits)
            # self.traces.append(self.expt.C.tolist())
                
            # update data and send it out
            # self.trial_lengths.append(self.expt.splits)
            # self.traces.append(self.expt.C.tolist())
            
            # self.handle_outgoing()
    
    @run_in_executor        
    def _do_next_group(self):
        self.expt.do_next_group()
             
    def handle_session_end(self):
        """
        Handles the SI 'session done' message event. Sent when a loop/grad is completed. Calls the 
        final caiman fit on all the data.
        """
        if self.iters == 0:
            self.loop.stop()
        else:
            self.update()
            WebSocketAlert('SI says session ended.', 'warn')
            print('Saving data...')
            self.save_trial_data_mat()
            # print('Starting final caiman fit...')
            # self.expt.do_final_fit()
            print('quitting...')
            self.loop.stop()
                
    def update(self):
        """
        Updates acq counters and anything else that needs to keep track of trial counts.
        """
        # if self.acqs_done == 0:
        #     self.expt.segment_mm3d()
            # self.expt.segment() for if you want to provide the structural image manually
        # else:
            # get data from caiman main

        self.acqs_done += 1
        self.acqs_this_batch += 1
        self.iters += 1

    # def save_trial_data_mat(self):
    #     print('processing and saving trial data')
    #     dat = self.load_and_format()
    #     psths = process_data(self.traces, self.trial_lengths)
    #     out = dict(psths = psths)
    #     save_path = os.path.join(self.srv_folder, f'cm_out_plane{self.expt.plane}_iter_{self.iters}.mat')
    #     sio.savemat(save_path, out)

    def save_trial_data_mat(self):
        fit_data = []
        len_data = []
        dff_data = []
        loc_data = []
        # THIS IS MESSED UP, RETURNING: TIME X TRIALS, NOT CELLS X TIME
        for acq in self.data:
            for plane in acq:
                fit_data.append(np.array([a for a in plane['c']]))
                # len_data.append(np.array([a for a in plane['splits']]))
                dff_data.append(np.array([a for a in plane['dff']]))
                # coords = json.loads(plane['coords'])['CoM']
                # coords = {int(key):value for key, value in coords.items()}
                # loc_data.append(np.array(list(coords.values())))
            len_data.append(np.array([a for a in plane['splits']]))
            coords = json.loads(plane['coords'])['CoM']
            coords = {int(key):value for key, value in coords.items()}
            loc_data.append(np.array(list(coords.values())))
        len_data = np.concatenate(len_data)/(self.expt.planes * self.channels)
        psths = process_data(fit_data, len_data)
        out = dict(psths = psths)
        save_path = os.path.join(self.srv_folder, f'cm_out_plane{self.expt.plane}_iter_{self.iters}.mat')
        sio.savemat(save_path, out)

if __name__ == '__main__':
    # mm3d = MakeMasks3D(template_image, channels, planes, x_start, x_end)
    expt = OnlineAnalysis(caiman_params, **image_params)
    expt.make_templates(template_path)
    srv = SISocketServer(ip, port, expt, srv_folder)
    # expt.structural_image = image