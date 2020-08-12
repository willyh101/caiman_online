import warnings
warnings.filterwarnings('ignore')


"""
Websocket server for handling communication between ScanImage and Caiman.
Requires websockets (pip install websockets)
"""

import websockets
import asyncio
from caiman_main import OnlineAnalysis
import json


ip = 'localhost'
port = 5001

# image = np.array of mean image that is serving as structural template, needs to be 2D cropped size x 512 mean image
# image_path = path/to/image/to/load (must already be cropped to match x_start:x_end)

from glob import glob
import imageio
import cv2

user_name = 'Mora'
x_start = 50
x_end = 450
date = '20200715'
mouse = 'MBOT5_419'
exp_name = 'ori'

#tif_folder = 'D://'+ user_name + date + mouse + exp_name
tif_folder='D://Mora//20200721//caimantests//'
reference_folder ='D://' + user_name +'//'+ date +'//'+ mouse +'//'+ 'reference' + '//'
image_path = glob(reference_folder + '*.png')[0]


mR= imageio.imread(image_path)
image = mR[:,x_start:x_end,0]

cv2.imwrite(reference_folder + 'caiman_template.png',image)


dxy = (2, 2) # spatial resolution in x and y in (um per pixel)
max_shift_um = (12., 12.) # maximum shift in um
patch_motion_xy = (100., 100.) # patch size for non-rigid correction in um

image_params = {
    'channels': 2,
    'planes': 1,
    'x_start':x_start,
    'x_end': x_end,
    'folder': tif_folder # this is where the tiffs are, make a sub-folder named out to store output data
}








caiman_params = {
    'fr': 15,  # imaging rate in frames per second, per plane
    'overlaps': (24, 24),
    'max_deviation_rigid': 3,
    'p': 2,  # deconv 0 is off, 1 is slow, 2 is fast
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
        data = json.loads(data)

        if isinstance(data, dict):
            # handle the data if it's a dict
            kind = data['kind']
            self.handle_json(data)

        elif isinstance(data, str):
            # handle the data for simple strings
            if data == 'acq done':
                self.handle_acq_done()

            elif data == 'session end':
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

            else:
                # event not specified
                print('unknown event!')

        else:
            # otherwise we don't know what it is
            print('unknown data!')

    def handle_json(self, data):
        kind = data['kind']
        if kind == 'setup':
            self.expt.channels = int(data['nchannels'])
            self.expt.planes = int(data['nplanes'])


    def handle_acq_done(self):
        """
        Handles the SI 'acq done' message event. Send when a tiff/acquistion is completed. Calls
        a new caiman fit after acq_per_batch is satisfied.
        """
        self.update()
        print(f'SI says acq done. ({self.acqs_this_batch})')

        if self.acqs_this_batch >= self.acq_per_batch:
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
            #self.expt.segment_mm3d()
            self.expt.segment() #for if you want to provide the structural image manually
        self.acqs_done += 1
        self.acqs_this_batch += 1



if __name__ == '__main__':
    expt = OnlineAnalysis(caiman_params, **image_params)
    # expt.set_structural_image(image_path)  ...OR...
    expt.structural_image = image
    srv = SISocketServer(ip, port, expt)
    srv.expt.structural_image = image
