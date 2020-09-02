import asyncio
import multiprocessing
import json

import websockets

from .wscomm import WebSocketAlert

# make a cmn

class TrueOnlineServer:
    """
    A class for running caiman_online, online.
    """
    def __init__(self, ip, port, nplanes):
        self.ip = ip
        self.port = port
        self.nplanes = nplanes
        self.url = f'ws://{ip}:{port}'
        self.service = 'websocket'
        self.plane_is_on = 0
        
        self.caiman_data = None
        self.cmns = []
        
        WebSocketAlert(f'Starting WS server ({self.url})...', 'success')
        self._start_server()
        
        self.queues = [asyncio.Queue() for p in range(self.nplanes)]

    def _start_server(self):
        """
        Starts the WS server.
        """
        serve = websockets.serve(self.handle_incoming, self.ip, self.port)
        asyncio.get_event_loop().run_until_complete(serve)
        WebSocketAlert('Ready to launch!', 'success')
        self.loop = asyncio.get_event_loop()
        self.loop.run_forever()
        
    def _ensure_json(self, payload):
        try:
            data = json.loads(payload)
        except:
            WebSocketAlert('Incoming data not JSON formatted. Could not parse', 'error')
    
    async def _recv_payload(self, websocket):
        self.websocket = websocket
        payload = await websocket.recv()
        return payload
                    
    async def handle_incoming(self, websocket, path):
        """Handle incoming data."""
        
        # await incoming and validate
        payload = await _recv_payload(websocket)
        data = _ensure_json(payload)
        
        try:
            kind = data.pop('kind')
        except KeyError:
            WebSocketAlert('Incoming JSON parse error. No kind specified', 'error')
        
        if kind == 'setup':
            self.handle_setup(data)
        elif kind == 'frame':
            self.handle_frame(data)
        else:
            WebSocketAlert('Incoming JSON parse error. Specified kind not implemented', 'error')
            
    def handle_setup(self, data):
        """Handle the initial setup data from ScanImage."""
        self.nchannels = data['nchannels']
        WebSocketAlert(f'Set nchannels to {self.nchannels}', 'success')
        self.nplanes = data['nplanes']
        WebSocketAlert(f'Set nplanes to {self.nplanes}', 'success')
        self.fr = data['frameRate']
        WebSocketAlert(f'Set fr to {self.fr}', 'success')
    
    def handle_frame(self, frame):
        """Main function that does all of the caiman stuff."""
        self.queues[self.plane_is_on].put(frame)
            
        for p, q in enumerate(self.queues):
            self.caiman_data[self.plane_is_on] = self.process_frame(q, p)
            
        # increase the plane counter
        self.plane_is_on += 1
        if self.plane_is_on > self.nplanes:
            self.plane_is_on = 0
            
    def handle_conds(self, data):
        pass
    
    def handle_si_trialinfo(self, data):
        pass
    
    def process_frame(self, queue, plane):
        # gets data queue
        frame = queue.get()
        # calls caiman
        self.cmns[p]
        pass
    
    async def worker(self, queue):
        while True:
            frame = await queue.get()
            frame_data = await process_frame(frame)
            
class CaimanWorker:
    def __init__(self, opts):
        self.queue = asyncio.Queue()
        self.acid = cmnf.online_cnmf.OnACID(dview=None, params=opts)
        self.acid.initalize_online()
        self.t = 0
        
        self.loop = asyncio.get_event_loop()
        self.loop.run_forever()
        self.task = asyncio.create_task(self.process())
        
    def append_to_queue(self, frame):
        self.queue.put(frame)
        
    def process(self):
        while True:
            frame = await self.queue.get()
            self.t += 1
            frame = self.acid.mc_next(self.t, frame)
            self.acid.fit_next(t, frame.ravel(order='F'))
            self.queue.task_done()