"""
Websocket server for handling communication between ScanImage and Caiman.
Requires websockets (pip install websockets)
"""

import websockets
import asyncio
from caiman_main import image_params, caiman_params, OnlineAnalysis

IP = 'localhost'
PORT = 5000

# IMAGE = np.array of mean image that is serving as structural template, needs to be 2D cropped size x 512 mean image
# IMAGE_PATH = path/to/image/to/load (must already be cropped to match x_start:x_end)

class SISocketServer:
    """
    Runs the websocket server for communication with ScanImage. Also maybe will eventually run the 
    live plotting to the DAQ.
    
    ip = IP address to serve on, defaults to 'localhost'
    port = port to serve on, defaults to 5000
    expt = online experiment object
    """
    def __init__(self, ip, port, expt):
        self.ip = ip
        self.port = port
        self.expt = expt
        self.url = f'ws://{ip}:{port}'
        
        self.acqs_done = 0
        self.acqs_this_batch = 0
        self.acq_per_batch = 5
        self.expt.batch_size = self.acq_per_batch
        
        print('Starting WS server...', end = ' ')
        self.start_server()
        
    def start_server(self):
        """
        Starts the WS server.
        """
        self.serve = websockets.serve(self.handle_incoming, self.ip, self.port)
        asyncio.get_event_loop().run_until_complete(self.serve)
        print('ready to launch!')
        self.loop = asyncio.get_event_loop()
        self.loop.run_forever()

    
    
    async def handle_incoming(self, websocket, path):
        """
        Handles data incoming over the websocket and dispatches to specific handle functions.
        
        Not sure how websocket and path work, they must be passed implicitly by websocket.serve(...)
        so I don't really care. Add specific handle functions here.
        """
        
        data = await websocket.recv()

        if data == 'acq done':
            self.handle_acq_done()
        
        elif data == 'session end':
            self.handle_session_end()
        
        elif data == 'uhoh':
            print('uhoh!')
            self.loop.stop()
            
        elif data == 'hi':
            print('SI computer says hi!')
        
        else:
            print('unknown event!')
        
    def handle_acq_done(self):
        """
        Handles the SI 'acq done' message event. Send when a tiff/acquistion is completed. Calls
        a new caiman fit after acq_per_batch is satisfied.
        """
        self.update()
        print(f'SI says acq done. ({self.acqs_this_batch})')
        
        if self.acqs_this_batch > self.acq_per_batch:
            self.acqs_this_batch = 0
            print('Starting caiman fit...')
            self.expt.do_next_group()
            
    def handle_session_end(self):
        """
        Handles the SI 'session done' message event. Sent when a loop/grad is completed. Calls the 
        final caiman fit on all the data.
        """
        self.update()
        print('SI says session stopped.')
        print('Starting final caiman fit...')
        self.expt.do_final_fit()
        print('quitting...')
        self.loop.stop()
                
    def update(self):
        """
        Updates acq counters and anything else that needs to keep track of trial counts.
        """
        if self.acqs_done == 0:
            self.expt.segment_mm3d()
            # self.expt.segment() for if you want to provide the structural image manually
        self.acqs_done += 1
        self.acqs_this_batch += 1
            
if __name__ == '__main__':
    EXPT = OnlineAnalysis(caiman_params, **image_params)
    # EXPT.set_structural_image(IMAGE)  ...OR...
    # EXPT.structural_image = IMAGE
    srv = SISocketServer(IP, PORT, EXPT)