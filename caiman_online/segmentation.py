import warnings

with warnings.catch_warnings():
    warnings.simplefilter('ignore', category=FutureWarning)
    import caiman as cm
    from caiman.source_extraction.cnmf import params as params
    from caiman.motion_correction import MotionCorrect

from tifffile import tifffile
from ScanImageTiffReader import ScanImageTiffReader
import matplotlib.pyplot as plt



class MakeMasks3D:
    """Not yet fully working so dont use!"""
    def __init__(self, tiff, channels, planes, x_start, x_end, mc_opts, use_green_ch=False,):
        self.tiff = tiff
        self.channels = channels
        self.planes = planes
        self.x_start = x_start
        self.x_end = x_end
        self.xslice = slice(x_start, x_end)
        self.mc_opts = mc_opts
        self.use_green_ch = use_green_ch
        if self.use_green_ch == True:
            self.channel2use = 0
        else:
            self.channel2use = 1

        if self.mc_opts:
            self.opts = params.CNMFParams(params_dict=mc_opts)
        
        self.file_list = []
        self.images = []
        self.motion_corrected_images = []
        self.masks = []
        self.coords = None
        self.corr_images = []
        
    def crop_tiffs(self):
        self.images = []
        self.file_list = []
        for plane in list(range(self.planes)):
            time_slice = slice(plane*self.channels+self.channel2use, -1, self.channels*self.planes)
            with ScanImageTiffReader(self.tiff) as reader:
                data = reader.data()
                data = data[time_slice, : , self.xslice]
            self.images.append(data)
            tif_name = self.tiff.split('.')[0] + '_template_plane' + str(plane) + '.tif'
            self.file_list.append(tif_name)
            tifffile.imsave(tif_name, data)
            
    def view_planes(self):
        fig, axes = plt.subplots(1, self.planes, constrained_layout=True)
        for i,ax in enumerate(axes):
            image = self.images[i].mean(axis=0)
            ax.imshow(image)
            ax.set_aspect('equal', 'box')
            ax.axis('off')
            ax.set_title(f'Plane {i}')
        fig.suptitle('Original')
            
    def view_corrected(self):
        fig, axes = plt.subplots(1, self.planes, constrained_layout=True)
        for i,ax in enumerate(axes):
            image = self.motion_corrected_images[i]
            ax.imshow(image)
            ax.set_aspect('equal', 'box')
            ax.axis('off')
            ax.set_title(f'Plane {i}')
        fig.suptitle('Corrected')
    
    def view_corr(self):
        self.corr_images = []
        fig, axes = plt.subplots(1, self.planes, constrained_layout=True)
        for i,ax in enumerate(axes):
            image = self.motion_corrected_images[i]
            corr_im = cm.local_correlations(image, swap_dim=False)
            self.corr_images.append(corr_im)
            ax.imshow(image)
            ax.set_aspect('equal', 'box')
            ax.axis('off')
            ax.set_title(f'Plane {i}')
        fig.suptitle('Correlation Image')
        
    def motion_correct_red(self):
        c, dview, n_processes = cm.cluster.setup_cluster(
            backend='local', n_processes=None, single_thread=False)
        
        self.motion_corrected_images = []
        for plane in list(range(self.planes)):
            print(f'Starting motion correction plane {plane}')
            self.mc = MotionCorrect(self.file_list[plane], dview=dview, **self.opts.get_group('motion'))
            self.mc.motion_correct()
            self.motion_corrected_images.append(self.mc.total_template_els)
        cm.stop_server(dview=dview)
            
    def extract_masks(self, radius=7):
        self.masks = []
        self.coords = []
        if len(self.motion_corrected_images) > 0:
            image_source = self.motion_corrected_images
        else:
            image_source = self.images
        for plane in range(self.planes):
            self.masks.append(cm.base.rois.extract_binary_masks_from_structural_channel(image_source[plane])[0])
            self.coords.append(cm.utils.visualization.get_contours(self.masks[plane], 
                                                                   image_source[plane].shape,
                                                                   thr=0.99,
                                                                   thr_method='max'))
        
    def run(self):
        self.crop_tiffs()
        self.motion_correct_red()
        self.extract_masks()