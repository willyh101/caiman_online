"""
Code for basic plotting. Uses matplotlib and seaborn.
"""
import matplotlib.pyplot as plt
import matplotlib as mpl
from matplotlib.gridspec import GridSpec
import seaborn as sns

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

def plot_ori_dists(mdf):
    fig, (ax1, ax2, ax3) = plt.subplots(1,3, constrained_layout=True, figsize=(10,3))

    data = mdf[(mdf.vis_resp == True) & (mdf.ori > -45)].copy()
    data['ori180'] = data['ori'] % 180
    oris = data.ori180.unique()

    vals = data.groupby(['cell']).mean()
    data[data.isna()] = 'None'

    # pref hist
    ax1.hist(vals['pref'])
    ax1.set_xlabel('Preferred Orientation')
    ax1.set_ylabel('Count')
    ax1.set_xticklabels(data.ori180.unique())
    ax1.set_xticks(oris)

    # pdir hist
    ax2.hist(vals['pdir'])
    ax2.set_xlabel('Preferred Direction')
    ax2.set_ylabel('Count')
    ax2.set_xticklabels(data.ori.unique())
    ax2.set_xticks(data.ori.unique())

    # osi hist
    kde_opts = {
        'lw':2
    }

    celldf = data[data.vis_resp==True].groupby('cell').mean()

    sns.distplot(celldf.osi.unique(), kde_kws=kde_opts, ax=ax3)
    ax3.set_xlim([0,1])
    ax3.set_xlabel('OSI')
    ax3.set_ylabel('KDE')

    plt.show()
    
# def pl
            

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