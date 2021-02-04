import asyncio
from caiman_online.wrappers import tictoc
from caiman_online.utils import slice_movie, tiffs2array
import os
import warnings
import json
import queue
from pathlib import Path
from ScanImageTiffReader import ScanImageTiffReader

import websockets
import numpy as np

from ..comm import Alert
from ..workers import RealTimeWorker
from .. import networking

warnings.filterwarnings(
    action='ignore',
    lineno=1969, 
    module='scipy')

warnings.filterwarnings(
    action='ignore',
    lineno=1963, 
    module='scipy')

class RealTimeServer:
    def __init__(self, ip, port, srv_folder, opts, Ain_path=None, num_frames_max=10000):
        self.ip = ip
        self.port = port
        self.url = f'ws://{ip}:{port}'
        self.srv_folder = srv_folder
        self.opts = opts
        self.Ain_path = Ain_path     
        self.num_frames_max = num_frames_max
        self.init_files = None
        self.qs = []
        self.workers = []

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
        
    async def incoming(self, payload):
        data = json.loads(payload)
        
        try:
            kind = data.pop('kind')
            
            if kind == 'setup':
                await self.handle_setup(**data)
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
            await self.incoming(payload)
            
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
        
        # spawn queues and workers
        for p in range(self.nplanes):
            self.qs.append(queue.Queue())
            Alert(f'Starting RealTimeWorker {p}', 'info')
            worker = RealTimeWorker(self.files, p, self.nchannels, self.nplanes, self.opts, self.qs[p],
                                    num_frames_max=self.num_frames_max, Ain_path=self.Ain_path)
            self.loop.run_in_executor(None, worker.process_frame_from_queue)
        
        Alert("Ready to process online!", 'success')
    
    async def put_in_frame_queue(self, frame, plane):
        if isinstance(frame, list):
            frame = np.array(frame, dtype='float32')
        self.qs[plane].put_nowait(frame)

    def get_last_tiff(self):
        crap = []
        lengths = []
        # get the last tiff and make sure it's the right size
        last_tiffs = list(self.folder.glob('*.tif*'))[-6:-1]
        # pull the last five tiffs to make sure none are weirdos and get trial lengths
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
        tiff = self.get_last_tiff()
        for p in range(self.nplanes):
            mov = slice_movie(str(tiff), x_slice=None, y_slice=None, t_slice=slice(p*self.nchannels))
            for f in mov:
                self.qs[p].put_nowait(f)