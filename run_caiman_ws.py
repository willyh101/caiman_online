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
    def __init__(self, ip, port, expt, srv_folder, batch_size):
        self.ip = ip
        self.port = port
        self.expt = expt
        self.url = f'ws://{ip}:{port}'
        self.srv_folder = srv_folder

        self.acqs_done = 0
        self.acqs_this_batch = 0
        self.acq_per_batch = batch_size
        self.iters = 0
        self.expt.batch_size = self.acq_per_batch
        self.min_frames_to_process = 400

        self.trial_lengths = []
        self.traces = []
        self.stim_times = []
        self.stim_conds = []

        self.data = []

        cprint(f'[INFO] Starting WS server ({self.url})...', 'green', end = ' ')
        self.start_server()

    def start_server(self):
        """
        Starts the WS server.
        """
        serve = websockets.serve(self.handle_incoming, self.ip, self.port)
        asyncio.get_event_loop().run_until_complete(serve)
        cprint('ready to launch!', 'green')
        self.loop = asyncio.get_event_loop()
        self.loop.run_forever()

    async def handle_incoming(self, websocket, path):
        """
        Handles data incoming over the websocket and dispatches
        to specific handle functions.
        """

        async for data in websocket:
            # data = await websocket.recv()
            data = json.loads(data)

            if isinstance(data, dict):
                # handle the data if it's a dict
                self.handle_json(data)

            elif isinstance(data, str):
                # handle the data for simple strings
                if data == 'acq done':
                    await self.handle_acq_done()

                elif data == 'session end':
                    await self.handle_session_end()

                elif data == 'uhoh':
                    print('uhoh!')
                    self.loop.stop()

                elif data == 'hi':
                    print('SI computer says hi!')

                elif data == 'wtf':
                    WebSocketAlert('BAD ERROR IN CAIMAN_MAIN (self.everything_is_ok == False)', 'error')
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

            self.expt.folder = data['si_path'] + '/'
            print(f'tiff source folder set to: {self.expt.folder}')

            frames_per_plane = data['framesPerPlane']
            self.acq_per_batch = self.min_frames_to_process // int(frames_per_plane)
            self.expt.batch_size  = self.acq_per_batch
            print(f'tiffs per batch set to: {self.expt.batch_size}')

            self.expt._verify_folder_structure()

        elif kind == 'daq_data':
            WebSocketAlert('Recieved trial data from DAQ', 'success')
            # appends in a trialwise manner
            self.stim_conds.append(data['condition'])
            self.stim_times.append(data['stim_times'])
            print(self.stim_conds)

        else:
            WebSocketAlert('Unknown JSON data. Printing data below...', 'error')
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
            
            # run the group in another thread and wait for the result
            self.task = self.loop.run_in_executor(None, self.expt.do_next_group)
            await self.task

            WebSocketAlert('Fit done. Waiting on next batch', 'success')

            # save the data
            self.data.append(self.expt.data_this_round)

    async def handle_session_end(self):
        """
        Handles the SI 'session done' message event. Sent when a loop/acq is completed. Calls the
        final caiman fit on all the data.

        Currently DOES NOT do a final fit or a cleanup fit because I am concerned about
        making sure there are enough tiffs for the final fit.
        """
        WebSocketAlert('SI says session ended.', 'warn')
        
        if self.iters == 0:
            self.loop.stop()
        else:
            WebSocketAlert('Waiting for Caiman to finish.', 'info')
            await self.task
            
            self.update()
            
            WebSocketAlert('Proccessing final data...', 'info')
            self.save_trial_data_mat()
            WebSocketAlert('Data saved. Quitting...', 'success')
            self.loop.stop()
            print('bye!')

    def update(self):
        """
        Updates acq counters and anything else that needs to keep track of trial counts.
        """

        self.acqs_done += 1
        self.acqs_this_batch += 1
        self.iters += 1

    def save_trial_data_mat(self):
        
        dff_data = []
        fit_data = []
        len_data = []
        loc_data = []
        
        for acq in self.data:
            fewest_frames = min([np.array(plane['c']).shape[1] for plane in acq])
            fit_data.append(np.concatenate([np.array(plane['c'])[:,:fewest_frames] for plane in acq]))
            dff_data.append(np.concatenate([np.array(plane['dff'])[:,:fewest_frames] for plane in acq]))
            
            len_data.append(np.array(acq[0]['splits']))
    
            coords = json.loads(acq[0]['coords'])['CoM']
            coords = {int(key):value for key, value in coords.items()}
            loc_data.append(np.array(list(coords.values())))
            
        len_data = np.concatenate(len_data)
        fit_data = np.concatenate(fit_data, axis=1)
        dff_data = np.concatenate(dff_data, axis=1)

        # save whole trace output as mat file
        out_data = fit_data - fit_data.min(axis=1).reshape(-1,1)
        out = dict(traces = out_data)
        save_path = os.path.join(self.srv_folder, f'caiman_traces_full.mat')
        sio.savemat(save_path, out)

        # make into psths and save
        psths = process_data(fit_data, len_data)
        out = dict(psths = psths)
        save_path = os.path.join(self.srv_folder, f'caiman_psths.mat')
        sio.savemat(save_path, out)