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