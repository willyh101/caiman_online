from caiman_online.wrappers import tictoc
from caiman_online.analysis import extract_cell_locs
from caiman_online.workers import OnAcidWorker
import logging
from caiman_online.pipelines import OnAcidPipeline
from caiman_online.utils import ptoc, tic
import dask

logger = logging.getLogger('caiman_online')

class OnAcidParallel(OnAcidPipeline):
    def fit_plane(self, plane, splits, tiffs):
        
        print(f'***** Starting Plane {plane} OnACID... *****')
        print('Starting OnACID processing...')
        ct = tic()
        
        # CNMF PROCESSING
        logger.debug('Starting OnACID worker.')
        this_ain = self.Ain[plane]
        acid_worker = OnAcidWorker(tiffs, this_ain, plane, 
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
            'splits': splits,
            'coords': locs
        }
        self.save_plane_json(plane=plane, save_path=acid_worker.out_path, **plane_data)
        
        ptoc(ct, start_string=f'***** Plane {plane} done.', end_string='s *****')
        
        # return c, dff, locs, acid_worker.out_path
            
    @tictoc
    def fit_batch(self):
        tiffs, splits = self.get_tiffs()
        
        # using dask.distrubted
        # requires a seperate install
        # client = Client()
        # future = [client.submit(self.fit_plane, p, splits, tiffs) for p in range(self.nplanes)]
        # future.result()
        
        # maybe faster with list concat
        fits = [dask.delayed(self.fit_plane)(p, splits, tiffs) for p in range(self.nplanes)]
        dask.compute(*fits)
        
        # same as above in formal loop, potentially slower
        # fit = dask.delayed(self.fit_plane)
        # fs = []
        # for plane in range(self.nplanes):
        #     fs.append(fit(plane, splits, tiffs))
        # dask.compute(*fs)
            
        