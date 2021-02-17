import asyncio
import json
import queue
import warnings
import os
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import scipy.io as sio
import websockets
from caiman_online.analysis import process_data
from caiman_online.utils import slice_movie
from ScanImageTiffReader import ScanImageTiffReader

from ..comm import Alert
from ..workers import RealTimeWorker

warnings.filterwarnings(
    action='ignore',
    lineno=1969, 
    module='scipy')

warnings.filterwarnings(
    action='ignore',
    lineno=1963, 
    module='scipy')

class RealTimeServer:
    def __init__(self, ip, port, srv_folder, opts, Ain_path=None, num_frames_max=10000, **kwargs):
        self.ip = ip
        self.port = port
        self.url = f'ws://{ip}:{port}'
        self.srv_folder = Path(srv_folder)
        self.opts = opts
        self.Ain_path = Ain_path     
        self.num_frames_max = num_frames_max
        self.init_files = None
        self.qs = []
        self.workers = None
        self.lengths = []
        self.kwargs = kwargs

        Alert(f'Starting WS server ({self.url})...', 'success')
        self._start_server()

    def _start_server(self):
        """
        Starts the WS server.
        """
        serve = websockets.serve(self.handle_incoming, self.ip, self.port, max_size=5000000, max_queue=None)
        asyncio.get_event_loop().run_until_complete(serve)
        Alert('Ready to launch!', 'success')
        self.loop = asyncio.get_event_loop()
        self.loop.run_forever()
        
    async def route(self, payload):
        data = json.loads(payload)

        if isinstance(data, str):
            if data == 'acq done':
                await self.put_tiff_frames_in_queue()
            elif data == 'session done':
                Alert('Recieved acqAbort. Workers will continue running until all frames are completed.', 'info')
                for q in self.qs:
                    q.put_nowait('stop')
            elif data == 'uhoh':
                Alert('Forced quit from SI.', 'error')

        elif isinstance(data, dict):
            try:
                kind = data.pop('kind')
                
                if kind == 'setup':
                    await self.handle_setup(**data)
                elif kind == 'armed':
                    await self.run_queues()
                elif kind == 'frame':
                    await self.put_in_frame_queue(**data)
                elif kind == 'quit':
                    self.loop.stop()
                elif kind =='acq done':
                    await self.put_tiff_frames_in_queue()
                else:
                    Alert('Incoming JSON parse error. Specified kind not implemented', 'error')
            except KeyError:
                Alert('Incoming JSON parse error. No kind specified', 'error')
                    
    async def handle_incoming(self, websocket, path):
        """Handle incoming data."""
        
        self.websocket = websocket
        async for payload in websocket:
            await self.route(payload)
            
    async def handle_setup(self, nchannels, nplanes, frameRate, si_path, **kwargs):
        """Handle the initial setup data from ScanImage."""
        
        Alert('Recieved setup data from SI', 'success')
        
        self.nchannels = int(nchannels)
        Alert(f'Set nchannels to {nchannels}', 'info')
        
        self.nplanes = int(nplanes)
        Alert(f'Set nplanes to {self.nplanes}', 'info')
        
        self.opts['fr'] = float(frameRate)
        Alert(f'Set fr to {frameRate}', 'info')
        
        self.folder = Path(si_path)
        self.files = list(Path(si_path).glob('*.tif*'))
        Alert(f'Set si_path to {si_path}', 'info')
        
        # spawn queues and workers (without launching queue)
        self.workers = [self._start_worker(p) for p in range(self.nplanes)]
        
        # finished setup, ready to go
        Alert("Ready to process online!", 'success')
        
        # run the queues
        # ? put here to simplify the MATLAB interface for now, bypassing 'armed
        await self.run_queues()
                
    async def run_queues(self):
        tasks = [self.loop.run_in_executor(None, w.process_frame_from_queue) for w in self.workers]
        results = await asyncio.gather(*tasks)
        # from here do final analysis
        # results will be a list of dicts
        self.process_and_save(results)
         # Return True to release back to main loop
        return True
        
    def process_and_save(self, results):
        c_list = [r['C'] for r in results]
        c_all = np.concatenate(c_list, axis=0)
        out = {
            'c': c_all.tolist(),
            'splits': self.lengths
        }
        
        # first save the raw data in case it fails (concatentated)
        fname = self.srv_folder/'raw_data.json'
        with open(fname, 'w') as f:
            json.dump(out, f)
        
        # do proccessing and save trialwise json
        traces = process_data(**out, normalizer='scale')
        out = {
            'traces': traces.tolist()
        }
        fname = self.srv_folder/'traces_data.json'
        with open(fname, 'w') as f:
            json.dump(out, f)
            
        # save it as a npy also
        fname = self.srv_folder/'traces.npy'
        np.save(fname, c_all)
        fname = self.srv_folder/'psths.npy'
        np.save(fname, traces)
        
        # save as matlab
        fname = self.srv_folder/'data.mat'
        mat = {
            'tracesCaiman': c_all,
            'psthsCaiman': traces,
            'trialLengths': self.lengths
        }
        sio.savemat(fname, mat)
        
        Alert('Done saving! You can quit now.', 'success')
         
    def _start_worker(self, plane):
        self.qs.append(queue.Queue())
        Alert(f'Starting RealTimeWorker {plane}', 'info')
        worker = RealTimeWorker(self.files, plane, self.nchannels, self.nplanes, self.opts, self.qs[plane],
                                num_frames_max=self.num_frames_max, Ain_path=self.Ain_path, **self.kwargs)
        return worker
    
    async def put_in_frame_queue(self, frame, plane):
        if isinstance(frame, list):
            frame = np.array(frame, dtype='float32')
        self.qs[plane].put_nowait(frame)

    def get_last_tiff(self):
        crap = []
        lengths = []
        # get the last tiff and make sure it's the right size
        last_tiffs = list(self.folder.glob('*.tif*'))[-4:-2]
        # pull the last few tiffs to make sure none are weirdos and get trial lengths
        for tiff in last_tiffs:
            with ScanImageTiffReader(str(tiff)) as reader:
                data = reader.data()
                # check for bad tiffs
                if data.shape[0] < 10: 
                    last_tiffs.remove(tiff)
                    crap.append(tiff)
                else:
                    lengths.append(data.shape[0])
        for crap_tiff in crap:
            os.remove(crap_tiff)

        return last_tiffs[-1]

    async def put_tiff_frames_in_queue(self):
        # added sleep because last tiff isn't closed in time I think
        await asyncio.sleep(0.5)
        tiff = self.get_last_tiff()
        for p in range(self.nplanes):
            mov = slice_movie(str(tiff), x_slice=None, y_slice=None, t_slice=slice(p*self.nchannels,-1,self.nchannels*self.nplanes))
            if p==0:
                # only want to do this once per tiff!
                self.lengths.append(mov.shape[0])
            for f in mov:
                self.qs[p].put_nowait(f.squeeze())
                
                
class TestRealTimeServer(RealTimeServer):
    def __init__(self, ip, port, srv_folder, opts, Ain_path, num_frames_max=10000):
        Alert('Starting test server...', 'info')
        super().__init__(ip, port, srv_folder, opts, Ain_path=Ain_path, num_frames_max=num_frames_max)
        self.test_server = True
        
    async def test_frame_queue(self, filename):
        for p in range(self.nplanes):
            mov = slice_movie(str(filename), x_slice=None, y_slice=None, t_slice=slice(p*self.nchannels,-1,self.nchannels*self.nplanes))
            if p==0:
                # only want to do this once per tiff!
                self.lengths.append(mov.shape[0])
            for f in mov:
                self.qs[p].put_nowait(f.squeeze())
                
    async def route(self, message):
        data = json.loads(message)
        kind = data.pop('kind')
        if kind == 'test_tiff':
            await self.test_frame_queue(**data)
        elif kind == 'armed':
            await self.run_queues()
        elif kind =='setup':
            await self.handle_setup(**data)
        elif kind =='stop':
            for q in self.qs:
                q.put_nowait('stop')
