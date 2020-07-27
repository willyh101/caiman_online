# reshape traces (trials, cell, time) and display them as image
plt.imshow(ftraces.transpose((1,0,2)).reshape((304,-1)), aspect='auto')

# make the cell dataframe
mdf.groupby('cell').mean()[['vis_resp', 'pval', 'pref', 'ortho', 'pdir', 'osi']].reset_index()