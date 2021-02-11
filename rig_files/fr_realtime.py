"""
USE THIS TO RUN CAIMAN_ONLING ON FRANKENRIG IN REALTIME

In regards to settings, most things should just run everything automatically with the following exceptions.

***
- Set 'x_start' and 'x_end' to match what you put into makeMasks3D.
- Other than that, everything is either updated by sendSetup (triggered by acqArmed) or is defaulted
- Ensure that makeMasks3D saves 'makeMasks3D_img.mat' into 'D:/caiman_temp/template/makeMasks3D_img'
   (this is setup by default on most mm3d scripts now...)
***

Instructions:
============

1. Take an image of around 500 frames. This will be used to initialize the
   online algorithm. It should be in the only tiff in the folder that you will
   be writing to for this epoch.

2. Start the caiman server (hit the green play button). The server will start
   and wait for signal from ScanImage.

3. In MATLAB/ScanImage, run 'caiman' from the command line. This will setup all the
   callbacks and enable them.

4. Hit LOOP in ScanImage. This will trigger caiman to grab the tiff that is in the
   current directory and start processing that file for initializing OnACID for each
   plane. For now, it will run each plane serially, and for 500 frames it should take about 
   30-40 seconds each plane.

5. Don't do anything else in SI until it says: [INFO] Ready to process online!

6. When caiman is ready to go, you can trigger ScanImage to start running. Every time there is
   and acqDone event (each trial), caiman will get the most recent tiff from the folder and
   add the frames to the processing queue for each plane. You will see updates every 500 frames
   or so about how fast it is processing each frame. It should be >= realtime (per plane). It
   is expected that processing time will decrease slightly with more frames.

7. When you are done with your experiment just hit ABORT when ScanImage is idle like you 
   normally would. This will put a stop signal into the queues to signal the end and to do
   final processing on the files. The queues might need to catch up if there is any lag.
   DO NOT QUIT CAIMAN until you see '[SUCCESS] Done saving! You can quit now.'!!

8. Try ctrl-c or hit the trashcan button where caiman is running to quit if it doesn't automatically.
    -> If you are done with caiman, run 'quitcaiman' from the MATLAB commandline to remove the callbacks.
    -> If you are running another caiman epoch, no need to do anything in MATLAB, just launch another 
       caiman session from VSCode.
    -> For now, be sure to put the seed tiff into the new folder for the next epoch.


Gotchas:
=======
- Right now you have to manually copy and paste the original seed file into each new folder.
- Everytime caiman runs for a new epoch, it will have to re-initialize off of that seed file.
- In the future, we can actually use the previous epochs results as the seed for the new epoch.


Output files:
============
Files get output into 2 locations: the epoch directory with the tiffs (TIFFS/caiman/out) 
and 'srv_folder' which is specified when starting caiman (it does not have to be a server, 
just a common place to store the outputs, I use the server bc it's easy to transfer to the DAQ).

> SERVER FILES <
* data.mat
    matfile with:
        tracesCaiman  -> the full-length traces (2D) of the experiment, raw data (cells x frames)
        psthsCaiman   -> the min subtracted and normalized traces cut trialwise (3D) (trials x cell x frames)
        lengthsCaiman -> length of each trial
* traces.npy
    2D full length and unprocessed traces (cells x frames)
* psths.npy
    3D min-subtracted and normalized traces trialwise (trials x cell x frames)
* raw_data.json
    JSON with:
        c: deconvolved/denoised traces (not spikes), standard caiman output traces
        splits: lengths of each trial
* traces_data.json
    JSON with:
        traces: the 3D processed trialwise data

> CAIMAN/OUT FILES <
* a hdf5 of the caiman object for each plane
* a JSON with most of the relevant data for each plane (incl. spatial and temporal components)


Other Notes:
===========
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
from caiman_online.realtime.server import RealTimeServer


### ----- THINGS YOU HAVE TO CHANGE! ----- ###
# Set these first to match makeMasks3D!!!
# I recommend using removing 110 pixels from each side. Maybe 120 for holography. Maybe less for vis stim. But 
# it has to match whatever you did in MakeMasks3D.
# also set the max number of frames you expect, is an upper limit so it can be really high (used for memory allocation)
x_start = 110
x_end = 512-110

y_start = 0
y_end = 512

max_frames = 20000


### ----- THINGS YOU PROBABLY DON'T NEED TO CHANGE ----- ###

# networking options
# this computers IP (should be static at 192.168.10.104)
# the corresponding IP addresses in networking.py must match exactly
# you could also use 'localhost' if not sending any info from the DAQ
ip = 'localhost'
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


# caiman specific
# some specified earlier, can make more changes here
caiman_params = {
    # CNMF
    'fr': frame_rate,
    'p': 1,  # deconv 0 is off, 1 is slow, 2 is fast
    'nb': background,  # background compenents -> nb: 3 for complex
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
    'motion_correct': True,
    'expected_comps': 300,
    'update_num_comps':False,
    'max_num_added': 0,
    'sniper_mode': False,
    'simultaneously': True,
    'test_both': False,
    'ring_CNN': False,
    'batch_update_suff_stat':True,
    'update_freq': 100,
    'save_online_movie':False,
    'show_movie': False,
    'n_refit': 1,
    'dist_shape_update':False
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
    RealTimeServer(ip, port, srv_folder, caiman_params,
                   Ain_path = 'D:/caiman_temp/template/makeMasks3D_img.mat',
                   xslice = slice(x_start, x_end),
                   yslice = slice(y_start, y_end),
                   num_frames_max=max_frames
                   )