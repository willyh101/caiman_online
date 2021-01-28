"""
Websocket server for handling communication between ScanImage and Caiman.
"""

import asyncio
from caiman_online.pipelines import OnAcidPipeline, SeededPipeline
import json
import os
import warnings
from pathlib import Path

import numpy as np
import scipy.io as sio
import websockets
from ScanImageTiffReader import ScanImageTiffReader
from termcolor import cprint

from ...analysis import process_data, stim_align_trialwise

warnings.filterwarnings(
    action='ignore',
    lineno=1969, 
    module='scipy')

warnings.filterwarnings(
    action='ignore',
    lineno=1963, 
    module='scipy')

class SIWebSocketServer:
    """
    Runs the websocket server for communication with ScanImage. Also maybe will eventually run the
    live plotting to the DAQ.

    ip = IP address to serve on, defaults to 'localhost'
    port = port to serve on, defaults to 5000
    expt = online experiment object
    srv_folder = where to output .mat (doesn't have to be a server)
    batch_size = number of tiffs to do at once
    """
    def __init__(self, ip, port, srv_folder, batch_size, pipeline):
        self.ip = ip
        self.port = port
        self.url = f'ws://{ip}:{port}'
        
        self.srv_folder = srv_folder

        self.acqs_done = 0
        self.acqs_this_batch = 0
        self.acq_per_batch = batch_size
        self.iters = 0
        self.min_frames_to_process = 500

        self.trial_lengths = []
        self.traces = []
        self.stim_times = []
        self.stim_conds = []
        self.vis_conds = []

        self.data = []
        self.task = None
        self.has_daq_data = False
                
        self.pipeline = pipeline
        
        Alert(f'Starting WS server ({self.url})...', 'success')
        self._start_server()

    def _start_server(self):
        """
        Starts the WS server.
        """
        serve = websockets.serve(self.handle_incoming, self.ip, self.port)
        asyncio.get_event_loop().run_until_complete(serve)
        Alert('Ready to launch!', 'success')
        self.loop = asyncio.get_event_loop()
        self.loop.run_forever()

    async def handle_incoming(self, websocket, path):
        """
        Handles data incoming over the websocket and dispatches
        to specific handle functions.
        """

        # async for data in websocket:
        self.websocket = websocket
        data = await websocket.recv()
        data = json.loads(data)

        if isinstance(data, dict):
            # handle the data if it's a dict
            await self.handle_json(data)

        elif isinstance(data, str):
            # handle the data for simple strings
            if data == 'acq done':
                await self.handle_acq_done()

            elif data == 'session done':
                await self.handle_session_end()

            elif data == 'hi':
                print('SI computer says hi!')

            elif data == 'wtf':
                Alert('Critical error! Shutting down server.', 'error')
                self.loop.stop()

            elif data == 'reset':
                self.acqs_done = 0

            else:
                # event not specified
                print('unknown event!')
                print(data)

        else:
            # otherwise we don't know what it is
            print('unknown kind of data!')
            print(data)

    async def handle_json(self, data):

        try:
            kind = data['kind']

            if kind == 'setup':
                Alert('Recieved setup data from SI', 'success')
                self.pipeline.nchannels = int(data['nchannels'])
                print(f'nchannels set to: {self.pipeline.nchannels}')

                self.pipeline.nplanes = int(data['nplanes'])
                print(f'nplanes set to: {self.pipeline.nplanes}')

                self.pipeline.params['fr'] = float(data['frameRate'])
                print(f'frame rate set to: {self.pipeline.params["fr"]}')

                self.pipeline.folder = Path(data['si_path'] + '/')
                print(f'tiff source folder set to: {self.pipeline.folder}')
                
                if isinstance(self.pipeline, SeededPipeline):
                    frames_per_plane = data['framesPerPlane']
                    self.acq_per_batch = self.min_frames_to_process // int(frames_per_plane)
                    self.pipeline.batch_size_tiffs = self.acq_per_batch
                    print(f'tiffs per batch set to: {self.acq_per_batch}')
                
            elif kind == 'daq_data':
                Alert('Recieved trial data from DAQ', 'success')
                # appends in a trialwise manner
                self.stim_conds.append(data['condition'])
                self.stim_times.append(data['stim_times'])
                self.vis_conds.append(data['vis_cond'])
                self.has_daq_data = True

            else:
                raise KeyError

        except KeyError:
            Alert('Unknown JSON data. Printing data below...', 'error')
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
            
            Alert('Starting Caiman fit', 'info')
            self.task = self.loop.run_in_executor(None, self.pipeline.fit_batch)
            await self.task

            self.iters += 1
            Alert('Fit done. Waiting on next batch', 'success')

    async def handle_session_end(self):
        """
        Handles the SI 'session done' message event. Sent when a loop/acq is completed. Calls the
        final caiman fit on all the data.

        Currently DOES NOT do a final fit or a cleanup fit because I am concerned about
        making sure there are enough tiffs for the final fit.
        """
        Alert('SI says session ended.', 'warn')
        
        if self.iters == 0:
            Alert('Caiman ended abruptly.', 'error')
            self.loop.stop()
        else:
            Alert('Waiting for Caiman to finish.', 'info')
            await self.task
            
            self.update()
            
            Alert('Proccessing final data...', 'info')
            self.save_trial_data_mat()
            
            Alert('Data saved. Quitting...', 'success')
            self.loop.stop()
            
            print('bye!')

    async def handle_outgoing(self, data):
        out = json.dumps(data)
        await self.websocket.send(out)
        Alert('Sent Caiman Data to DAQ', 'info')

    def update(self):
        """
        Updates acq counters and anything else that needs to keep track of trial counts.
        """
        self.acqs_done += 1
        self.acqs_this_batch += 1
        
    def format_out_data(self):
        pass

    def save_trial_data_mat(self):
        
        # dff_data = []
        # fit_data = []
        # len_data = []
        # loc_data = []
        
        # for acq in self.data:
        #     fewest_frames = min([np.array(plane['c']).shape[1] for plane in acq])
        #     fit_data.append(np.concatenate([np.array(plane['c'])[:,:fewest_frames] for plane in acq]))
        #     dff_data.append(np.concatenate([np.array(plane['dff'])[:,:fewest_frames] for plane in acq]))
            
        #     len_data.append(np.array(acq[0]['splits']))
    
        #     coords = json.loads(acq[0]['coords'])['CoM']
        #     coords = {int(key):value for key, value in coords.items()}
        #     loc_data.append(np.array(list(coords.values())))
            
        # len_data = np.concatenate(len_data)
        # fit_data = np.concatenate(fit_data, axis=1)
        # dff_data = np.concatenate(dff_data, axis=1)

        # save whole trace output as mat file
        fit_data = np.array(self.pipeline.traces).squeeze()
        len_data = self.pipeline.splits
        
        # min subtract
        out_data = fit_data - fit_data.min(axis=1).reshape(-1,1)
        
        out = {
            'tracesCaiman': out_data,
            'stimTimesCaiman': self.stim_times,
            'stimCondsCaiman': self.stim_conds,
            'visCondsCaiman': self.vis_conds
        }
        
        save_path = os.path.join(self.srv_folder, f'caiman_traces_full.mat')
        sio.savemat(save_path, out)

        # make into psths and save
        psths = process_data(fit_data, len_data)
        
        out = {
            'psthsCaiman': psths, 
            'stimTimesCaiman': self.stim_times,
            'stimCondsCaiman': self.stim_conds,
            'visCondsCaiman': self.vis_conds
        }
        
        save_path = os.path.join(self.srv_folder, f'caiman_psths.mat')
        sio.savemat(save_path, out)
        
        # if stim aligned, save it
        if self.has_daq_data:
            psths_aligned = stim_align_trialwise(psths, self.stim_times)
            
            out = {
                'psthsAlignedCaiman': psths_aligned,
                'stimCondsCaiman': self.stim_conds, 
                'visCondsCaiman': self.vis_conds
            }
            
            save_path = os.path.join(self.srv_folder, f'caiman_psths_aligned.mat')
            sio.savemat(save_path, out)      
            
            
def validate_tiffs(files, bad_tiff_size=5):
    """
    Finds the weird small tiffs and removes them. Arbitrarily set to <5 frame because it's not too
    small and not too big. Also gets the lengths of all good tiffs (note however it returns the TOTAL
    frame number, not the number adjuster for number of channels and number of planes).

    Args:
        bad_tiff_size (int, optional): Size tiffs must be to not be trashed. Defaults to 5.
    """
    
    crap = []
    lengths = []
    
    for tiff in files:
        with ScanImageTiffReader(str(tiff)) as reader:
            data = reader.data()
            if data.shape[0] < bad_tiff_size:
                # remove them from the list of tiffs
                files.remove(tiff)
                # add them to the bad tiff list for removal from HD
                crap.append(tiff)
            else:
                # otherwise we append the length of tiff to the lengths list
                lengths.append(data.shape[0])             
    for crap_tiff in crap:
        os.remove(crap_tiff)
        
    return lengths

class Alert:
    alerts = {
        'none': '*',
        'info': '[INFO]',
        'warn': '[WARNING]',
        'error': '[ERROR]',
        'success': '[INFO]'
    }
    
    colors = {
        'none': 'white',
        'info': 'yellow',
        'warn': 'yellow',
        'error': 'red',
        'success': 'green'
    }
    
    def __init__(self, message, level='none'):
        self.message = message
        self.level = level
        self.color = self.colors[self.level]
        
        out = self.format()
        self.show(out)
    
    def format(self):
        return f'{self.alerts[self.level]} {self.message}'
    
    def show(self, output):
        cprint(output, self.color)
