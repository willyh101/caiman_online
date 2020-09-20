import logging
import os
import warnings
from pathlib import Path

import numpy as np
from ScanImageTiffReader import ScanImageTiffReader

with warnings.catch_warnings():
    warnings.simplefilter('ignore', category=FutureWarning)
    import caiman as cm
    from caiman.motion_correction import MotionCorrect
    from caiman.source_extraction.cnmf import CNMF
    from caiman.source_extraction.cnmf import params

from .utils import tiffs2array
from .wrappers import tictoc


__all__ = ['MCWorker', 'SeededCaimanWorker']

# TODO 
# set the current working directory as the temp folder

logging.basicConfig(level=logging.INFO)

class Worker:
    """Base class for workers that process data (usually by slicing out planes)."""
    
    def __init__(self, files, plane, nchannels, nplanes, opts_dict):
        self.files = files
        self.plane = plane
        self.nchannels = nchannels
        self.nplanes = nplanes
        self.opts_dict = opts_dict
        
        self.data_root = Path(self.files[0]).parent
        self.caiman_path = Path()
        self.out_path = Path()
        self.temp_path = Path()
        self._setup_folders()
        
        # these get set up by _start_cluster, called on run so workers can be queued w/o 
        # ipyparallel clusters clashing
        self.C = None
        self.dview = None
        self.n_processes = None
        
        # setup the params object
        logging.debug('Setting up params...')
        self.params = params.CNMFParams(params_dict=opts_dict)
        
    def __del__(self):
        try:
            cm.stop_server(dview=self.dview)
            logging.debug('Cluster stopped on delete.')
        except:
            logging.debug('No cluster to shutdown on delete.')
        logging.debug('Worker object destroyed on delete.')
        
    def _start_cluster(self, **kwargs):
        # get default values if not specified in kwargs
        kwargs.setdefault('backend', 'local')
        kwargs.setdefault('n_processes', os.cpu_count()-2) # make room for matlab
        kwargs.setdefault('single_thread', False)
        
        for key, value in kwargs.items():
            logging.debug(f'{key} set to {value}')
        
        logging.info('Starting local cluster.')
        try:
            self.c, self.dview, self.n_processes = cm.cluster.setup_cluster(**kwargs)
        except:
            logging.error("Local ipyparallel cluster already working. Can't create another.")
            raise
        logging.info('Local cluster ready.')
        
    def _setup_folders(self):
        self.out_path = self.data_root/'caiman'/str(self.plane)/'out'
        self.temp_path = self.data_root/'caiman'/str(self.plane)/'tmp'
        
        self.out_path.mkdir(parents=True, exist_ok=True)
        logging.debug(f'Created out_path at {self.out_path}')
            
        self.temp_path.mkdir(parents=True, exist_ok=True)
        logging.debug(f'Created out_path at {self.temp_path}')
    
    # TODO this
    def _cleanup(self):
        pass
             
 
class SeededCaimanWorker(Worker):
    """Subclass worker for running the seeded CNMF (batch) fit."""
    
    def __init__(self, mov, Ain, files, plane, nchannels, nplanes, opts):
        super().__init__(files, plane, nchannels, nplanes, opts)
        self.mov = mov
        self.Ain = Ain
        logging.info('Starting seeded batch CNMF.')
    
    @staticmethod
    def make_movie(mmap_file):
        Yr, dims, T = cm.load_memmap(mmap_file)
        images = np.reshape(Yr.T, [T] + list(dims), order='C')
        return images
    
    @tictoc    
    def do_fit(self):
        cnmf = CNMF(self.n_processes, params=self.params, dview=self.dview, Ain=self.Ain)
        images = self.make_movie(self.mov)
        cnmf.fit(images)
        cnmf.estimates.detrend_df_f()
    
    def run(self):
        self._start_cluster() # this will error if there is already a cluster running
        out = self.do_fit()
        cm.stop_server(dview=self.dview)
        return out


class MCWorker(Worker):
    def __init__(self, files, plane, nchannels, nplanes, opts):
        super().__init__(files, plane, nchannels, nplanes, opts)
        self.tslice = slice(plane*nchannels, -1, nchannels * nplanes)
        self.xslice = slice(0, 512)
        self.yslice = slice(0, 512)
        
        self.mc = None # placeholder for created MC object
        self._splits = None # indiv tiff lengths
        
    def _validate_tiffs(self, bad_tiff_size=5):
        """
        Finds the weird small tiffs and removes them. Arbitrarily set to <5 frame because it's not too
        small and not too big.

        Args:
            bad_tiff_size (int, optional): Size tiffs must be to not be trashed. Defaults to 5.
        """
        
        crap = []
        lengths = []
        for tiff in self.files:
            with ScanImageTiffReader(str(tiff)) as reader:
                data = reader.data()
                if data.shape[0] < bad_tiff_size:
                    crap.append(tiff)
        for crap_tiff in crap:
            os.remove(crap_tiff)
            
    
    # TODO fix how this works bc validate tiffs doesn't really do anything here (tiffs are not re-globbed)
    @tictoc        
    def load(self):
        """Make memory mapped files for each plane in a set of tiffs."""

        # make the tiffs into a concatenated array
        self._validate_tiffs()
        mov = tiffs2array(movie_list=self.files, 
                          x_slice=self.xslice, 
                          y_slice=self.yslice,
                          t_slice=self.tslice)
        return mov
    
    @tictoc        
    def motion_correct(self, mov):
        """
        Motion correct to a template independently of running CNMF.
        
        Args:
            mov (array-like): numpy array of loaded tiff
        """
        
        
        if not hasattr(self, 'gcamp_template'):
            # make a the first template
            logging.info('Starting motion correction without provided template...')
            
            self.mc = MotionCorrect(mov, dview=self.dview, **self.params.get_group('motion'))
            self.mc.motion_correct(save_movie=True)
            
            try:
                # elastic/PW
                self.gcamp_template = self.mc.total_template_els
                
            except AttributeError:
                # rigid motion correction (not PW) was done
                self.gcamp_template = self.mc.total_template_rig
                
        else:
            # use the first templatet to motion correct off of
            logging.info('Starting motion correction with provided template...')
            self.mc = MotionCorrect(mov, dview=self.dview, **self.params.get_group('motion'))
            self.mc.motion_correct(save_movie=True, template=self.gcamp_template)
    
    @tictoc
    def run(self):
        self._start_cluster() # this will error if there is already a cluster running
        mov = self.load()
        self.motion_correct(mov)
        cm.stop_server(dview=self.dview)
        return self.mc.mmap_file[0]