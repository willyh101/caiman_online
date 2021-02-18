import json
from pathlib import Path
from ...comm import Alert
import queue

class Live2pServer:
    def __init__(self, ip, port, expt):
        self.ip = ip
        self.port = port
        self.expt = expt
        
        self.qs = []
        self.workers = []
        
    async def handle_incoming(self, websocket, path):
        """Handle incoming data."""
        
        self.websocket = websocket
        async for payload in websocket:
            await self.route(payload)
            
    async def route_incoming(self, payload):
        data = json.loads(payload)
    
    async def handle_setup(self, nchannels, nplanes, frameRate, si_path, **kwargs):
        """Handle the initial setup data from ScanImage."""
        
        Alert('Recieved setup data from SI', 'success')
        
        self.expt.nchannels = int(nchannels)
        Alert(f'Set nchannels to {nchannels}', 'info')
        
        self.expt.nplanes = int(nplanes)
        Alert(f'Set nplanes to {self.nplanes}', 'info')
        
        self.expt.fr = float(frameRate)
        Alert(f'Set fr to {frameRate}', 'info')
        
        self.expt.folder = Path(si_path)
        self.files = list(Path(si_path).glob('*.tif*'))
        Alert(f'Set si_path to {si_path}', 'info')
        
        # spawn queues and workers (without launching queue)
        self.workers = [self._start_worker(p) for p in range(self.nplanes)]
        
        # finished setup, ready to go
        Alert("Ready to process online!", 'success')
        
        # run the queues
        # ? put here to simplify the MATLAB interface for now, bypassing 'armed
        await self.run_queues()
        
    def _start_worker(self, plane):
        self.qs.append(queue.Queue())
        Alert(f'Starting RealTimeWorker {plane}', 'info')
        worker = RealTimeWorker(self.files, plane, self.nchannels, self.nplanes, self.opts, self.qs[plane],
                                num_frames_max=self.num_frames_max, Ain_path=self.Ain_path, **self.kwargs)
        return worker