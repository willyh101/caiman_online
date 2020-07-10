import caiman as cm
from caiman.source_extraction.cnmf import cnmf as cnmf
from caiman.source_extraction.cnmf import params as params
from caiman.source_extraction.cnmf import online_cnmf as online_cnmf
from glob import glob
from ScanImageTiffReader import ScanImageTiffReader
import numpy as np
import os
import json

from utils import tic, toc, ptoc, remove_artifacts, mm3d_to_img 
from utils import cleanup_hdf5, cleanup_mmaps, cleanup_json
from matlab import networking


class OnlineAnalysis:
    """
    The main class to implement caiman pseudo-online analysis.
    
    Requires a simple folder structure:
    
        folder (self.folder, speficied on __init__)
          |--template (location of template for seeding caiman, MUST be present already)
          |--out (where results get stored, auto-created if absent)
          
    
    """
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
        self.save_folder = folder + 'out/'
        print('Setting up caiman...')
        self.opts = params.CNMFParams(params_dict=self.caiman_params)
        self.batch_size = 30 # can be overridden by expt runner
        self.fnumber = 0
        self.bad_tiff_size = 10
        self._splits = None
        self._json = None
        
        # other init things to do
        # start server
        self._start_cluster()
        # cleanup
        cleanup_mmaps(self.folder)
        cleanup_hdf5(self.save_folder)
        cleanup_json(self.save_folder)
        
        self._everything_is_OK = True
        
    @property
    def everything_is_OK(self):
        return self._everything_is_OK
    
    @everything_is_OK.setter
    def everything_is_OK(self, status):
        if status == False:
            networking.wtf()
            
    @property
    def tiffs(self):
        self._tiffs = glob(self.folder_tiffs)
        return self._tiffs
    
    
    def _start_cluster(self):
        if 'self.dview' in locals():
            cm.stop_server(dview=self.dview)
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
            base_name=f'MAP{self.fnumber}a', 
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
        self.coords = cm.utils.visualization.get_contours(cnm_seeded.estimates.A, dims=cnm_seeded.dims)
        cnm_seeded.estimates.detrend_df_f()
        self.dff = cnm_seeded.estimates.F_dff
        cnm_seeded.save(self.save_folder + f'caiman_data_{self.fnumber:04}.hdf5')
        print(f'CNMF fitting done. Took {toc(t):.4f}s')
        return cnm_seeded.estimates.C
        
        
    def do_next_group(self):
        """
        Do the next iteration on a group of tiffs.
        """
        self.validate_tiffs()
        these_tiffs = self.tiffs[-self.batch_size:None]
        print(f'processing files: {these_tiffs}')
        self.opts.change_params(dict(fnames=these_tiffs))
        self.make_mmap(these_tiffs) # gets the last x number of tiffs
        self.make_movie()
        self.C = self.do_fit()
        self.trial_lengths.append(self.splits)
        self.save_json()
        self.advance(by=self.batch_size)
        
    @property
    def splits(self):
        these_maps = glob(f'{self.folder}MAP{self.fnumber}a0*.mmap')
        self._splits = [int(m.split('_')[-2]) for m in these_maps]
        return self._splits

        
    def do_final_fit(self):
        """
        Do the last fit on all the tiffs in the folder. This makes an entirely concenated cnmf fit.
        """
        t = tic()
        print(f'processing files: {self.tiffs}')
        self.opts.change_params(dict(fnames=self.tiffs))
        
        maplist = []
        for i in range(self.fnumber):
            m = glob(self.folder + f'MAP{i}a_*')[0]
            maplist.append(m)
            
        # all_memmaps = glob(self.folder + 'MAP00*.mmap')
        memmap = cm.save_memmap_join(
            maplist,
            base_name='FINAL',
            dview=self.dview
        )
        
        Yr, dims, T = cm.load_memmap(memmap)
        images = np.reshape(Yr.T, [T] + list(dims), order='F')
        
        cnm_seeded = cnmf.CNMF(self.n_processes, params=self.opts, dview=self.dview, Ain=self.Ain)
        cnm_seeded.fit(images)
        cnm_seeded.save(self.save_folder + 'FINAL_caiman_data.hdf5')
        
        self.coords = cm.utils.visualization.get_contours(cnm_seeded.estimates.A, dims=cnm_seeded.dims)
        cnm_seeded.estimates.detrend_df_f()
        self.dff = cnm_seeded.estimates.F_dff
        self.C = cnm_seeded.estimates.C
        
        self.save_json()
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
        with open(f'{self.save_folder}data_out_{self.fnumber:04}.json', 'w') as outfile:
            json.dump(self.json, outfile)
    
    @property
    def json(self):
        self._json = {
            'c': self.C.tolist(),
            'splits': self.splits,
            'dff': self.dff,
            'coords': self.coords
        }
        return self._json
    
    def _verify_folder_structure(self):
        # check to make sure the out folder is there
        try:
            if not os.path.exists(self.folder + 'out/'):
                os.mkdir(self.folder + 'out/')
        except OSError:
            print("can't make the save path for some reason :( ")
            
        # check to make sure there is a template folder
        try:
            os.path.exists(self.folder + 'template/')
        except:
            print(f'ERROR: No template folder found in {self.folder}')
            
            
class SimulateAcq(OnlineAnalysis):
    
    def __init__(self, *args, **kwargs):
        self.chunk_size = kwargs.pop('chunk_size')
        self.structural_image = kwargs.pop('structural_img')
        self.group_lenths = []
        self.segment()
        super().__init__(*args, **kwargs)
        
    @property
    def json(self):
        """
        Replaces the OnlineAnalysis.json to add group lengths time measurement.
        """
        
        self._json = {
            'c': self.C.tolist(),
            'splits': self.splits,
            'time': self.group_lenths,
            'dff': self.dff,
            'coords': self.coords
        }
        
        return self._json
        
    def make_tiff_groups(self):
        """
        Groups tiffs in a folder into list of list for running a fake acq.

        Args:
            chunk_size (int): number of files to do at once
        """
        all_tiffs = glob(self.folder_tiffs)
        chunked = [all_tiffs[i:i + self.chunk_size] for i in range(0, len(all_tiffs), self.chunk_size)]
        return chunked
    
    def do_next_group(self, tiffs_to_run):
        """
        Replaces the OnlineAnalysis.do_next_group() so we can fake experiments and test downstream
        analysis.
        """
        t = tic()
        self.validate_tiffs()
        self.opts.change_params(dict(fnames=tiffs_to_run))
        self.make_mmap(tiffs_to_run)
        self.make_movie()
        self.C = self.do_fit()
        self.trial_lengths.append(self.splits)
        self.group_lenths.append(toc(t))
        self.save_json()
        self.advance(by=1)
        
    def run_fake_expt(self):
        """
        Runs the loop over tiffs, chunked by tiff size.
        """
        tiff_list = self.make_tiff_groups()
        for tiff_group in tiff_list:
            self.do_next_group(tiff_group)
        self.do_final_fit()
        cm.stop_server(dview=self.dview)

            
# class NotSeeded(OnlineAnalysis):
#     def __init__(self, caiman_params, channels, planes, x_start, x_end, folder):
#         super().__init__(caiman_params, channels, planes, x_start, x_end, folder)
#         self.opts.change_params(self.unseeded_params())
#         self.Ain = None
        
#     def unseeded_params(self):
#         opts = {
#             'method_init': 'greedy_roi',
#             'rf': 60
#         }
#         return opts
        
# class DropAcid(OnlineAnalysis):
#     def __init__(self, *args, **kwargs):
#         super().__init__(*args, **kwargs)
#         self.Ain = None
#         self.opts.change_params(self.OnAcidParams())
        
#     def OnAcidParams(self):
#         opts = {
#             'init_method': 'bare',
#             'sniper_mode': True,
#             'init_batch': 50,
#             'expected_comps': 500,
#             'min_num_trial': 10,
#             'K': 2,
#             'epochs': 2
#         }
#         return opts
        
#     def do_fit(self):
#         """
#         Perform the OnAcid calculation.
#         """
#         t = tic()
#         print('Starting motion correction and CNMF...')
#         cnm_seeded = online_cnmf.OnACID(params=self.opts)
#         cnm_seeded.fit_online()
#         cnm_seeded.save(self.save_folder + f'caiman_data_{self.fnumber}.hdf5')
#         print(f'CNMF fitting done. Took {toc(t):.4f}s')
#         return cnm_seeded.estimates.C