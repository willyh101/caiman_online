import json
import os

import websocket
import pandas as pd
import matplotlib.pyplot as plt

from plot import make_ori_figure, plot_ori_dists
from caiman_analysis import process_data
from vis import run_pipeline, create_df
from wscomm.alerts import WebSocketAlert

# check this
path = 'E:/caiman_scratch/results'
os.chdir(path)

ip = 'localhost'
port = 5002
url = f'ws://{ip}:{port}'

ws = websocket.create_connection(url)
WebSocketAlert(f'Starting DAQ WS Client at {url}', 'info')
WebSocketAlert('Connection establisted.', 'success')

try:
    while True:
        print(ws.recv())
        
except ConnectionResetError:
    WebSocketAlert('Host connection dropped', 'error')
    
finally:
    ws.close()