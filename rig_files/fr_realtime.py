"""
USE THIS TO RUN CAIMAN_ONLING ON FRANKENRIG IN REALTIME

But most things should just run everything automatically with the following exceptions.

***
- Set 'x_start' and 'x_end' to match what you put into makeMasks3D.
- Ensure that nchannels and nplanes is updated.
- Other than that, everything is either updated by sendSetup (triggered by acqArmed) or is defaulted
***

When you are ready to go, just press the green play button at the top right.

The conda environment should change to caiman-online automatically. If it doesn't (throws
module not found error or something weird), hit ctrl+shift+p and start typing in 
'python select interpreter' and then select 'Python: Select Interpreter'. In the dropdown
then select 'Python 3.7.9 64-bit ('caiman-online':conda). Then try again.

To enable caiman callbacks in MATLAB, run the command 'caiman'. This will setup and enable the SI user functions.

When you are done, type in 'quitcaiman' to disable and remove the callbacks.

If you want to run caiman again, be sure to launch a new session from VSCode! (no need to re-enable the callbacks
in scanimage or anything)

If it breaks and you need to restart, you should be able to click in the shell below and ctrl+c to
kill the server. If that doesn't work, clicking the garbage can in the shell should kill it.

"""
import warnings
import logging
from caiman_online.comm import SIWebSocketServer
from caiman_online.pipelines import OnAcidPipeline, SeededPipeline


### ----- THINGS YOU HAVE TO CHANGE! ----- ###
# Set these first to match makeMasks3D!!!
# I recommend using removing 110 pixels from each side. Maybe 120 for holography. Maybe less for vis stim. But 
# it has to match whatever you did in MakeMasks3D.
x_start = 110
x_end = 512-110
nchannels = 2
nplanes = 3




### ----- THINGS YOU PROBABLY DON'T NEED TO CHANGE ----- ###

# networking options
# this computers IP (should be static at 192.168.10.104)
# the corresponding IP addresses in networking.py must match exactly
# you could also use 'localhost' if not sending any info from the DAQ
ip = '192.168.10.104'
port = 5003

# path to caiman data output folder on server, doesn't need to change as long as the server is there
# (it doesn't have to be a server folder, is just convenient for transferring to the DAQ)
# outputs are also save in the epoch folder with your tiffs
srv_folder = 'F:/caiman_out'

# motion correction params
dxy = (1.5, 1.5) # spatial resolution in x and y in (um per pixel)
max_shift_um = (12., 12.) # maximum shift in um
patch_motion_xy = (100., 100.) # patch size for non-rigid correction in um

# CNMF params
background = 3 # number of background components (default, 2 or 3).
# a bigger number here decreases the background but too much can reduce the signal

# other file pathing
template_path = 'D:/caiman_temp/template/makeMasks3D_img.mat' # path to mm3d file, must be specified, but shouldn't change
tiff_folder = 'D:/Will/20200805/i140_2/e3/' # not needed if using send_setup
tiffs_per_batch = 50 # default value, will be overwritten by using send_setup if using batch algo (not onacid)
frame_rate = 6.36 # default value, is overwritten by send_setup

# logging level (print more or less processing info)
# change logger.setLevel(logging.DEBUG) for more or logger.setLevel(logging.INFO) for less
LOGFORMAT = '{relativeCreated:08.0f} - {levelname:8} - [{module}:{funcName}:{lineno}] - {message}'
logging.basicConfig(level=logging.ERROR, format=LOGFORMAT, style='{')
logger = logging.getLogger('caiman_online')
logger.setLevel(logging.DEBUG) # more
# logger.setLevel(logging.INFO) # less


image_params = {
    'nchannels': nchannels,
    'nplanes': nplanes,
    'x_start': x_start,
    'x_end': x_end,
    'folder': tiff_folder, # this is where the tiffs are, make a sub-folder named out to store output data
    'batch_size_tiffs': tiffs_per_batch
}

caiman_params = {
    'fr': frame_rate,  # imaging rate in frames per second, per plane
    'overlaps': (24, 24),
    'max_deviation_rigid': 3,
    'p': 1,  # deconv 0 is off, 1 is slow, 2 is fast
    'nb': background,  # background compenents -> nb: 3 for complex
    'decay_time': 1.0,  # sensor tau
    'gSig': (7, 7),  # expected half size of neurons in pixels, very important for proper component detection
    'only_init': False,  # has to be `False` when seeded CNMF is used
    'rf': None,  # half-size of the patches in pixels. Should be `None` when seeded CNMF is used.
    'pw_rigid': False,  # piece-wise rigid flag
    'ssub': 1,
    'tsub': 1,
    'do_merge': False,
    'merge_thr': 0.999,
    'update_background_components': False,
    'gSig_filt': (7, 7),
    'num_frames_split': 50,
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
    expt = OnAcidPipeline(params=caiman_params, **image_params)
    expt.make_templates(template_path)
    srv = SIWebSocketServer(ip, port, srv_folder, tiffs_per_batch, expt)