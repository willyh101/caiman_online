from glob import glob
from caiman_online.utils import make_ain
from caiman_online.pipelines import SeededPipeline
import logging

LOGFILE = 'E:/caiman_scratch/ori2/caiman/out/pipeline_test.log'
LOGFORMAT = ''
logging.basicConfig(level=logging.ERROR)
logger = logging.getLogger('caiman_online')
logger.setLevel(logging.DEBUG)

folder =  'E:/caiman_scratch/ori2'
mm3d_path = glob('E:/caiman_scratch/ori2/*.mat')[0]
nchannels = 2
nplanes = 3
xslice = slice(100,400)
batch_size_tiffs = 30

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
    'gSig': (5, 5),  # expected half size of neurons in pixels, very important for proper component detection
    'only_init': False,  # has to be `False` when seeded CNMF is used
    'rf': None,  # half-size of the patches in pixels. Should be `None` when seeded CNMF is used.
    'ssub': 1,
    'tsub': 1,
    # 'do_merge': True, # new found param, testing
    'update_background_components': True,
    'merge_thr': 0.999,
    # 'optimize_g': True,
    
    # motion
    'gSig_filt': (7, 7), # high pass spatial filter for motion correction
    'nonneg_movie': True,
    # 'niter_rig': 1,
    'pw_rigid': False,  # piece-wise rigid flag, slower
    'max_deviation_rigid': 3,
    'overlaps': (24, 24),
    'max_shifts': [int(a/b) for a, b in zip(max_shift_um, dxy)],
    'strides': tuple([int(a/b) for a, b in zip(patch_motion_xy, dxy)]),
    'num_frames_split': 50,
    'border_nan': 'copy',
    
    # online
    # 'init_method': 'seeded',
    # 'epochs': 2,
    # 'show_movie': False,
    # 'motion_correct': True,
    # 'expected_comps': 500,
    # 'update_num_comps':False,
    # 'max_num_added':0,
}

class TestSeededPipeline(SeededPipeline):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
    def get_tiffs(self):
        all_tiffs = list(self.folder.glob('*.tif*'))
        chunked = [all_tiffs[i:i + self.batch_size_tiffs] for i in range(0, len(all_tiffs), self.batch_size_tiffs)]
        tiffs = chunked[self.iters]
        splits = self.validate_tiffs(tiffs)
        logger.debug(f'Processing files: {tiffs}')
        return tiffs, splits

def test_seeded():
    logger.info('Running test of seeded pipeline.')
    Ain = [make_ain(mm3d_path, p, 100, 400) for p in range(nplanes)]
    seeded = TestSeededPipeline(folder, params, nchannels, nplanes, 
                            x_start=100, x_end=400, Ain=Ain, batch_size_tiffs=batch_size_tiffs)
    
    ntiffs = len(glob(folder + '/*.tif*'))
    rounds = ntiffs//batch_size_tiffs
    
    for _ in range(rounds):
        seeded.fit_batch()

if __name__ == '__main__':
    test_seeded()