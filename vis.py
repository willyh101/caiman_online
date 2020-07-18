import xarray as xr
import pandas as pd
import numpy as np
import scipy.stats as stats

def run_pipeline(df, analysis_window, col_name):
    """
    [summary]

    Args:
        df ([type]): [description]
    """
    
    mdf = make_mean_df(df, analysis_window, col_name)

    cells, pvals = find_vis_resp(mdf)
    prefs, orthos = po(mdf)
    pdirs = pdir(mdf)

    mdf.loc[:, 'vis_resp'] = False
    mdf.loc[mdf.cell.isin(cells), 'vis_resp'] = True

    mdf = mdf.join(pd.Series(pvals, name='pval'), on='cell')

    mdf = mdf.join(prefs, on='cell')
    mdf = mdf.join(orthos, on='cell')
    mdf = mdf.join(pdirs, on='cell')

    osis = osi(mdf)
    mdf = mdf.join(osis, on='cell')

    df = df.join(prefs, on='cell')
    df = df.join(orthos, on='cell')
    df = df.join(pdirs, on='cell')
    df = df.join(osis, on='cell')
    
    return df, mdf

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

def make_mean_df(df, win, col):
    """
    Alias for meanby. Just easier to remember and understand...
    
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
    return meanby(df, win, col)

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
    base = df[(df.time > win[0]) & (df.time < win[1])].groupby(['cell', col, 'trial']).mean().reset_index()
    resp = df[(df.time > win[2]) & (df.time < win[3])].groupby(['cell', col, 'trial']).mean().reset_index()
    resp['df'] = resp['df'] - base['df']
    return resp

def find_vis_resp(df, p=0.05, test='anova'):
    """
    Takes a mean dataframe (see meanby) and finds visually responsive cells using 
    a 1-way ANOVA test.
    
    Args:
        df (pd.DataFrame): mean dataframe (trials, cells, vis_condition)
        p (float, optional): p-valuse to use for significance. Defaults to 0.05.
        test (str, optional): statistical test to use, only one option now. Defaults to 'anova'.

    Returns:
        np.array of visually responsive cells
        np.array of p values for all cells
    """
    
    # for adding others later
    tests = {
        'anova': _vis_resp_anova(df)
    }
    
    p_vals = tests[test]
    vis_cells = np.where(p_vals < p)[0]

    n = vis_cells.size
    c = p_vals.size
    print(f'There are {n} visually responsive cells, out of {c} ({n/c*100:.2f}%)')

    return vis_cells, p_vals

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
    po = vals.df[vals.pref == vals.ori].groupby('cell').mean().values
    oo = vals.df[vals.ortho == vals.ori].groupby('cell').mean().values
    osi = _osi(po, oo)
    osi = pd.Series(osi, name='osi')

    return osi

def _osi(preferred_responses, ortho_responses):
    return ((preferred_responses - ortho_responses)
            / (preferred_responses + ortho_responses))

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