ip = 'localhost'
port = 5002
srv_folder = 'F:/caiman_out' # path to caiman data output folder on server
template_path = glob('D:/caiman_temp/template/*.mat')[0] # path to mm3d file


image_params = {
    'channels': 2,
    'planes': 3,
    'x_start': 100,
    'x_end': 400,
    'folder': 'D:/caiman_temp/', # this is where the tiffs are, make a sub-folder named out to store output data
}

###----CAIMAN PARAMS----###
# put any params for caiman here in dictionary
# the first lines are just for doing ums <-> pixels but can also be altered

# motion correction spatial components
dxy = (1.5, 1.5) # spatial resolution in x and y in (um per pixel)
max_shift_um = (12., 12.) # maximum shift in um
patch_motion_xy = (100., 100.) # patch size for non-rigid correction in um

# edit parameters here
caiman_params = {
    'fr': 6,  # imaging rate in frames per second, per plane
    'overlaps': (24, 24),
    'max_deviation_rigid': 3,
    'p': 0,  # deconv 0 is off, 1 is slow, 2 is fast
    'nb': 2,  # background compenents -> nb: 3 for complex
    'decay_time': 1.0,  # sensor tau
    'gSig': (5, 5),  # expected half size of neurons in pixels, very important for proper component detection
    'only_init': False,  # has to be `False` when seeded CNMF is used
    'rf': None,  # half-size of the patches in pixels. Should be `None` when seeded CNMF is used.
    'pw_rigid': True,  # piece-wise rigid flag
    'ssub': 1, # spatial subsampling (ie. 2 would be 1/2 the data)
    'tsub': 1, # temporal subsampling
    'merge_thr': 0.9, # merge ROIs
    'num_frames_split': 20,
    'border_nan': 'copy',
    'max_shifts': [int(a/b) for a, b in zip(max_shift_um, dxy)],
    'strides': tuple([int(a/b) for a, b in zip(patch_motion_xy, dxy)])
}