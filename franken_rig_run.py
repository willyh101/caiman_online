"""
Holds franken rig settings in effort to keep rig-based conflicts out
of run_caiman_ws.py

But should just run everything automatically.
"""
import warnings
from run_caiman_ws import SISocketServer
from caiman_main import OnlineAnalysis

ip = '192.168.10.104'
port = 5002

srv_folder = 'F:/caiman_out' # path to caiman data output folder on server

template_path = 'D:/caiman_temp/template/makeMasks3D_img.mat' # path to mm3d file
tiff_folder = 'D:/Will/20200805/i140_2/e3/' # not needed if using send_setup
tiffs_per_batch = 10

dxy = (1.5, 1.5) # spatial resolution in x and y in (um per pixel)
max_shift_um = (12., 12.) # maximum shift in um
patch_motion_xy = (100., 100.) # patch size for non-rigid correction in um

image_params = {
    'channels': 2,
    'planes': 3,
    'x_start': 100,
    'x_end': 400,
    'folder': tiff_folder, # this is where the tiffs are, make a sub-folder named out to store output data
}

caiman_params = {
    'fr': 6.36,  # imaging rate in frames per second, per plane
    'overlaps': (24, 24),
    'max_deviation_rigid': 3,
    'p': 1,  # deconv 0 is off, 1 is slow, 2 is fast
    'nb': 2,  # background compenents -> nb: 3 for complex
    'decay_time': 1.0,  # sensor tau
    'gSig': (5, 5),  # expected half size of neurons in pixels, very important for proper component detection
    'only_init': False,  # has to be `False` when seeded CNMF is used
    'rf': None,  # half-size of the patches in pixels. Should be `None` when seeded CNMF is used.
    'pw_rigid': True,  # piece-wise rigid flag
    'ssub': 1,
    'tsub': 1,
    'merge_thr': 0.999,
    'num_frames_split': 20,
    'border_nan': 'copy',
    'max_shifts': [int(a/b) for a, b in zip(max_shift_um, dxy)],
    'strides': tuple([int(a/b) for a, b in zip(patch_motion_xy, dxy)])
}

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
    expt = OnlineAnalysis(caiman_params, **image_params)
    expt.make_templates(template_path)
    srv = SISocketServer(ip, port, expt, srv_folder, batch_size=tiffs_per_batch)