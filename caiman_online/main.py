import json
import os
from glob import glob

import caiman as cm
import matplotlib.pyplot as plt
import numpy as np
from caiman.source_extraction.cnmf import cnmf as cnmf
from caiman.source_extraction.cnmf import params as params
from ScanImageTiffReader import ScanImageTiffReader

from .analysis import extract_cell_locs
from .matlab import networking
from .utils import cleanup, make_ain, ptoc, tic, toc


class OnlineAnalysis:
    """
    The main class to implement caiman pseudo-online analysis.
    """
    def __init__(self, caiman_params, channels, planes, x_start, x_end, folder, batch_size=15):
        self.channels = channels
        self.planes = planes
        self.x_start = x_start
        self.x_end = x_end
        self.folder = folder
        self.caiman_params = caiman_params
        
        # derived params
        self.folder_tiffs = folder + '*.tif*'
        self.save_folder = folder + 'out/'

        print('Setting up caiman...')
        self.opts = params.CNMFParams(params_dict=self.caiman_params)
        self.batch_size = batch_size # can be overridden by expt runner
        self.fnumber = 0
        
        self._splits = None
        self._json = None
        self.times = []
        self.cond = []
        self.vis_cond = []
        
        # other init things to do
        # start server
        self._start_cluster()
        # cleanup
        cleanup(self.folder, 'mmap')
        cleanup(self.save_folder, 'hdf5')
        cleanup(self.save_folder, 'json')
        cleanup(os.getcwd(), 'npz')
    
    
    ##----- properties, setters, getters ----##
    
    @property
    def folder(self):
        return self._folder

    @folder.setter
    def folder(self, folder):
        self._folder = folder
        self.folder_tiffs = folder + '*.tif*'
        self.save_folder = folder + 'out/'
        self._verify_folder_structure()
            
    @property
    def tiffs(self):
        self._tiffs = glob(self.folder_tiffs)[:-1]
        if len(self._tiffs) == 0:
            networking.wtf()
            raise FileNotFoundError(
                f'No tiffs found in {self.folder_tiffs}. Check SI directory.'
            )
        return self._tiffs
    
    @property
    def json(self):
        self._json = {
            'c': self.C.tolist(),
            'splits': self.splits,
            'dff': self.dff.tolist(),
            'coords': self.coords.to_json(),
            'times': self.times,
            'cond': self.cond,
            'vis_cond': self.vis_cond
        }
        return self._json
    
    
    @property
    def splits(self):
        """This gets the frames numbers for each trial by reading the file name of the mmap."""
        # get all memmap files
        these_maps = glob(f'{self.folder}MAP{self.fnumber}_plane{self.plane}_a0*.mmap')
        # number of frames is the 2nd from the last thing in the file name
        self._splits = [int(m.split('_')[-2]) for m in these_maps]
        return self._splits
    
    
    def _start_cluster(self):
        if 'self.dview' in locals():
            cm.stop_server(dview=self.dview)
        print('Starting local cluster...', end = ' ')
        self.c, self.dview, self.n_processes = cm.cluster.setup_cluster(
            backend='local', n_processes=None, single_thread=False)
        self.dview = None
        print('done.')

       
    ###------internal use methods-------###     
      
    def _extract_rois_caiman(self, image):
        return cm.base.rois.extract_binary_masks_from_structural_channel(image, 
                                                                    min_area_size = 20, 
                                                                    min_hole_size = 10, 
                                                                    gSig = 5, 
                                                                    expand_method='dilation')[0]
    
    def _verify_folder_structure(self):
        # check to make sure the out folder is there
        try:
            if not os.path.exists(self.folder + 'out/'):
                os.mkdir(self.folder + 'out/')
        except OSError:
            print("can't make the save path for some reason :( ")
       
    
    ###-----general methods-----####
    
    def segment(self):
        if self.structural_image is None:
            raise ValueError('No structural image provided!')
        
        t = tic()
        print('Starting segmentation on a provided template...')
        self._extract_rois_caiman(self.structural_image)
        ptoc(t, start_string='done in')
        
        
    def make_mmap(self, files):
        """Make memory mapped files for each plane in a set of tiffs."""
        t = tic()
        memmap = []
        for plane in range(self.planes):
            print(f'Memory mapping current file, plane {plane}...')
            plane_slice = plane * self.channels
            memmap.append(cm.save_memmap(
                files,
                base_name=f'MAP{self.fnumber}_plane{plane}_a', 
                order='C',
                slices=[
                    slice(plane_slice, -1, self.channels * self.planes),
                    slice(0, 512),
                    slice(self.x_start, self.x_end)
                ]
            ))
        print(f'Memory mapping done. Took {toc(t):.4f}s')
        return memmap
        
        
    def make_movie(self, memmap):
        """
        Load memmaps and make the movie.
        """
        Yr, dims, T = cm.load_memmap(memmap)
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
                if data.shape[0] < bad_tiff_size:
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
        self.coords = extract_cell_locs(cnm_seeded)
        cnm_seeded.estimates.detrend_df_f()
        self.dff = cnm_seeded.estimates.F_dff
        cnm_seeded.save(self.save_folder + f'caiman_data_plane_{self.plane}_{self.fnumber:04}.hdf5')
        print(f'CNMF fitting done. Took {toc(t):.4f}s')
        return cnm_seeded.estimates.C
    
    
    def make_templates(self, path):
        """
        Manually make Ain from makeMasks3D output. This aids in getting the cells in the right
        order for caiman (ie. brightest first, not by position).
        """
        t = tic()
        print('Using makeMasks3D sources as seeded input.')
        self.templates = [make_ain(path, plane, self.x_start, self.x_end) for plane in range(self.planes)]
        ptoc(t)
        
        
    def do_next_group(self):
        """
        Do the next iteration on a group of tiffs.
        """
        self.validate_tiffs()
        these_tiffs = self.tiffs[-self.batch_size:None]
        print(f'processing files: {these_tiffs}')
        self.opts.change_params(dict(fnames=these_tiffs))
        memmaps = self.make_mmap(these_tiffs) # gets the last x number of tiffs
        self.data_this_round = []
        for plane,memmap in enumerate(memmaps):
            print(f'PLANE {plane}')
            t = tic()

            # do the fit
            self.plane = plane
            self.Ain = self.templates[plane]
            self.make_movie(memmap)
            self.C = self.do_fit()

            # use the json prop to save data
            self.data_this_round.append(self.json)
            self.save_json()

            ptoc(t, start_string=f'Plane {plane} done in')

        self.advance(by=self.batch_size)
        
        
    def do_final_fit(self):
        """
        Same thing as do_next_group() but catches all the tiffs. No [:-1] to
        avoid grabbing the current SI tiff.
        """
        
        all_tiffs = glob(self.folder_tiffs)
        self.validate_tiffs()
        these_tiffs = all_tiffs[-self.batch_size:None]
        print(f'processing files: {these_tiffs}')
        self.opts.change_params(dict(fnames=these_tiffs))
        self.make_mmap(these_tiffs) # gets the last X number of tiffs
        self.make_movie()
        self.C = self.do_fit()
        self.trial_lengths.append(self.splits)
        self.save_json()
        self.advance(by=self.batch_size)
        print('Caiman online analysis done.')
        
        
    def advance(self, by=1):
        """
        Advance the tiff file counts and whatever else needed by an interation count (for example
        the number of tiffs per batch).

        Args:
            by (int, optional): How much to advance fnumber by. Defaults to 1.
        """
        self.fnumber += by
    
    def save_json(self):
        with open(f'{self.save_folder}data_out_plane{self.plane}_{self.fnumber:04}.json', 'w') as outfile:
            json.dump(self.json, outfile)
            
            
            
class SimulateAcq(OnlineAnalysis):
    
    """Class for testing/simulating running caiman."""
    
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
            'dff': self.dff.tolist(),
            'coords': self.coords.to_json()
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
        
        
