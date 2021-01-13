"""
Holds franken rig settings in effort to keep rig-based conflicts out
of run_caiman_ws.py

But should just run everything automatically.

***
It is important to check and make sure that the xrange matches what you put in MM3D.
***

"""
import warnings
import logging
from caiman_online.comm import SIWebSocketServer
from caiman_online.pipelines import OnAcidPipeline, SeededPipeline

ip = 'localhost'
port = 5003

# srv_folder = 'F:/caiman_out' # path to caiman data output folder on server
srv_folder = 'F:/caiman_out'

template_path = 'D:/caiman_temp/template/makeMasks3D_img.mat' # path to mm3d file
tiff_folder = 'D:/Will/20200805/i140_2/e3/' # not needed if using send_setup
tiffs_per_batch = 100

x_start = 120
x_end = 329
nchannels = 2
nplanes = 3

dxy = (1.5, 1.5) # spatial resolution in x and y in (um per pixel)
max_shift_um = (12., 12.) # maximum shift in um
patch_motion_xy = (100., 100.) # patch size for non-rigid correction in um

image_params = {
    'nchannels': nchannels,
    'nplanes': nplanes,
    'x_start': x_start,
    'x_end': x_end,
    'folder': tiff_folder, # this is where the tiffs are, make a sub-folder named out to store output data
    'batch_size_tiffs': tiffs_per_batch
}

caiman_params = {
    'fr': 6.36,  # imaging rate in frames per second, per plane
    'overlaps': (24, 24),
    'max_deviation_rigid': 3,
    'p': 1,  # deconv 0 is off, 1 is slow, 2 is fast
    'nb': 3,  # background compenents -> nb: 3 for complex
    'decay_time': 1.0,  # sensor tau
    'gSig': (7, 7),  # expected half size of neurons in pixels, very important for proper component detection
    'only_init': False,  # has to be `False` when seeded CNMF is used
    'rf': None,  # half-size of the patches in pixels. Should be `None` when seeded CNMF is used.
    'pw_rigid': False,  # piece-wise rigid flag
    'ssub': 1,
    'tsub': 1,
    'do_merge': False,
    'merge_thr': 0.999,
    'update_background_components': True,
    'gSig_filt': (7, 7),
    'num_frames_split': 50,
    'border_nan': 'copy',
    'max_shifts': [int(a/b) for a, b in zip(max_shift_um, dxy)],
    'strides': tuple([int(a/b) for a, b in zip(patch_motion_xy, dxy)])
}

LOGFORMAT = '{relativeCreated:08.0f} - {levelname:8} - [{module}:{funcName}:{lineno}] - {message}'
logging.basicConfig(level=logging.ERROR, format=LOGFORMAT, style='{')
logger = logging.getLogger('caiman_online')
logger.setLevel(logging.DEBUG)

warnings.filterwarnings(
    action='ignore',
    lineno=1963, 
    module='scipy')

warnings.filterwarnings(
    action='ignore',
    lineno=535, 
    module='tensorflow')

# run everything
if __name__ == '__main__':
    expt = SeededPipeline(params=caiman_params, **image_params)
    expt.make_templates(template_path)
    srv = SIWebSocketServer(ip, port, srv_folder, tiffs_per_batch, expt)