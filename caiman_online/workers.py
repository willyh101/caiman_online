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
    from caiman.source_extraction.cnmf.online_cnmf import OnACID
    from caiman.source_extraction.cnmf.params import CNMFParams

from .utils import tiffs2array
from .wrappers import tictoc

logger = logging.getLogger('caiman_online')

__all__ = ['MCWorker', 'CaimanWorker', 'OnAcidWorker']

class Worker:
    """Base class for workers that process data (usually by slicing out planes)."""
    
    def __init__(self, files, plane, nchannels, nplanes, params):
        """
        Base class for implementing caiman online. Don't call this class directly, rather call or
        make a subclass.

        Args:
            files (list): list of files to process
            plane (int): plane number to process, serves a slice through each tiff
            nchannels (int): total number of channels total, helps slicing ScanImage tiffs
            nplanes (int): total number of z-planes imaged, helps slicing ScanImage tiffs
            params (dict): caiman params dict
        """
        self.files = files
        self.plane = plane
        self.nchannels = nchannels
        self.nplanes = nplanes
        
        # setup the params object
        logger.debug('Setting up params...')
        self.params = CNMFParams(params_dict=params)
        
        self.data_root = Path(self.files[0]).parent
        self.caiman_path = Path()
        self.temp_path = Path()
        self.all_path = Path()
        self._setup_folders()
        
        # these get set up by _start_cluster, called on run so workers can be queued w/o 
        # ipyparallel clusters clashing
        self.c = None # little c is ipyparallel related
        self.dview = None
        self.n_processes = None
        
    def __del__(self):
        self._stop_cluster()
        logger.debug('Worker object destroyed on delete.')
        
    def _start_cluster(self, **kwargs):
        # get default values if not specified in kwargs
        kwargs.setdefault('backend', 'local')
        kwargs.setdefault('n_processes', os.cpu_count()-2) # make room for matlab
        kwargs.setdefault('single_thread', False)
        
        for key, value in kwargs.items():
            logger.debug(f'{key} set to {value}')
        
        logger.debug('Starting local cluster.')
        try:
            self.c, self.dview, self.n_processes = cm.cluster.setup_cluster(**kwargs)
        except:
            logger.error("Local ipyparallel cluster already working. Can't create another.")
            raise
        logger.debug('Local cluster ready.')
        
    def _stop_cluster(self):
        try:
            cm.stop_server(dview=self.dview)
            logger.debug('Cluster stopped.')
        except:
            logger.warning('No cluster to shutdown.')
                
    def _setup_folders(self):
        self.temp_path = self.data_root/'caiman'/'tmp'
        self.out_path = self.data_root/'caiman'/'out'
            
        self.temp_path.mkdir(parents=True, exist_ok=True)
        logger.debug(f'Set temp_path to {self.temp_path}')
        
        self.out_path.mkdir(parents=True, exist_ok=True)
        logger.debug(f'Set out_path to {self.out_path}')
        
        # set the CWD to the temp path
        os.chdir(self.temp_path)
        logger.info(f'Set working dir to {self.temp_path}')
    
    def cleanup_tmp(self, ext='*'):
        """
        Deletes all the files in the tmp folder.

        Args:
            ext (str, optional): Removes files with given extension. Defaults to '*' (all extensions).
        """
        
        files = self.temp_path.glob('*.' + ext)
        for f in files:
            try:
                # try to remove the file
                f.unlink()
            except:
                # warn if the file is still in use
                logger.error(f'Unable to remove file: {f}')


class MCWorker(Worker):
    """Implements caiman motion correction."""
    def __init__(self, files, plane, nchannels, nplanes, params):
        """
        Implents caiman motion correction.

        Args:
            files (list): list of tiffs to process
            plane (int): index of plane currrently being processed
            nchannels (int): total number of channels
            nplanes (int): total number of planes
            params (dict): dictionary of parameters, is turned into a caiman.Params object
        """
        super().__init__(files, plane, nchannels, nplanes, params)
        self.tslice = slice(plane*nchannels, -1, nchannels * nplanes)
        self.xslice = slice(0, 512)
        self.yslice = slice(0, 512)
        
        self.mc = None # placeholder for created MC object
        self.splits = None # indiv tiff lengths, gotten by _validate_tiffs() on load
        
    def _validate_tiffs(self, bad_tiff_size=5):
        """
        Finds the weird small tiffs and removes them. Arbitrarily set to <5 frame because it's not too
        small and not too big. Also gets the lengths of all good tiffs.

        Args:
            bad_tiff_size (int, optional): Size tiffs must be to not be trashed. Defaults to 5.
        """
        
        crap = []
        lengths = []
        
        for tiff in self.files:
            with ScanImageTiffReader(str(tiff)) as reader:
                data = reader.data()
                if data.shape[0] < bad_tiff_size:
                    # remove them from the list of tiffs
                    self.files.remove(tiff)
                    # add them to the bad tiff list for removal from HD
                    crap.append(tiff)
                else:
                    # otherwise we append the length of tiff to the lengths list
                    lengths.append(data.shape[0])             
        for crap_tiff in crap:
            os.remove(crap_tiff)
            
        self.splits = (np.array(lengths) / (self.nchannels * self.nplanes)).astype(np.int)
            
            
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
        
        # check to see if a motion template is provided and if not make one
        if not hasattr(self, 'gcamp_template'):
            # make a the first template
            logger.info('Starting motion correction without provided template...')
            
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
            logger.info('Starting motion correction with provided template...')
            self.mc = MotionCorrect(mov, dview=self.dview, **self.params.get_group('motion'))
            self.mc.motion_correct(save_movie=True, template=self.gcamp_template)
    
    @tictoc
    def run(self):
        self._start_cluster() # this will error if there is already a cluster running
        mov = self.load()
        self.motion_correct(mov)
        cm.stop_server(dview=self.dview)
        return self.mc.mmap_file[0]
    
class CaimanWorker(Worker):
    """Subclass worker for running the seeded CNMF (batch) fit."""
    
    def __init__(self, mov, Ain, files, plane, nchannels, nplanes, params):
        super().__init__(files, plane, nchannels, nplanes, params)
        self.mov = mov
        self.Ain = Ain
        logger.info('Starting seeded batch CNMF.')
    
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
        # cnmf.estimates.detrend_df_f()
        return cnmf
    
    def run(self):
        self._start_cluster()
        out = self.do_fit()
        cm.stop_server(dview=self.dview)
        return out
    

class OnAcidWorker(CaimanWorker):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        logging.info('Started seeded OnACID.')
    
    @tictoc
    def do_fit(self):
        onacid = OnACID(params=self.params, dview=self.dview)
        return onacid
    
    def run(self):
        self._start_cluster()
        out = self.do_fit()
        cm.stop_server(dview=self.dview)
        return out
        