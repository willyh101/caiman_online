import json
import logging
import pandas as pd
from caiman_online.analysis import extract_cell_locs
import os
from ScanImageTiffReader import ScanImageTiffReader
import numpy as np
from pathlib import Path
from .workers import CaimanWorker, MCWorker, OnAcidWorker
from . import networking
from .utils import format_json, make_ain, ptoc, tic
from datetime import datetime

logger = logging.getLogger('caiman_online')


def run_seeded_pipeline(files, params, nchannels, nplanes, plane=0, 
                        xslice=slice(112, 400), Ain=None, motion_template=None):
    """
    Run seeded caiman batch with motion correction. This implements the classes before and returns
    instances of each. Use this as a general guide for making altered pipelines.
    
    1. Motion correction via the general MCWorker class (defined above).
    2. Caiman CNMF via the general batch CNMF worker class (defined above).
    3. Return traces (generally, at least C and splits)

    Args:
        files (list): list of tiffs to process
        params (caiman.Params): caiman params object (not dictionary)
        nchannels (int): total number of channels in tiff per plane
        nplanes (int): total number of planes per volume
        plane (int, optional): Current plane being proccessed. Defaults to 0.
        xslice (slice, optional): Slice to cut the tiff in x to remove artifacts. Defaults to slice(112, 400).
        Ain (array-like, optional): Template to seed CNMF off of. Defaults to None.
        motion_template (array-like, optional): Template to motion correct off of. Defaults to None.

    Returns:
        C (deconvolved dff)
    """
    motion_worker = MCWorker(files, plane, nchannels, nplanes, params)
    motion_worker.xslice = xslice
    motion_worker.gcamp_template = motion_template
    mapfile = motion_worker.run()
    
    caiman_worker = CaimanWorker(mapfile, Ain, files, plane, nchannels, nplanes, params)
    caiman_data = caiman_worker.run()
    
    return caiman_data.estimates.C

def run_seeded_onacid(files, params, nchannels, nplanes, plane=0, 
                        xslice=slice(112, 400), Ain=None):
    """
    Run seeded caiman OnACID (aka online) with motion correction. This implements the relevant 
    worker classes and instances of each. Note OnACID motion corrects itself, so no manual MC needed.
    However, due to this you can't supply a motion template.

    Args:
        files (list): list of tiffs to process
        params (caiman.Params): caiman params object (not dictionary)
        nchannels (int): total number of channels in tiff per plane
        nplanes (int): total number of planes per volume
        plane (int, optional): Current plane being proccessed. Defaults to 0.
        xslice (slice, optional): Slice to cut the tiff in x to remove artifacts. Defaults to slice(112, 400).
        Ain (array-like, optional): Template to seed CNMF off of. Defaults to None.

    Returns:
        C (deconvolved dff)
    """
    acid_worker = OnAcidWorker(files, Ain, plane, nchannels, nplanes, params)
    acid_worker.xslice = xslice
    acid_data = acid_worker.run()
    return acid_data.estimates.C

class SeededPipeline:
    """
    Implentation of seeded caiman-batch with motion correction. Works as seeded, though leaving out Ain should
    default the pipeline to non-seeded.
    """
    def __init__(self, folder, params, nchannels, nplanes, x_start=0, x_end=512, 
                 y_start=0, y_end=512, Ain=None, batch_size_tiffs=30):
        
        self.folder = Path(folder)
        self.params = params
        self.nchannels = nchannels
        self.nplanes = nplanes
        self.x_start = x_start
        self.x_end = x_end
        self.y_start = y_start
        self.y_end = y_end
        self.Ain = Ain
        self.batch_size_tiffs = batch_size_tiffs
        
        self._xslice = None
        self._yslice = None
        self._tslice = None
        
        self.motion_template = []
        self.iters = 0
        
        # outputs
        self.traces = []
        self.dff = []
        self.splits = []
        self.coords = []
        self.data = None
        
    @property
    def xslice(self):
        self._xslice = slice(self.x_start, self.x_end)
        return self._xslice
    
    @property
    def yslice(self):
        self._yslice = slice(self.y_start, self.y_end)
        return self._yslice
    
    @property
    def tslice(self):
        self._tslice = self.nchannels * self.nplanes
        return self._tslice
        
    def fit_batch(self):
        
        tiffs_this_round, splits_temp = self.get_tiffs()
                    
        traces_temp = []
        coords_temp = []
        
        for plane in range(self.nplanes):
            print(f'***** Starting Plane {plane} motion correction and CNMF... *****')
            print('Starting motion correction...')
            t = tic()
            
            # MOTION CORRECTION
            motion_worker = MCWorker(tiffs_this_round, plane, self.nchannels, self.nplanes, self.params)
            motion_worker.xslice = self.xslice
            motion_worker.yslice = self.yslice
            
            if self.iters == 0:
                # no template, so get one
                mapfile = motion_worker.run()
                self.motion_template.append(motion_worker.gcamp_template) 
            else:
                # use the template to correct of off
                motion_worker.gcamp_template = self.motion_template[plane]
                mapfile = motion_worker.run()
                
            ptoc(t, start_string='Motion correction done.')
            
            print('Starting CNMF processing...')
            ct = tic()
            # CNMF PROCESSING
            this_ain = self.Ain[plane]
            caiman_worker = CaimanWorker(mapfile, this_ain, tiffs_this_round, plane, 
                                         self.nchannels, self.nplanes, self.params)
            caiman_data = caiman_worker.run()
            
            # PLANE-WISE RAW DATA SAVING
            # this is the data for a single plane
            c = caiman_data.estimates.C
            locs = extract_cell_locs(caiman_data)
            
            # saving the caiman data happens for every plane
            caiman_data.save(str(motion_worker.out_path/f'caiman_data_plane_{plane}_batch_{self.iters:04}.hdf5'))
            
            ptoc(ct, start_string='Caiman processing done.')
            
            # also save a single plane json
            plane_data = {
                'c': c,
                'splits': splits_temp,
                'coords': locs
            }
            self.save_plane_json(plane=plane, save_path=motion_worker.out_path, **plane_data)
            
            # append to the temp to collect multiplane data
            traces_temp.append(c)
            coords_temp.append(locs)
            
            caiman_worker.cleanup_tmp(ext='*')
            ptoc(t, start_string=f'***** Plane {plane} done.', end_string='s *****')
        
        # ALL PLANES DATA SAVING    
        # NOTE: splits is already a single vector since it's the same for all planes, so no concatenation needed
        traces_temp = np.concatenate(traces_temp, axis=0)
        coords_temp = pd.concat(coords_temp, ignore_index=True)
        
        # add to the main lists that accumulate over batches
        self.traces.append(traces_temp)
        self.splits.extend(splits_temp)
        self.coords.append(coords_temp.to_json())
        
        # concatenate again so the array grows in time
        # NOTE: this will error if the same number of cells aren't present, so for now we are catching that
        try:
            traces_concat = np.concatenate(self.traces, axis=1)

            all_data = {
                'c': traces_concat.tolist(),
                'splits': self.splits,
                'coords': self.coords
            }
            
            self.save_all_json(save_path=motion_worker.out_path, **all_data)
            
            self.data = {
                'c': traces_concat,
                'splits': self.splits
            }
            logger.debug('Successfully saved all_data to file.')
            
        except ValueError:
            logger.critical('Did not save concatentaed traces due to dimension mismatch.')
            logger.critical("This means a cell was lost in between batches and caiman_online can't complete :(") 
            # ? should I raise an error here???
            raise
            
        self.advance()
        
        
    def advance(self):
        self.iters += 1
        
    def get_tiffs(self):
        all_tiffs = list(self.folder.glob('*.tif*'))[:-1]
        # NOTE: skips the last one because it is in use by scanimage
        # throw and error if there are no tiffs in the directory
        
        if len(all_tiffs) < 1:
            try:
                networking.wtf()
            except:
                pass
            raise FileNotFoundError(
                f'No tiffs found in {self.folder}. Check SI directory.'
            )
            
        tiffs = all_tiffs[-self.batch_size_tiffs:None]
        splits = self.validate_tiffs(tiffs)
        
        if len(splits) < len(tiffs):
            # if validate tiffs deleted a weird short tiff then we need to remake the current tiff list
            tiffs = all_tiffs[-self.batch_size:None]
            
        return tiffs, splits
        
    def save_plane_json(self, plane, save_path, **kwargs):
        data_out = format_json(**kwargs)
        d = datetime.now()
        d_str = d.strftime('%Y%m%d_%H%M%S')
        fname = f'data_out_plane_{plane}_{self.iters:04}_{d_str}.json'
        path = save_path/fname
        with open(path, 'w') as outfile:
            json.dump(data_out, outfile)
            
    def save_all_json(self, save_path, **kwargs):
        data_out = format_json(**kwargs)
        d = datetime.now()
        d_str = d.strftime('%Y%m%d_%H%M%S')
        fname = f'data_out_plane_all_update_{self.iters:04}_{d_str}.json'
        path = save_path/fname
        with open(path, 'w') as outfile:
            json.dump(data_out, outfile)
            
    def validate_tiffs(self, files, bad_tiff_size=5):
        """
        Finds the weird small tiffs and removes them. Arbitrarily set to <5 frame because it's not too
        small and not too big. Also gets the lengths of all good tiffs.

        Args:
            bad_tiff_size (int, optional): Size tiffs must be to not be trashed. Defaults to 5.
            
        Returns the frame lengths for a single plane and single channels (aka total frames / nchannels * nplanes)
        """
        
        crap = []
        lengths = []
        
        for tiff in files:
            with ScanImageTiffReader(str(tiff)) as reader:
                data = reader.data()
                if data.shape[0] < bad_tiff_size:
                    # remove them from the list of tiffs
                    files.remove(tiff)
                    # add them to the bad tiff list for removal from HD
                    crap.append(tiff)
                else:
                    # otherwise we append the length of tiff to the lengths list
                    lengths.append(data.shape[0])
        for crap_tiff in crap:
            os.remove(crap_tiff)
            
        return (np.array(lengths) / (self.nchannels * self.nplanes)).tolist()
    
    def make_templates(self, path):
        """
        Manually make Ain from makeMasks3D output. This aids in getting the cells in the right
        order for caiman (ie. brightest first, not by position).
        """
        t = tic()
        print('Using makeMasks3D sources as seeded input.')
        self.Ain = [make_ain(path, plane, self.x_start, self.x_end) for plane in range(self.nplanes)]
        ptoc(t)
        

class OnAcidPipeline(SeededPipeline):
    """
    Implements the specific case of OnACID seeded, but not in real-time. Just runs OnACID on
    batches of provided tiffs.
    """
        
    def fit_batch(self):
        
        tiffs_this_round, splits_temp = self.get_tiffs()
                    
        traces_temp = []
        coords_temp = []
        dff_temp = []
        
        for plane in range(self.nplanes):
            print(f'***** Starting Plane {plane} OnACID... *****')
            print('Starting OnACID processing...')
            ct = tic()
            # CNMF PROCESSING
            logger.debug('Starting OnACID worker.')
            this_ain = self.Ain[plane]
            acid_worker = OnAcidWorker(tiffs_this_round, this_ain, plane, 
                                         self.nchannels, self.nplanes, self.params)
            
            acid_worker.xslice = self.xslice
            acid_worker.yslice = self.yslice
            
            caiman_data = acid_worker.run()
            
            # PLANE-WISE RAW DATA SAVING
            # this is the data for a single plane
            logger.debug('Saving data.')
            c = caiman_data.estimates.C
            dff = caiman_data.estimates.F_dff
            locs = extract_cell_locs(caiman_data)
            
            # saving the caiman data happens for every plane
            # ! saving here isn't working for some reason, temporarily commenting out.
            # ! appears to only be not saving sometimes? removing to see if there is a
            # ! problem that is being masked by saving
            # caiman_data.save(str(acid_worker.out_path/f'caiman_data_plane_{plane}_batch_{self.iters:04}.hdf5'))
                        
            # also save a single plane json
            plane_data = {
                'c': c,
                'dff': dff,
                'splits': splits_temp,
                'coords': locs
            }
            self.save_plane_json(plane=plane, save_path=acid_worker.out_path, **plane_data)
            
            # append to the temp to collect multiplane data
            traces_temp.append(c)
            dff_temp.append(dff)
            coords_temp.append(locs)
            
            acid_worker.cleanup_tmp(ext='*')
            ptoc(ct, start_string=f'***** Plane {plane} done.', end_string='s *****')
        
        # ALL PLANES DATA SAVING    
        # NOTE: splits is already a single vector since it's the same for all planes, so no concatenation needed
        traces_temp = np.concatenate(traces_temp, axis=0)
        dff_temp = np.concatenate(dff_temp, axis=0)
        coords_temp = pd.concat(coords_temp, ignore_index=True)
        
        # add to the main lists that accumulate over batches
        self.traces.append(traces_temp)
        self.dff.append(dff_temp)
        self.splits.extend(splits_temp)
        self.coords.append(coords_temp.to_json())
        
        # concatenate again so the array grows in time
        # NOTE: this will error if the same number of cells aren't present, so for now we are catching that
        try:
            traces_concat = np.concatenate(self.traces, axis=1)
            dff_concat = np.concatenate(self.dff, axis=1)

            all_data = {
                'c': traces_concat.tolist(),
                'dff': dff_concat.tolist(),
                'splits': self.splits,
                'coords': self.coords
            }
            self.save_all_json(save_path=acid_worker.out_path, **all_data)
            
            self.data = {
                'c': traces_concat,
                'dff': dff_concat,
                'splits': self.splits
            }
            logger.debug('Successfully saved all_data to file.')
            
        except ValueError:
            logger.critical('Did not save concatentaed traces due to dimension mismatch.')
            logger.critical("This means a cell was lost in between batches and caiman_online can't complete :(")
            # ? should I raise an error here???
            raise
            
        self.advance()