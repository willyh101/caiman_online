import asyncio
from plot import make_ori_figure, plot_ori_dists
from caiman_analysis import process_data
from vis import run_pipeline, create_df
import websockets
import matplotlib.pyplot as plt

class DaqClient:
    
    def __init__(self, ip, port):
        self.ip = ip
        self.port = port
        self.url = f'ws://{ip}:{port}'
        
        self.acqs_recvd = 0
        
        print('Starting DAQ WS Client...')
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
                print('connection terminated!')
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
        
if __name__ == '__main__':
    DaqClient('localhost', 5002)