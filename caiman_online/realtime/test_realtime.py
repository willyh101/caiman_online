import asyncio
import json
import logging
import time
import warnings
from datetime import datetime
from glob import glob
from pathlib import Path

with warnings.catch_warnings():
    warnings.simplefilter('ignore', category=FutureWarning)
    import tensorflow as tf
import websockets

from caiman_online.networking import send_this
from caiman_online.realtime.server import TestRealTimeServer
from caiman_online.utils import tic, tiffs2array, toc

if tf.__version__[0] == '1':
    tf.enable_eager_execution()
    
import os

os.environ['MKL_NUM_THREADS'] = '1'
os.environ['OPENBLAS_NUM_THREADS'] = '1'

__all__ = ['test_send_tiffs']

warnings.filterwarnings(
    action='ignore',
    lineno=1969, 
    module='scipy')

warnings.filterwarnings(
    action='ignore',
    lineno=1963, 
    module='scipy')

# LOGFILE = folder + '/caiman/out/pipeline_test.log'
LOGFORMAT = '{relativeCreated:08.0f} - {levelname:8} - [{module}:{funcName}:{lineno}] - {message}'
# logging.basicConfig(level=logging.ERROR, format=LOGFORMAT, filename=LOGFILE, style='{')
logging.basicConfig(level=logging.ERROR, format=LOGFORMAT, style='{')
logger = logging.getLogger('caiman_online')
logger.setLevel(logging.DEBUG)

FOLDER = 'e:/caiman_scratch/ori_20210209_seed'
DATA_FOLDER = 'e:/caiman_scratch/ori_20210209'
NPLANES = 3
NCHANNELS = 2
PLANE2USE = 0
MM3D_PATH = glob(DATA_FOLDER+'/*.mat')[0]

IP = 'localhost'
PORT = 5003

# motion correction and CNMF 
dxy = (1.5, 1.5) # spatial resolution in x and y in (um per pixel)
max_shift_um = (15., 15.) # maximum shift in um
patch_motion_xy = (100., 100.) # patch size for non-rigid correction in um

params = {
    # CNMF
    'fr': 6.36,
    'p': 1,  # deconv 0 is off, 1 is slow, 2 is fast
    'nb': 2,  # background compenents -> nb: 3 for complex
    'decay_time': 1.0,  # sensor tau
    'gSig': (7, 7),  # expected half size of neurons in pixels, very important for proper component detection
    'only_init': False,  # has to be `False` when seeded CNMF is used
    'rf': None,  # half-size of the patches in pixels. Should be `None` when seeded CNMF is used.
    'ssub': 1,
    'tsub': 1,
    'do_merge': False, # new found param, testing
    'update_background_components': True,
    'merge_thr': 0.8, 
    'K':300,
    'remove_very_bad_comps': False,
    # 'optimize_g': True,
    
    # motion
    'gSig_filt': (7, 7), # high pass spatial filter for motion correction
    'nonneg_movie': True,
    'niter_rig': 2,
    'pw_rigid': False,  # piece-wise rigid flag, slower
    'max_deviation_rigid': 3,
    'overlaps': (24, 24),
    'max_shifts': [int(a/b) for a, b in zip(max_shift_um, dxy)],
    'strides': tuple([int(a/b) for a, b in zip(patch_motion_xy, dxy)]),
    'num_frames_split': 80,
    'border_nan': 'copy',
    
    # online
    'init_method': 'seeded',
    'epochs': 1,
    'motion_correct': True,
    'expected_comps': 300,
    'update_num_comps':False,
    'max_num_added': 0,
    'sniper_mode': False,
    'simultaneously': True,
    'test_both': False,
    'ring_CNN': True,
    'batch_update_suff_stat':True,
    'update_freq': 100,
    'save_online_movie':False,
    'show_movie': False,
    'n_refit': 1,
    'dist_shape_update':False
}

def load_big_movie_stream(file_path):
    logger.info('Making big movie array for stream.')
    file_path = Path(file_path)
    stream_tiffs = list(file_path.glob('*.tif'))[20:]
    mov = tiffs2array(stream_tiffs,
                      x_slice=slice(120,392),
                      y_slice=slice(0,512),
                      t_slice=slice(PLANE2USE*NCHANNELS,-1,NCHANNELS*NPLANES)
                      )
    logger.info(f'Movie dims are {mov.shape}')
    return mov
    
def test_frames(rate):
    mov = load_big_movie_stream(FOLDER)
    t = tic()
    for i in range(mov.shape[0]):
        logger.info(f'Sent frame {i} of {mov.shape[0]}. Took {toc(t):.3f}s.')
        t = tic()
        frame = mov[i,:,:].tolist()
        out = {
            'kind':'frame',
            'frame': frame
        }
        send_this(out, IP, PORT)
        time.sleep(rate)
             
def test_quit():
    out = {
        'kind':'quit'
    }
    send_this(out, IP, PORT)
        
def test_setup():
    out = {
        'kind':'setup',
        'nchannels':NCHANNELS,
        'nplanes':NPLANES,
        'frameRate':6.36,
        'si_path':FOLDER
    }
    send_this(out, IP, PORT)
    
def test_stop():
    out = {
        'kind':'stop'
    }
    send_this(out, IP, PORT)
    
def test_acq_done():
    out = {
        'kind':'acq done'
    }
    send_this(out, IP, PORT)
    
def test_armed():
    out = {
        'kind': 'armed'
    }
    send_this(out, IP, PORT)
    
def send_frames_ws(rate):
    mov = load_big_movie_stream(FOLDER)
    async def send():
        async with websockets.connect(f'ws://{IP}:{PORT}') as websocket:
            t = tic()
            for i in range(mov.shape[0]):
                logger.info(f'Sent frame {i} of {mov.shape[0]}. Took {toc(t):.3f}s.')
                t = tic()
                frame = mov[i,:,:].tolist()
                out = {
                    'kind':'frame',
                    'frame': frame
                }
                out = json.dumps(out)
                await websocket.send(out)
                time.sleep(rate)
    asyncio.get_event_loop().run_until_complete(send())
    
def test_send_tiffs(rate):
    test_setup()
    input('press enter after init has run... ')
    # test_armed()
    # make sure it has time to catch up and start the queues
    time.sleep(5)
    async def send():
        async with websockets.connect(f'ws://{IP}:{PORT}') as websocket:
            all_tiffs = Path(DATA_FOLDER).glob('*.tif*')
            for f in all_tiffs:
                print(f'Sent tiff {f}')
                out = {
                    'kind':'test_tiff',
                    'filename': str(f)
                }
                out = json.dumps(out)
                await websocket.send(out)
                await asyncio.sleep(rate)
    asyncio.get_event_loop().run_until_complete(send())
    test_stop()
    now = datetime.now()
    current_time = now.strftime("%H:%M:%S")
    print('Last frame (a stop frame) sent at: ', current_time)
        

def test_realtime_server():
    serve = TestRealTimeServer(IP, PORT, 'e:/caiman_scratch/fake_server', params, Ain_path=MM3D_PATH)


    
if __name__ == '__main__':
    test_realtime_server()