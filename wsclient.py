import asyncio
from plot import make_ori_figure, plot_ori_dists
from caiman_analysis import process_data
from vis import run_pipeline, create_df
import websockets
import matplotlib.pyplot as plt
from termcolor import cprint
import pandas as pd
import json
import os

# check this
path = 'C:/path/to/daq/saving'
os.chdir(path)

class DaqClient:
    
    def __init__(self, ip, port):
        self.ip = ip
        self.port = port
        self.url = f'ws://{ip}:{port}'
        
        self.acqs_recvd = 0
        
        cprint(f'[INFO] Starting DAQ WS Client at {self.url}', 'yellow')
        self.loop = asyncio.get_event_loop()
        self.loop.run_until_complete(self.run_ws())
        asyncio.get_event_loop().run_forever()
        
    async def run_ws(self):
        """
        Starts the WS Client.
        """
        while True:
            try:
                async with websockets.connect(self.url) as websocket:
                    self.websocket = websocket
                    data = await websocket.recv()
                    self.handle_data(data)
            except websockets.ConnectionClosed:
                cprint('[WARNING] Wconnection terminated!', 'red')
                break
        print('quitting...')
        self.loop.quit()

                
    def handle_data(self, data):
        
        print('got data')
        plt.close('all')
        
        analysis_window = (0.2, 0.8, 1.4, 2.0)
        traces = process_data(data['c'], data['splits'])
        
        df = create_df(traces, data['stim_conds'], 'ori')
        df, mdf = run_pipeline(df, analysis_window)
        
        make_ori_figure(df, mdf)
        plot_ori_dists(mdf)
        
        # save output data
        # but maybe save it when it is quit gracefully
        cell_df = mdf.groupby('cell').mean()[
            ['vis_resp', 'pval', 'pref', 'ortho', 'pdir', 'osi']
        ]
        
        locs = pd.DataFrame(json.loads(data['coords']))['CoM']
        locs.index = locs.index.astype('int64')
        
        cell_df = cell_df.join(locs)
        
        # saves it as a CSV that can be read in by MATLAB readtable()
        cell_df.to_csv()
        
if __name__ == '__main__':
    DaqClient('localhost', 5002)