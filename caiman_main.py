import caiman as cm
from caiman.source_extraction.cnmf import cnmf as cnmf
from caiman.source_extraction.cnmf import params as params
from glob import glob
from ScanImageTiffReader import ScanImageTiffReader
import numpy as np
import os
import json

from utils import tic, toc, ptoc, remove_artifacts, mm3d_to_img 
from utils import cleanup_hdf5, cleanup_mmaps, cleanup_json

class OnlineAnalysis:
    def __init__(self, caiman_params, channels, planes, x_start, x_end, folder):
        self.channels = channels
        self.planes = planes
        self.x_start = x_start
        self.x_end = x_end
        self.folder = folder
        self.caiman_params = caiman_params
        self.trial_lengths = []
        
        # derived params
        self.folder_tiffs = folder + '*.tif*'
        self.save_h5df_folder = folder + 'out/'
        print('Setting up caiman...')
        self.opts = params.CNMFParams(params_dict=self.caiman_params)
        self.batch_size = 5 # can be overridden by expt runner
        self.fnumber = 0
        self.bad_tiff_size = 10
        self._splits = None
        self._json = None
        
        # other init things to do
        # start server
        self._start_cluster()
        # cleanup
        cleanup_mmaps(self.folder)
        cleanup_hdf5(self.save_h5df_folder)
        
        
    @property
    def tiffs(self):
        self._tiffs = glob(self.folder_tiffs)
        return self._tiffs
    
    def _start_cluster(self):
        if 'self.dview' in locals():
            cm.stop_server(dview=dview)
        print('Starting local cluster...', end = ' ')
        self.c, self.dview, self.n_processes = cm.cluster.setup_cluster(
            backend='local', n_processes=None, single_thread=False)
        print('done.')
    
    
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
        image = self.prep_mm3d_template(glob('E:/caiman_scratch/template/*.mat')[0])
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
        self.movie = np.reshape(Yr.T, [T] + list(dims), order='F')
        
        
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
        return cnm_seeded.estimates.C
        
        
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
        self.C = self.do_fit()
        self.trial_lengths.append(self.splits)
        self.save_json()
        self.advance(by=self.batch_size)
        
    @property
    def splits(self):
        these_maps = glob(f'{self.folder}MAP{self.fnumber}0*.mmap')
        self._splits = [m.split('_')[-2] for m in these_maps]
        return self._splits
        
        
    def do_final_fit(self):
        """
        Do the last fit on all the tiffs in the folder. This makes an entirely concenated cnmf fit.
        """
        t = tic()
        print(f'processing files: {self.tiffs}')
        self.opts.change_params(dict(fnames=self.tiffs))
        
        all_memmaps = glob(self.folder + 'MAP00*.mmap')
        memmap = cm.save_memmap_join(
            all_memmaps,
            base_name='FINAL',
            dview=self.dview
        )
        
        Yr, dims, T = cm.load_memmap(memmap)
        images = np.reshape(Yr.T, [T] + list(dims), order='F')
        
        cnm_seeded = cnmf.CNMF(self.n_processes, params=self.opts, dview=self.dview, Ain=self.Ain)
        cnm_seeded.fit(images)
        cnm_seeded.save(self.save_h5df_folder + 'FINAL_caiman_data.hdf5')
        
        self.C = cnm_seeded.estimates.C
        print(f'CNMF fitting done. Took {toc(t):.4f}s')
        print('Caiman online analysis done.')
        
        
    def advance(self, by=1):
        """
        Advance the tiff file counts and whatever else needed by an interation count (for example
        the number of tiffs per batch).

        Args:
            by (int, optional): How much to advance fnumber by. Defaults to 1.
        """
        self.fnumber += by
    
    
    def send_json(self):
        pass
    
    
    def save_json(self):
        with open(f'{self.save_h5df_folder}data_out_{self.fnumber}.json', 'w') as outfile:
            json.dump(self.json, outfile)
    
    @property
    def json(self):
        self._json = {
            'c': self.C.tolist(),
            'splits': self.splits
        }
        return self._json