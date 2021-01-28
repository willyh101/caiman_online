import asyncio
import warnings
import json
import queue

import websockets
import numpy as np

from ..comm import Alert
from .workers import RealTimeWorker

warnings.filterwarnings(
    action='ignore',
    lineno=1969, 
    module='scipy')

warnings.filterwarnings(
    action='ignore',
    lineno=1963, 
    module='scipy')

class RealTimeServer:
    def __init__(self, ip, port, srv_folder, opts, Ain_path=None):
        self.ip = ip
        self.port = port
        self.url = f'ws://{ip}:{port}'
        self.srv_folder = srv_folder
        self.opts = opts
        self.Ain_path = Ain_path
        self.q = queue.Queue()
        

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
        
    async def incoming(self, payload):
        data = json.loads(payload)
        
        try:
            kind = data['kind']
            
            if kind == 'setup':
                await self.handle_setup(data)
            elif kind == 'frame':
                await self.handle_frame_queue(data['frame'])
            elif kind == 'quit':
                self.loop.stop()
            elif kind == 'stop':
                await self.handle_frame_queue(kind)
            else:
                Alert('Incoming JSON parse error. Specified kind not implemented', 'error')
        except KeyError:
            Alert('Incoming JSON parse error. No kind specified', 'error')
                    
    async def handle_incoming(self, websocket, path):
        """Handle incoming data."""
        
        self.websocket = websocket
        async for payload in websocket:
            await self.incoming(payload)
            
    async def handle_setup(self, data):
        """Handle the initial setup data from ScanImage."""
        self.nchannels = data['nchannels']
        Alert(f'Set nchannels to {self.nchannels}', 'success')
        self.nplanes = data['nplanes']
        Alert(f'Set nplanes to {self.nplanes}', 'success')
        self.fr = data['frameRate']
        self.opts['fr'] = self.fr
        Alert(f'Set fr to {self.fr}', 'success')
        
        # spawn workers
        self.worker = RealTimeWorker(self.q, 0, self.opts, Ain_path=self.Ain_path, 
                                     nplanes=self.nplanes, nchannels=self.nchannels)
        self.loop.run_in_executor(None, self.worker.process_frame_from_queue)
    
    async def handle_frame(self, frame):
        """Main function that does all of the caiman stuff."""
        frame = np.array(frame, dtype='float32')
        self.worker.process_frame(frame)
        # func = functools.partial(self.worker.process_frame, frame)
        # self.task = self.loop.run_in_executor(None, func)
        # await self.task
        
    async def handle_frame_queue(self, frame):
        if isinstance(frame, list):
            frame = np.array(frame, dtype='float32')
        self.q.put_nowait(frame)