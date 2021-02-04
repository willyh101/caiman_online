
import asyncio
import websockets
from caiman_online.wrappers import tictoc
from caiman_online.utils import make_ain, ptoc, tic, tiffs2array, toc
from caiman.source_extraction import cnmf
import logging
from pathlib import Path
import caiman as cm
import tensorflow as tf
from glob import glob
from caiman_online.realtime.server import RealTimeServer
from caiman_online.networking import send_this
import time
import json
import warnings

if tf.__version__[0] == '1':
    tf.enable_eager_execution()
    
import os
os.environ['MKL_NUM_THREADS'] = '1'
os.environ['OPENBLAS_NUM_THREADS'] = '1'

__all__ = ['send_setup', 'send_quit', 'send_frames', 'send_stop', 'send_frames_ws']

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

FOLDER = 'e:/caiman_scratch/ori4'
NPLANES = 3
NCHANNELS = 2
PLANE2USE = 0
MM3D_PATH = glob(FOLDER + '/*.mat')[0]

IP = 'localhost'
PORT = 5000

# motion correction and CNMF 
dxy = (1.5, 1.5) # spatial resolution in x and y in (um per pixel)
max_shift_um = (15., 15.) # maximum shift in um
patch_motion_xy = (100., 100.) # patch size for non-rigid correction in um

params = {
    # CNMF
    'fr': 6.36,
    'p': 1,  # deconv 0 is off, 1 is slow, 2 is fast
    'nb': 3,  # background compenents -> nb: 3 for complex
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
    # 'optimize_g': True,
    
    # motion
    'gSig_filt': (7, 7), # high pass spatial filter for motion correction
    'nonneg_movie': True,
    'niter_rig': 1,
    'pw_rigid': True,  # piece-wise rigid flag, slower
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
    'max_num_added':0,
    'sniper_mode': False,
    'test_both': False,
    'ring_CNN': False,
    'batch_update_suff_stat':True,
    'update_freq':200,
    'save_online_movie':True,
    'show_movie': False,
}

@tictoc
def load_init(file_path):
    """
    Concatenate a few tiffs for caiman to seed off of for online processing.

    Args:
        file_path (str): path to the tiffs to make the init
    """
    
    logger.info('Making an init...')
    file_path = Path(file_path)
    init_tiffs = list(file_path.glob('*.tif'))[:20]
    mov = tiffs2array(init_tiffs,
                      x_slice=slice(120,392),
                      y_slice=slice(0,512),
                      t_slice=slice(PLANE2USE*NCHANNELS,-1,NCHANNELS*NPLANES)
                      )
    logger.info(f'Movie dims are {mov.shape}')
    m = cm.movie(mov.astype('float32'))
    fname_init = m.save('init.mmap', order='C')
    return fname_init

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

def load_big_movie_stream2(file_path):
    logger.info('Making big movie array for stream.')
    file_path = Path(file_path)
    stream_tiffs = list(file_path.glob('*.tif'))
    mov = tiffs2array(stream_tiffs,
                      x_slice=slice(120,392),
                      y_slice=slice(0,512),
                      t_slice=slice(PLANE2USE*NCHANNELS,-1,NCHANNELS*NPLANES)
                      )
    logger.info(f'Movie dims are {mov.shape}')
    return mov
    
def test_realtime():
    logger.info('Testing real-time caiman OnACID (single plane)')
    logger.info(f'Using init method {params["init_method"]}')
    params['fnames'] = load_init(FOLDER)
    opts = cnmf.params.CNMFParams(params_dict=params)
    cnm = cnmf.online_cnmf.OnACID(dview=None, params=opts)
    if params['init_method'] == 'seeded':
        Ain = make_ain(MM3D_PATH, PLANE2USE, 120,392)
        cnm.estimates.A = Ain
    t = tic()
    logger.info('Starting the init batch')
    cnm.initialize_online()
    t2 = toc(t)
    logger.info(f'Init done in {t2}s')
    
def send_frames(rate):
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
             
def send_quit():
    out = {
        'kind':'quit'
    }
    send_this(out, IP, PORT)
        
def send_setup():
    out = {
        'kind':'setup',
        'nchannels':NCHANNELS,
        'nplanes':NPLANES,
        'frameRate':6.36
    }
    send_this(out, IP, PORT)
    
def send_stop():
    out = {
        'kind':'stop'
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

    
# def test_realtime_server():
#     logger.info('Testing real-time caiman OnACID (single plane) as a server.')
#     logger.info(f'Using init method {params["init_method"]}')
#     params['fnames'] = load_init(FOLDER)

#     logger.info('Spinning up RealTimeServer...')
#     if params['init_method'] == 'seeded':
#         serve = RealTimeServer(IP, PORT, 'e:/caiman_online/fake_server', params, Ain_path=MM3D_PATH)
#     else:
#         serve = RealTimeServer(IP, PORT, 'e:/caiman_online/fake_server', params)

def test_realtime_server():
    serve = RealTimeServer('localhost', 5000, 'e:/caiman_scratch/fake_server', params, Ain_path=MM3D_PATH)


    
if __name__ == '__main__':
    test_realtime_server()