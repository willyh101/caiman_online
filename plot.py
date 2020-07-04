"""
Code for basic plotting. Uses matplotlib and seanborn.
"""
import matplotlib.pyplot as plt
import seaborn as sns

def psth(data, ax=None, figsize=(4,4), **plot_kws):
    if ax is None:
        ax = plt.gca()
        
    plot_kws.setdefault('cmap', 'viridis')
    plot_kws.setdefault('vmin', 0)
    plot_kws.setdefault('vmax', 3)
    
    f, ax = plt.subplots(figsize=figsize)
    
    ax = plt.imshow(data, **plot_kws)
    
def average_trace(data, ax=None, **kwargs):
    if ax is None:
        ax = plt.gca()
