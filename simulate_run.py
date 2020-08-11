"""
Holds franken rig settings in effort to keep rig-based conflicts out
of run_caiman_ws.py
"""
import warnings

warnings.filterwarnings(
    action='ignore',
    lineno=545,
    module='tensorboard'
)

from glob import glob

from run_caiman_ws import SISocketServer
from caiman_main import OnlineAnalysis

# for running the webserver
ip = 'localhost'
port = 5003

# folder locations
srv_folder = 'E:/caiman_scratch/fake_server' # path to caiman data output folder on server
template_path = glob('E:/caiman_scratch/template/*.mat')[0] # path to mm3d file
tiff_folder = 'E:/caiman_scratch/data/' # this is where the tiffs are

# other custom options
batch_size = 16 # how many tiffs to run together
x_start = 100
x_end = 400
channels = 2 # default, overwritten if send setup is being used
planes = 3 # default, overwritten if send setup is being used

# motion correction
dxy = (1.5, 1.5) # spatial resolution in x and y in (um per pixel)
max_shift_um = (12., 12.) # maximum shift in um
patch_motion_xy = (100., 100.) # patch size for non-rigid correction in um

image_params = {
    'channels': channels,
    'planes': planes,
    'x_start': x_start, 
    'x_end': x_end,
    'folder': tiff_folder
}

caiman_params = {
    'fr': 6.36,  # imaging rate in frames per second, per plane
    'overlaps': (24, 24),
    'max_deviation_rigid': 3,
    'p': 1,  # deconv 0 is off, 1 is slow, 2 is fast
    'nb': 3,  # background compenents -> nb: 3 for complex
    'decay_time': 1.0,  # sensor tau
    'gSig': (5, 5),  # expected half size of neurons in pixels, very important for proper component detection
    'only_init': False,  # has to be `False` when seeded CNMF is used
    'rf': None,  # half-size of the patches in pixels. Should be `None` when seeded CNMF is used.
    'pw_rigid': True,  # piece-wise rigid flag
    'ssub': 1,
    'tsub': 1,
    'do_merge': False, # new found param, testing
    'update_background_components': False,
    'merge_thr': 0.9999,
    'num_frames_split': 20,
    'border_nan': 'copy',
    'max_shifts': [int(a/b) for a, b in zip(max_shift_um, dxy)],
    'strides': tuple([int(a/b) for a, b in zip(patch_motion_xy, dxy)])
}



# warnings.filterwarnings(
#     action='ignore',
#     lineno=1963, 
#     module='scipy')

# warnings.filterwarnings(
#     action='ignore',
#     lineno=535, 
#     module='tensorflow')

# run everything
if __name__ == '__main__':
    expt = OnlineAnalysis(caiman_params, **image_params)
    expt.make_templates(template_path)
    srv = SISocketServer(ip, port, expt, srv_folder, batch_size)