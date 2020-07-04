import caiman as cm
from caiman.source_extraction.cnmf import cnmf as cnmf
from caiman.source_extraction.cnmf import params as params
from glob import glob
from ScanImageTiffReader import ScanImageTiffReader
import numpy as np
import os

from utils import tic, toc, ptoc, remove_artifacts, mm3d_to_img, cleanup_hdf5, cleanup_mmaps

dxy = (1.5, 1.5) # spatial resolution in x and y in (um per pixel)
max_shift_um = (12., 12.) # maximum shift in um
patch_motion_xy = (100., 100.) # patch size for non-rigid correction in um

image_params = {
    'channels': 2,
    'planes': 3,
    'x_start': 100,
    'x_end': 400,
    'folder': 'E:/caiman tests/stims/' # this is where the tiffs are, make a sub-folder named out to store output data
}

caiman_params = {
    'fr': 6,  # imaging rate in frames per second, per plane
    'overlaps': (24, 24),
    'max_deviation_rigid': 3,
    'p': 0,  # deconv 0 is off, 1 is slow, 2 is fast
    'nb': 2,  # background compenents -> nb: 3 for complex
    'decay_time': 1.0,  # sensor tau
    'gSig': (5, 5),  # expected half size of neurons in pixels, very important for proper component detection
    'only_init': False,  # has to be `False` when seeded CNMF is used
    'rf': None,  # half-size of the patches in pixels. Should be `None` when seeded CNMF is used.
    'pw_rigid': True,  # piece-wise rigid flag
    'ssub': 2,
    'tsub': 1,
    'merge_thresh': 0.9,
    'num_frames_split': 50,
    'border_nan': 'copy',
    'max_shifts': [int(a/b) for a, b in zip(max_shift_um, dxy)],
    'strides': tuple([int(a/b) for a, b in zip(patch_motion_xy, dxy)])
}

class OnlineAnalysis:
    def __init__(self, caiman_params, channels, planes, x_start, x_end, folder):
        self.channels = channels
        self.planes = planes
        self.x_start = x_start
        self.x_end = x_end
        self.folder = folder
        self.caiman_params = caiman_params
        self.structural_image = None
        
        # derived params
        self.folder_tiffs = folder + '*.tif*'
        self.save_h5df_folder = folder + 'out/'
        print('Setting up caiman...')
        self.opts = params.CNMFParams(params_dict=self.caiman_params)
        self.batch_size = 1 # can be overridden by expt runner
        self.fnumber = 0
        self.bad_tiff_size = 10
        
        # other init things to do
        # start server
        print('Starting local cluster...', end = ' ')
        self.c, self.dview, self.n_processes = cm.cluster.setup_cluster(
            backend='local', n_processes=None, single_thread=False)
        print('done.')
        # cleanup
        cleanup_mmaps(self.folder)
        cleanup_hdf5(self.save_h5df_folder)
        
        
    @property
    def tiffs(self):
        self._tiffs = glob(self.folder_tiffs)
        return self._tiffs
    
    def set_structural_image(self, image_path):
        """
        Sets the structural image for use. Must be a single frame.

        Args:
            image_path (np.array): path to mean structural image
        """
        with ScanImageTiffReader(image_path) as reader:
            data = reader.data()
            assert data.ndim == 2, 'Image must be 2D'
            # assert data.shape
        self.structural_image = data
        
    def prep_mm3d_template(self, mm3d_file):
        self.mm3d_file = mm3d_file # save for later
        mm3d_img = mm3d_to_img(mm3d_file, chan=0) # red channel
        return remove_artifacts(mm3d_img, self.x_start, self.x_end)[0,:,:]
        
        
    def _extract_rois_caiman(self, image):
        self.Ain = cm.base.rois.extract_binary_masks_from_structural_channel(image, 
                                                                    min_area_size = 20, 
                                                                    min_hole_size = 10, 
                                                                    gSig = 5, 
                                                                    expand_method='dilation')[0]
        
        
    def segment(self):
        if self.structural_image is None:
            raise ValueError('No structural image provided!')
        
        t = tic()
        print('Starting segmentation on a provided template...')
        self._extract_rois_caiman(self.structural_image)
        ptoc(t, start_string='done in')
        
        
    def segment_mm3d(self):
        """
        Performs makeMasks3D segmentation.
        """
        t = tic()
        print('Starting makeMasks3D segmentation...', end=' ')
        image = self.prep_mm3d_template(glob('E:/caiman tests/stimtest/*.mat')[0])
        self._extract_rois_caiman(image)
        ptoc(t, start_string='done in')
        
        
    def make_mmap(self, files):
        t = tic()
        print('Memory mapping current file...', end=' ')
        self.memmap = cm.save_memmap(
            files,
            base_name=f'MAP{self.fnumber}', 
            order='C',
            slices=[
                slice(0, -1, self.channels * self.planes),
                slice(0, 512),
                slice(self.x_start, self.x_end)
            ]
        )
        print(f'done. Took {toc(t):.4f}s')
        
        
    def make_movie(self):
        """
        Load memmaps and make the movie.
        """
        Yr, dims, T = cm.load_memmap(self.memmap)
        self.movie = np.reshape(Yr.T, [T] + list(dims), order='C')
        
        
    def validate_tiffs(self, bad_tiff_size=5):
        """
        Finds the weird small tiffs and removes them. Arbitrarily set to <5 frame because it's not too
        small and not too big.

        Args:
            bad_tiff_size (int, optional): Size tiffs must be to not be trashed. Defaults to 5.
        """
        
        crap = []
        for tiff in self.tiffs:
            with ScanImageTiffReader(tiff) as reader:
                data = reader.data()
                if data.shape[0] < self.bad_tiff_size:
                    crap.append(tiff)
        for crap_tiff in crap:
            os.remove(crap_tiff)
                    
        
    def do_fit(self):
        """
        Perform the CNMF calculation.
        """
        t = tic()
        print('Starting motion correction and CNMF...')
        cnm_seeded = cnmf.CNMF(self.n_processes, params=self.opts, dview=self.dview, Ain=self.Ain)
        cnm_seeded.fit(self.movie)
        cnm_seeded.save(self.save_h5df_folder + f'caiman_data_{self.fnumber}.hdf5')
        print(f'CNMF fitting done. Took {toc(t):.4f}s')
        
        
    def do_next_group(self):
        """
        Do the next iteration on a group of tiffs.
        """
        self.validate_tiffs()
        self.these_tiffs = self.tiffs[-self.batch_size:None]
        print(f'processing files: {self.these_tiffs}')
        self.opts.change_params(dict(fnames=self.these_tiffs))
        self.make_mmap(self.these_tiffs) # gets the last x number of tiffs
        self.make_movie()
        self.do_fit()
        self.advance(by=self.batch_size)


    def do_final_fit(self):
        """
        Do the last fit on all the tiffs in the folder. This makes an entirely concenated cnmf fit.
        """
        
        print(f'processing files: {self.tiffs}')
        self.opts.change_params(dict(fnames=self.tiffs))
        
        # all_memmaps = glob(self.folder + '*.mmap')
        # memmap = cm.save_memmap_join(
        #     all_memmaps,
        #     base_name='FINAL',
        #     dview=self.dview
        # )
        # caiman was creating an extra memmap that was joined and that would cause weirdness, so 
        # for now we'll just memmap again.
        memmap = cm.save_memmap(
            self.tiffs,
            base_name='FINAL',
            order='C',
            slices=[
                slice(0, -1, self.channels * self.planes),
                slice(0, 512),
                slice(self.x_start, self.x_end)
            ]
        )
        
        Yr, dims, T = cm.load_memmap(memmap)
        images = np.reshape(Yr.T, [T] + list(dims), order='C')
        
        cnm_seeded = cnmf.CNMF(self.n_processes, params=self.opts, dview=self.dview, Ain=self.Ain)
        cnm_seeded.fit(images)
        cnm_seeded.save(self.save_h5df_folder + 'FINAL_caiman_data.hdf5')
        print('Caiman done!')
        
        
    def advance(self, by=1):
        """
        Advance the tiff file counts and whatever else needed by an interation count (for example
        the number of tiffs per batch).

        Args:
            by (int, optional): How much to advance fnumber by. Defaults to 1.
        """
        self.fnumber += by
    
    
    def send(self):
        pass