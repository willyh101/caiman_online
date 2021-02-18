import logging
import os
import warnings
import json
from pathlib import Path
from datetime import datetime

import numpy as np
from ScanImageTiffReader import ScanImageTiffReader
import tifffile

with warnings.catch_warnings():
    warnings.simplefilter('ignore', category=FutureWarning)
    import caiman as cm
    from caiman.motion_correction import MotionCorrect
    from caiman.source_extraction.cnmf import CNMF
    from caiman.source_extraction.cnmf.online_cnmf import OnACID
    from caiman.source_extraction.cnmf.params import CNMFParams

from .utils import make_ain, tic, toc, tiffs2array
from .wrappers import tictoc
from .analysis import find_com

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
        self._params = CNMFParams(params_dict=params)
        
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
        
    @property
    def params(self):
        return self._params
    
    @params.setter
    def params(self, params):
        if isinstance(params, dict):
            self._params = CNMFParams(params_dict=params)
        elif isinstance(params, CNMFParams):
            self._params = params
        else:
            raise ValueError('Please supply a dict or cnmf params object.')
        
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
        logger.debug(f'Set working dir to {self.temp_path}')
        
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
            
            if hasattr(self.mc, 'total_template_els'):
                self.gcamp_template = self.mc.total_template_els
            else:
                self.gcamp_template = self.mc.total_template_rig
            # try:
            #     # elastic/PW
            #     self.gcamp_template = self.mc.total_template_els
                
            # except AttributeError:
            #     # rigid motion correction (not PW) was done
            #     self.gcamp_template = self.mc.total_template_rig
                
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
        cnmf.estimates.detrend_df_f()
        return cnmf
    
    def run(self):
        self._start_cluster()
        out = self.do_fit()
        cm.stop_server(dview=self.dview)
        return out
    

class OnAcidWorker(Worker):
    def __init__(self, files, Ain, plane, nchannels, nplanes, params):
        super().__init__(files, plane, nchannels, nplanes, params)
        self.tslice = slice(plane*nchannels, -1, nchannels * nplanes)
        self.xslice = slice(0, 512)
        self.yslice = slice(0, 512)
        self.Ain = Ain
        self.splits = None
        logger.info('Started seeded OnACID.')
        
    @tictoc
    def make_tiff(self, save_path='./onlinemovie.tif'):
        self._validate_tiffs()
        mov = tiffs2array(movie_list=self.files, 
                          x_slice=self.xslice, 
                          y_slice=self.yslice,
                          t_slice=self.tslice)
        save_path = f'./onlinemovie_plane_{self.plane}.tif'
        tifffile.imsave(save_path, mov)
        self.mov_path = Path(save_path).absolute()
        return [str(self.mov_path)]
    
    @tictoc
    def do_fit(self, movie_path):
        onacid = OnACID(params=self.params, dview=self.dview)
        onacid.params.change_params(dict(fnames=movie_path))
        onacid.estimates.A = self.Ain
        onacid.fit_online()
        onacid.estimates.detrend_df_f()
        return onacid
    
    def run(self):
        # self._start_cluster()
        movie_path = self.make_tiff()
        out = self.do_fit(movie_path)
        # cm.stop_server(dview=self.dview)
        return out


class RealTimeWorker(Worker):
    def __init__(self, files, plane, nchannels, nplanes, params, q, 
                 num_frames_max=10000, Ain_path=None, use_prev_init=True, **kwargs):

        super().__init__(files, plane, nchannels, nplanes, params)

        self.q = q
        self.num_frames_max = num_frames_max
        
        if isinstance(Ain_path, str):
            self.Ain = make_ain(Ain_path, plane, self.xslice.start, self.xslice.stop)
        else:
            self.Ain = None
        
        # set slicing
        self.tslice = kwargs.get('tslice', slice(plane*nchannels, -1, nchannels * nplanes))
        self.xslice = kwargs.get('xslice', slice(0, 512))
        self.yslice = kwargs.get('yslice', slice(0, 512))
        
        # other options
        self.use_CNN = False
        self.update_freq = 500
        self.use_prev_init = use_prev_init
        
        # setup initial parameters
        self.t = 0 # current frame is on
        
        # placeholders
        self.acid = None
        
        # extra pathing for realtime
        # add folder to hold inits
        self.init_fname = f'realtime_init_plane_{self.plane}.hdf5'
        self.init_dir = self.data_root.parent/'live2p_init'
        self.init_path = self.init_dir/self.init_fname
        
        logger.info('Starting OnACID (real-time) worker.')
        
        # run OnACID initialization if needed
        if self.init_dir.exists() and self.use_prev_init:
            self.init_dir.mkdir(exist_ok=True)
            self.acid = self.initialize_from_file()
        else:
            logger.info(f'Starting new OnACID initialization.')
            init_mmap = self.make_init_mmap()
            self.acid = self.initialize(init_mmap)   
        
    def make_init_mmap(self, save_path='init.mmap'):
        logger.debug('Making init memmap...')
        self._validate_tiffs()
        mov = tiffs2array(movie_list=self.files, 
                          x_slice=self.xslice, 
                          y_slice=self.yslice,
                          t_slice=self.tslice)
        
        self.frame_start = mov.shape[0] + 1
        self.t = mov.shape[0] + 1
        
        self.params.change_params(dict(init_batch=mov.shape[0]))
        m = cm.movie(mov.astype('float32'))
        
        save_path = f'initplane{self.plane}.mmap'
        init_mmap = m.save(save_path, order='C')
        
        logger.debug(f'Init mmap saved to {init_mmap}.')
        
        return init_mmap
    
    @tictoc
    def initialize(self, fname_init):
        """
        Initialize OnACID from a tiff to generate initial model. Saves CNMF/OnACID object
        into ../live2p_init. Runs the initialization specified in params ('bare', 'seeded', etc.).

        Args:
            fname_init (Path-like): Path or str to tiff to initalize from

        Returns:
            initialized OnACID object
        """
        
        # change params to use new mmap as init file
        self.params.change_params(dict(fnames=str(fname_init)))

        # setup caiman object
        acid = OnACID(dview=None, params=self.params)
        acid.estimates.A = self.Ain
        
        # do initialization
        acid.initialize_online(T=self.num_frames_max)
        
        # save for next time to init path
        self.save_acid(fname=self.init_path)
        
        logger.debug('OnACID initialized.')
        
        return acid
    
    @tictoc
    def initialize_from_file(self):
        """
        Initialize OnACID from a previous initialization or full OnACID session (not yet
        implemented).

        Returns:
            initialized OnACID object
        """
        
        logger.info(f'Loading previous OnACID initialization from {self.init_path}.')
        
        # load
        acid = self.load_acid(self.init_path)
        
        # set frame counters
        init_batch = acid.params.online['init_batch']
        self.frame_start = init_batch + 1
        self.t = init_batch + 1
        
        return acid
    
    def process_frame_from_queue(self):
        """
        The main loop. Pulls data from the queue and processes it, fitting data to the model. Stops
        upon recieving a 'stop' string.

        Returns:
            json representation of the OnACID model
        """
        
        while True:
            frame = self.q.get()
            
            if isinstance(frame, np.ndarray):
                frame_time = []
                t = tic()
                
                frame_ = frame[self.yslice, self.xslice].copy().astype(np.float32)
                frame_cor = self.acid.mc_next(self.t, frame_)
                self.acid.fit_next(self.t, frame_cor.ravel(order='F'))
                self.t += 1
                
                frame_time.append(toc(t))
                
                if self.t % 500 == 0:
                    logger.info(f'Total of {self.t} frames processed. (Queue {self.plane})')
                    # calculate average time to process
                    mean_time = np.mean(frame_time) * 1000 # in ms
                    mean_hz = round(1/np.mean(frame_time),2)
                    logger.info(f'Average processing time: {int(mean_time)} ms. ({mean_hz} Hz) (Queue {self.plane})')
                
            elif isinstance(frame, str):
                if frame == 'stop':                 
                    logger.info('Stopping realtime caiman....')
                    now = datetime.now()
                    current_time = now.strftime("%H:%M:%S")
                    logger.debug(f'Processing done at: {current_time}')
                    logger.info('Getting final results...')

                    self.update_acid()
                    
                    # save
                    try:
                        self.save_acid()
                    except:
                        # need to catch exception here because we want to complete the future and
                        # process the final data
                        logger.exception('Dumb error with saving OnACID hdf5. Might have still worked?')
                        
                    self.save_json()
                    data = self._model2dict()
                    
                    break
                
                else:
                    continue
                
        return data
                
    def update_acid(self):
        (self.acid.estimates.A, 
        self.acid.estimates.b, 
        self.acid.estimates.C,
        self.acid.estimates.f,
        self.acid.estimates.nC,
        self.acid.estimates.YrA
        ) = self.get_model()

    def get_model(self):

        # A = spatial component (cells)
        A = self.acid.estimates.Ab[:, self.acid.params.get('init', 'nb'):].toarray()
        # b = background components (neuropil)
        b = self.acid.estimates.Ab[:, :self.acid.params.get('init', 'nb')].toarray()
        # C = denoised trace for cells
        C = self.acid.estimates.C_on[self.acid.params.get('init', 'nb'):self.acid.M, self.frame_start:self.t]
        # f = denoised neuropil signal
        f = self.acid.estimates.C_on[:self.acid.params.get('init', 'nb'), self.frame_start:self.t]
        # nC a.k.a noisyC is ??
        nC = self.acid.estimates.noisyC[self.acid.params.get('init', 'nb'):self.acid.M, self.frame_start:self.t]
        # YrA = signal noise, important for dff calculation
        YrA = nC - C
        
        return A, b, C, f, nC, YrA
    
    def _model2dict(self):
        A, b, C, f, nC, YrA = self.get_model()
        coords = find_com(A, self.acid.estimates.dims, self.xslice.start)
        data = {
            'plane': int(self.plane),
            't': self.t,
            'A':A.tolist(),
            'b':b.tolist(),
            'C':C.tolist(),
            'f':f.tolist(),
            'nC':nC.tolist(),
            'YrA':YrA.tolist(),
            'CoM':coords.tolist()
        }
        return data
 
    def save_json(self, fname='realtime'):
        data = self._model2dict()
        fname += f'_plane_{self.plane}.json'
        save_path = self.out_path/fname
        with open(save_path, 'w') as f:
            json.dump(data, f)
        logger.info(f'Saved JSON to {str(save_path)}')
        
    def save_acid(self, fname=None):
        if fname is None:
            fname = f'realtime_results_plane_{self.plane}.hdf5'
        save_path = str(self.out_path/fname)                 
        self.acid.save(save_path)
        logger.info(f'Saved OnACID hdf5 to {save_path}')
        
    def load_acid(self, filepath):
        logger.info('Loading existing OnACID object file.')
        return cm.source_extraction.cnmf.online_cnmf.load_OnlineCNMF(filepath)