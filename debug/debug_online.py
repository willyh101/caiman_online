from caiman_main import OnlineAnalysis, NotSeeded, DropAcid

ip = 'localhost'
port = 5000

# image = np.array of mean image that is serving as structural template, needs to be 2D cropped size x 512 mean image
# image_path = path/to/image/to/load (must already be cropped to match x_start:x_end)

dxy = (1.5, 1.5) # spatial resolution in x and y in (um per pixel)
max_shift_um = (12., 12.) # maximum shift in um
patch_motion_xy = (25., 25.) # patch size for non-rigid correction in um

image_params = {
    'channels': 2,
    'planes': 3,
    'x_start': 100,
    'x_end': 400,
    'folder': 'E:/caiman_scratch/ori/' # this is where the tiffs are, make a sub-folder named out to store output data
}

caiman_params = {
    'fr': 6,  # imaging rate in frames per second, per plane
    'overlaps': (24, 24),
    'max_deviation_rigid': 3,
    'p': 1,  # deconv 0 is off, 1 is slow, 2 is fast
    'nb': 4,  # background compenents -> nb: 3 for complex
    'decay_time': 1.0,  # sensor tau
    'gSig': (7, 7),  # expected half size of neurons in pixels, very important for proper component detection
    'only_init': False,  # has to be `False` when seeded CNMF is used
    'rf': None,  # half-size of the patches in pixels. Should be `None` when seeded CNMF is used.
    'pw_rigid': True,  # piece-wise rigid flag
    'ssub': 1,
    'tsub': 1,
    'merge_thr': .99,
    'num_frames_split': 50,
    'border_nan': 'copy',
    'max_shifts': [int(a/b) for a, b in zip(max_shift_um, dxy)],
    'strides': tuple([int(a/b) for a, b in zip(patch_motion_xy, dxy)])
}

if __name__ == '__main__':
    expt = OnlineAnalysis(caiman_params, **image_params)
    expt.segment_mm3d()
    expt.do_next_group()