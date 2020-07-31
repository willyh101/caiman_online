"""
Websocket server for handling communication between ScanImage and Caiman.
Requires websockets (pip install websockets)
"""

import websockets
import asyncio
import json
import warnings
import os
from glob import glob
from termcolor import cprint
from caiman_main import OnlineAnalysis
from caiman_main import MakeMasks3D
from caiman_analysis import process_data
from wrappers import run_in_executor
import scipy.io as sio

import warnings
warnings.filterwarnings(
    action='ignore',
    lineno=1969, 
    module='scipy')

warnings.filterwarnings(
    action='ignore',
    lineno=535, 
    module='tensorflow')

ip = 'localhost'
port = 5002
srv_folder = 'F:/caiman_out' # path to caiman data output folder on server
template_path = glob('D:/caiman_temp/template/*.mat')[0] # path to mm3d file

# image = np.array of mean image that is serving as structural template, needs to be 2D cropped size x 512 mean image
# image_path = path/to/image/to/load (must already be cropped to match x_start:x_end)

dxy = (1.5, 1.5) # spatial resolution in x and y in (um per pixel)
max_shift_um = (12., 12.) # maximum shift in um
patch_motion_xy = (100., 100.) # patch size for non-rigid correction in um

image_params = {
    'channels': 2,
    'planes': 3,
    'x_start': 100,
    'x_end': 400,
    'folder': 'D:/caiman_temp/', # this is where the tiffs are, make a sub-folder named out to store output data
}

caiman_params = {
    'fr': 6.36,  # imaging rate in frames per second, per plane
    'overlaps': (24, 24),
    'max_deviation_rigid': 3,
    'p': 1,  # deconv 0 is off, 1 is slow, 2 is fast
    'nb': 2,  # background compenents -> nb: 3 for complex
    'decay_time': 1.0,  # sensor tau
    'gSig': (5, 5),  # expected half size of neurons in pixels, very important for proper component detection
    'only_init': False,  # has to be `False` when seeded CNMF is used
    'rf': None,  # half-size of the patches in pixels. Should be `None` when seeded CNMF is used.
    'pw_rigid': True,  # piece-wise rigid flag
    'ssub': 1,
    'tsub': 1,
    'merge_thr': 0.9,
    'num_frames_split': 20,
    'border_nan': 'copy',
    'max_shifts': [int(a/b) for a, b in zip(max_shift_um, dxy)],
    'strides': tuple([int(a/b) for a, b in zip(patch_motion_xy, dxy)])
}

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
        self.acq_per_batch = 3
        self.iters = 0
        self.expt.batch_size = self.acq_per_batch
        
        self.trial_lengths = []
        self.traces = []
        self.stim_times = []
        self.stim_conds = []
        
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
            cprint('[INFO] Recieved setup data from SI', 'yellow')
            self.expt.channels = int(data['nchannels'])
            self.expt.planes = int(data['nplanes'])
            
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
            cprint('[INFO] Starting caiman fit...', 'yellow')
            await self.do_next_group()

            # save the data
            self.trial_lengths.append(self.expt.splits)
            self.traces.append(self.expt.C.tolist())
                
            # update data and send it out
            # self.trial_lengths.append(self.expt.splits)
            # self.traces.append(self.expt.C.tolist())
            
            # self.handle_outgoing()
    
    @run_in_executor        
    def do_next_group(self):
        self.expt.do_next_group()
             
    def handle_session_end(self):
        """
        Handles the SI 'session done' message event. Sent when a loop/grad is completed. Calls the 
        final caiman fit on all the data.
        """
        self.update()
        print('SI says session stopped.')
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

    def save_trial_data_mat(self):
        print('processing and saving trial data')
        psths = process_data(self.traces, self.trial_lengths)
        out = dict(psths = psths)
        save_path = os.path.join(self.srv_folder, f'cm_out_plane{self.expt.plane}_iter_{self.iters}.mat')
        sio.savemat(save_path, out)

if __name__ == '__main__':
    # mm3d = MakeMasks3D(template_image, channels, planes, x_start, x_end)
    expt = OnlineAnalysis(caiman_params, **image_params)
    expt.make_templates(template_path)
    srv = SISocketServer(ip, port, expt, srv_folder)
    # expt.structural_image = image
