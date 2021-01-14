from glob import glob
from caiman_online.utils import make_ain
from caiman_online.pipelines import OnAcidPipeline, SeededPipeline
import logging
import platform

drive = 'e'
folder = 'caiman_scratch/20210113_tests'

if platform.system() == 'Windows':
    folder = drive + ':/' + folder
else:
    folder = '/mnt/' + drive + '/' + folder

# LOGFILE = folder + '/caiman/out/pipeline_test.log'
LOGFORMAT = '{relativeCreated:08.0f} - {levelname:8} - [{module}:{funcName}:{lineno}] - {message}'
# logging.basicConfig(level=logging.ERROR, format=LOGFORMAT, filename=LOGFILE, style='{')
logging.basicConfig(level=logging.ERROR, format=LOGFORMAT, style='{')
logger = logging.getLogger('caiman_online')
logger.setLevel(logging.DEBUG)

# logger.debug(f"MM3D Path: {folder + '/*.mat'}")
mm3d_path = glob(folder + '/*.mat')[0]
nchannels = 2
nplanes = 3
xslice = slice(120,392)
batch_size_tiffs = 36

BATCH_SIZES_TO_TEST = [36]

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
    # 'optimize_g': True,
    
    # motion
    'gSig_filt': (7, 7), # high pass spatial filter for motion correction
    'nonneg_movie': True,
    'niter_rig': 1,
    'pw_rigid': False,  # piece-wise rigid flag, slower
    'max_deviation_rigid': 3,
    'overlaps': (24, 24),
    'max_shifts': [int(a/b) for a, b in zip(max_shift_um, dxy)],
    'strides': tuple([int(a/b) for a, b in zip(patch_motion_xy, dxy)]),
    'num_frames_split': 80,
    'border_nan': 'copy',
    
    # online
    'init_method': 'seeded',
    'epochs': 2,
    'show_movie': False,
    'motion_correct': True,
    'expected_comps': 300,
    'update_num_comps':False,
    'max_num_added':0,
    'sniper_mode': False,
    'test_both': False,
    'ring_CNN': False
}

class TestSeededPipeline(SeededPipeline):
    def get_tiffs(self):
        all_tiffs = list(self.folder.glob('*.tif*'))
        chunked = [all_tiffs[i:i + self.batch_size_tiffs] for i in range(0, len(all_tiffs), self.batch_size_tiffs)]
        tiffs = chunked[self.iters]
        splits = self.validate_tiffs(tiffs)
        logger.debug(f'Processing files: {tiffs}')
        return tiffs, splits
    
class TestOnAcidPipeline(OnAcidPipeline):
    def get_tiffs(self):
        all_tiffs = list(self.folder.glob('*.tif*'))
        chunked = [all_tiffs[i:i + self.batch_size_tiffs] for i in range(0, len(all_tiffs), self.batch_size_tiffs)]
        tiffs = chunked[self.iters]
        splits = self.validate_tiffs(tiffs)
        logger.debug(f'Processing files: {tiffs}')
        return tiffs, splits

def test_seeded():
    logger.info('Running test of seeded caiman batch pipeline.')
    Ain = [make_ain(mm3d_path, p, 120, 392) for p in range(nplanes)]
    seeded = TestSeededPipeline(folder, params, nchannels, nplanes, 
                            x_start=120, x_end=392, Ain=Ain, batch_size_tiffs=batch_size_tiffs)
    
    ntiffs = len(glob(folder + '/*.tif*'))
    rounds = ntiffs//batch_size_tiffs
    
    for _ in range(rounds):
        seeded.fit_batch()
        
def test_online():
    logger.info(f'Starting OnACID test runs with batch sizes: {BATCH_SIZES_TO_TEST}')
    logger.warning('Note: out data will be overwritten each go-round, so be sure to check everything if analyzing after.')
    
    for bs in BATCH_SIZES_TO_TEST:
        try:
            logger.info(f'Running test of seeded OnACID pipeline with BATCH SIZE = {bs}')
            Ain = [make_ain(mm3d_path, p, 120, 392) for p in range(nplanes)]
            seeded = TestOnAcidPipeline(folder, params, nchannels, nplanes, 
                                    x_start=120, x_end=392, Ain=Ain, batch_size_tiffs=bs)
            
            ntiffs = len(glob(folder + '/*.tif*'))
            rounds = ntiffs//bs
            
            for _ in range(rounds):
                seeded.fit_batch()
        except:
            logger.fatal(f'****** FAILED: Test OnACID run with batch size {bs} failed! ******', exc_info=True)
            continue
        else:
            logger.fatal(f'****** PASSED: Test OnACID run with batch size {bs} passed! ******')
            continue
        
def test_online_parallel():
    from caiman_online.parallel import OnAcidParallel
    logger.info(f'Starting OnACID test runs with batch sizes: {BATCH_SIZES_TO_TEST}')
    logger.warning('Note: out data will be overwritten each go-round, so be sure to check everything if analyzing after.')
    
    for bs in BATCH_SIZES_TO_TEST:
        try:
            logger.info(f'Running test of seeded OnACID pipeline with BATCH SIZE = {bs}')
            Ain = [make_ain(mm3d_path, p, 120, 392) for p in range(nplanes)]
            seeded = OnAcidParallel(folder, params, nchannels, nplanes, 
                                    x_start=120, x_end=392, Ain=Ain, batch_size_tiffs=bs)
            
            ntiffs = len(glob(folder + '/*.tif*'))
            rounds = ntiffs//bs
            
            for _ in range(rounds):
                seeded.fit_batch()
        except:
            logger.fatal(f'****** FAILED: Test OnACID run with batch size {bs} failed! ******', exc_info=True)
            continue
        else:
            logger.fatal(f'****** PASSED: Test OnACID run with batch size {bs} passed! ******')
            continue

if __name__ == '__main__':
    # test_seeded()
    # test_online()
    test_online_parallel()