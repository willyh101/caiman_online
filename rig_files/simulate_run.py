"""
Holds franken rig settings in effort to keep rig-based conflicts out
of server.py
"""

from glob import glob

from caiman_online.server import SISocketServer
from caiman_online.main import OnlineAnalysis

# for running the webserver
ip = 'localhost' # IP address of host, if not using DAQ to send trial data, 'localhost' is fine
port = 5003 # any port is fine

# folder locations
srv_folder = 'E:/caiman_scratch/fake_server' # path to caiman data output folder on server
template_path = glob('E:/caiman_scratch/template/old/*.mat')[0] # path to mm3d file

# other custom options
x_start = 100 # remove left side artifact
x_end = 400 # stop here to remove right side artifact

# required settings if sendSetup is not being used
# these will be overwritten by sendSetup
batch_size = 5 # how many tiffs wait for to run together, in general should be > 500 frames
frame_rate = 6.36
channels = 2 
planes = 3
tiff_folder = 'E:/caiman_scratch/ori/' # this is where the tiffs are

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
    'fr': frame_rate,
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

# run everything
if __name__ == '__main__':
    expt = OnlineAnalysis(caiman_params, **image_params) # makes an online analysis instance
    expt.make_templates(template_path) # segments based off of MM3D
    srv = SISocketServer(ip, port, expt, srv_folder, batch_size) # starts a websocket server 