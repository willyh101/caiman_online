from glob import glob
from caiman_online.parallel import OnAcidParallel
from caiman_online.comm import SIWebSocketServer

ip = 'localhost'
port = 5000

srv_folder = 'E:/caiman_scratch/fake_server'
template_path = glob('E:/caiman_scratch/ori2/*.mat')[0]

x_start = 100
x_end = 400

batch_size = 5
frame_rate = 6.36
channels = 2 
planes = 3
tiff_folder = 'E:/caiman_scratch/ori2/'
tiffs_per_batch = 10

dxy = (1.5, 1.5) # spatial resolution in x and y in (um per pixel)
max_shift_um = (12., 12.) # maximum shift in um
patch_motion_xy = (100., 100.) # patch size for non-rigid correction in um

image_params = {
    'nchannels': channels,
    'nplanes': planes,
    'x_start': x_start, 
    'x_end': x_end,
    'folder': tiff_folder,
    'batch_size_tiffs': tiffs_per_batch
}

caiman_params = {
    'fr': frame_rate,
    'overlaps': (24, 24),
    'max_deviation_rigid': 3,
    'p': 1,  # deconv 0 is off, 1 is slow, 2 is fast
    'nb': 3,  # background compenents -> nb: 3 for complex
    'decay_time': 1.0,  # sensor tau
    'gSig': (5, 5),  # expected half size of neurons in pixels, very important for proper component detection
    'only_init': False,  # has to be `False` when seeded CNMF is used
    'rf': None,  # half-size of the patches in pixels. Should be `None` when seeded CNMF is used.
    'pw_rigid': True,  # piece-wise rigid flag
    'ssub': 1,
    'tsub': 1,
    'do_merge': False, # new found param, testing
    'update_background_components': False,
    'merge_thr': 0.9999,
    'num_frames_split': 20,
    'border_nan': 'copy',
    'max_shifts': [int(a/b) for a, b in zip(max_shift_um, dxy)],
    'strides': tuple([int(a/b) for a, b in zip(patch_motion_xy, dxy)])
}

if __name__ == '__main__':
    expt = OnAcidParallel(params=caiman_params, **image_params)
    expt.make_templates(template_path)
    srv = SIWebSocketServer(ip, port, srv_folder, tiffs_per_batch, expt)