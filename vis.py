import xarray as xr
import pandas as pd
import numpy as np
import scipy.stats as stats
import sys
sys.path.append('G:/My Drive/Code')
import holoframe as hf


def create_df(traces, vis_stim, vis_name, fr=None):
    """
    Make the data frame for the analysis. Needs traces (cell x trials x time),
    a trialwise list of visIDs/orientations and the framerate of acq to get
    time in seconds.

    Inputs:
        traces (array): cells x trials x time
        vis_stim (array): trialwise list of vis stims (ori, contrast, etc.) shown
    """
    # standard make df
    df = xr.DataArray(traces.T).to_dataset(dim='dim_0').to_dataframe()
    df = df.reset_index(level=['dim_1', 'dim_2'])
    df = pd.melt(df, ('dim_1', 'dim_2'))
    df = df.rename(columns = {'dim_1':'cell', 'dim_2':'trial', 'variable':'time', 'value':'df'})

    # add real-time
    if fr is not None:
        df['frame'] = df['time']
        df['time'] = df['frame']/fr

    # append orientation
    df = df.join(pd.Series(vis_stim, name=vis_name), on='trial')

    return df

def find_vis_resp(df, win, p=0.05):
    """
    df (dataframe): full data frame
    win (tuple): window to average over
    p (0.05, float): p-value to be considered significant
    """

    if len(win) == 2:
        temp = df[(df.time > win[0]) & (df.time < win[1])]
        temp2 = temp.groupby(['cell', 'ori', 'trial']).mean().reset_index() # gets trial means
    elif len(win) == 4:
        temp_base = df[(df.time > win[0]) & (df.time < win[1])].groupby(['cell', 'ori', 'trial']).mean().reset_index()
        temp2 = df[(df.time > win[2]) & (df.time < win[3])].groupby(['cell', 'ori', 'trial']).mean().reset_index()
        temp2['df'] = temp2['df'] - temp_base['df']
    else:
        raise ValueError('win must be 2 or 4 values!')

    # calculate vis resp pvals
    p_val = _vis_resp_anova(temp2)
    df = df.add_cellwise(p_val, name='vis_ps')
    df['vis_resp'] = df['vis_ps'] < 0.05

    n = df[df.vis_resp == True].cell.nunique()
    c = df.cell.nunique()
    print(f'There are {n} visually responsive cells, out of {c} ({n/c*100:.2f}%)')
    percent = n/c*100

    return df


def _vis_resp_anova(data):
    """Determine visual responsiveness by 1-way ANOVA."""

    f_val = np.empty(data.cell.nunique())
    p_val = np.empty(data.cell.nunique())

    for cell in data.cell.unique():
        temp3 = data[data.cell==cell]
        temp4 = temp3[['ori', 'trial', 'df']].set_index(['ori','trial'])
        samples = [col for col_name, col in temp4.groupby('ori')['df']]
        f_val[cell], p_val[cell] = stats.f_oneway(*samples)

    return p_val

def meanby(df, win, col):
    """
    Takes the mean by a condition in the data frame betweeen 2 timepoints and
    returns a mean dataframe reduced over the column condition.

    Inputs:
        df: the dataframe
        start (int): start time in whatever 'time' is in the dataframe
        stop (int): same as start but for stop time
        col (str): column name that you are meaning over

    Returns:
        mean dataframe

    """

    # implemented trialwise subtraction
    assert len(win) == 4, 'Must give 4 numbers for window.'
    base = df[(df.time > win[0]) & (df.time < win[1])].groupby(['cell', 'ori', 'trial']).mean().reset_index()
    resp = df[(df.time > win[2]) & (df.time < win[3])].groupby(['cell', 'ori', 'trial']).mean().reset_index()
    resp['df'] = resp['df'] - base['df']
    return resp


def po(mdf):
    """
    Takes a mean dataframe (see meanby) and returns preferred and
    orthagonal orientation in orientation space (mod 180).
    
    General procedure:
        1. Remove blank trial conditions (specified as -45 degs)
        2. Modulo 0-315* to 0-135* (mod excludes the number you put in)
        3. Get mean response by cell and orientation.
        4. Find index of max df, corresponding to PO.
        5. Subtract 90* from PO and mod 180 to get ortho

    Args:
        mdf (pd.DataFrame): mean response dataframe, generated from meanby (above)

    Returns:
        pd.Series of pref_oris
        pd.Series of ortho_oris
    """
    vals = mdf.loc[mdf.ori != -45]
    vals['ori'] = vals['ori'] % 180

    vals = vals.groupby(['cell', 'ori']).mean().reset_index()

    pref_oris = vals.set_index('ori').groupby('cell')['df'].idxmax()
    pref_oris.name = 'pref'
    
    ortho_oris = (pref_oris - 90) % 180
    ortho_oris.name = 'ortho'    

    return pref_oris, ortho_oris

def pdir(df):
    """Calculates pref dir."""
    df = df.loc[df.ori != -45]
    pref_dir = df.set_index('ori').groupby(['cell'])['df'].idxmax()
    pref_dir.name = 'pdir'

    return pref_dir

def osi(df):
    """Takes the mean df."""
    vals = df.copy()
    # min subtract so there are no negative values
    vals['df'] -= vals['df'].min()
    # added set_index
    vals = vals.set_index('cell')
    # needs to have groupby...
    po = vals.df[vals.pref == vals.ori].groupby('cell').mean()
    oo = vals.df[vals.ortho == vals.ori].groupby('cell').mean()
    osi = ((po - oo)/(po + oo))

    return osi