"""
Code for basic plotting. Uses matplotlib and seaborn.
"""
import matplotlib.pyplot as plt
import matplotlib as mpl
from matplotlib.gridspec import GridSpec
from matplotlib.pyplot import subplot
import seaborn as sns
import numpy as np

mpl.rcParams['figure.constrained_layout.use'] = True
mpl.rcParams['savefig.dpi'] = 300 # default resolution for saving images in matplotlib
mpl.rcParams['savefig.format'] = 'png' # defaults to png for saved images (SVG is best, however)
mpl.rcParams['savefig.bbox'] = 'tight' # so saved graphics don't get chopped
sns.set_style('ticks',{'axes.spines.right': False, 'axes.spines.top': False}) # removes annoying top and right axis

def simple_psth(data, ax=None, figsize=(4,4), **plot_kws):
    
    if ax is None:
        ax = plt.gca()
        
    plot_kws.setdefault('cmap', 'viridis')
    plot_kws.setdefault('vmin', 0)
    plot_kws.setdefault('vmax', 1)
    
    # data = 
        
    ax.imshow(data, **plot_kws)
    
def average_trace(data, ax=None, **kwargs):
    if ax is None:
        ax = plt.gca()
        
def make_ori_figure(df, mdf, fig=None):
    if fig:
        plt.close(fig)
    
    plt.ion()
    
    n = df.ori.nunique()
    vis_conds = df.ori.unique()
    
    imdata = df.set_index(['ori']).groupby(['ori', 'cell', 'time'])['df'].mean().unstack(level=2)
    cells = mdf.set_index('cell')['df'].rank().nlargest(10).index.values
    

    widths = [1, 1]
    heights = [1, 1000] * n

    fig = plt.figure(figsize=(8,16), tight_layout=True, constrained_layout=True)
    gs = GridSpec(n*2, 2, height_ratios=heights, width_ratios=widths)

    for p, cond in zip(range(1,n*2,2), vis_conds):
        with sns.color_palette('hls'):
            ax = fig.add_subplot(gs[p,0])
            ax.imshow(imdata.loc[(cond, slice(None)), :], aspect='auto', cmap='viridis')
            ax.axis('tight')
            ax.set_ylabel('Cell')
        
    ax.set_xlabel('Time')

    for p, cond in zip(range(1,n*2,2), vis_conds):
        ax = fig.add_subplot(gs[p,1])
        plotdata = imdata.loc[(cond, cells), :].values.T
        ax.plot(plotdata, lw=2)
    #     g = sns.lineplot(x='time', y='df', data=df[(df['ori']==cond) & (df.cell.isin(cells))], ax=ax,
    #                      hue='cell', legend=False, n_boot=500)
        ax.set_xlabel('Time')
        ax.set_ylabel('df/F')
        
    for p, cond in zip(range(0,n*2,2), vis_conds):
        ax = fig.add_subplot(gs[p,:])  
        ax.set_xlabel(f'{cond} degrees')
        ax.xaxis.set_ticks([])
        ax.spines['bottom'].set_visible(False)
        ax.xaxis.set_ticklabels([])
        ax.yaxis.set_visible(False)

    plt.show()
        
        

# class SimpleOriFigure:
#     def __init__(self, dataframe):
#         self.dataframe = dataframe
            
#     def draw_psth(self, cat):
#         cats = self.data[cat].unique()
#         imdata = self.dataframe.set_index(['ori']).groupby(
#             ['ori', 'cell', 'time'])['df'].mean().unstack(level=2)
        
#         for ax in zip(axes[:,0], ):
            
            
    
#     def draw_examples(self):
#         pass        
    
#     def update_fig(self):
#         pass
        
#     def setup_fig(self):
#         plt.ion()
#         self.fig, self.axes = plt.subplots(self.data[cat].unique(), 2)
#         sns.despine(fig=self.fig, top=False, right=False)


# df.set_index(['ori']).groupby(['ori', 'cell', 'time']).mean()