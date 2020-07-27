import json
# from run_caiman_ws import SISocketServer
# import socketio

from flask import Flask
from flask_socketio import SocketIO

app = Flask(__name__)
socketio = SocketIO(app)
host = '0.0.0.0' # listen on all ips
port = 5000 # use port 5000

class ScanImageSession:
    
    def __init__(self, expt): 
        self.expt = expt
               
        self.acqs_done = 0
        self.acqs_this_batch = 0
        self.acq_per_batch = 5
        self.expt.batch_size = self.acq_per_batch
        
        self.trial_lengths = []
        self.traces = []
        # self.stim_times = []
        # self.stim_conds = []
        
    def update(self):
        """
        Updates acq counters and anything else that needs to keep track of trial counts.
        """
        if self.acqs_done == 0:
            self.expt.segment_mm3d()
            # self.expt.segment() for if you want to provide the structural image manually
        # else:
            # get data from caiman main

        self.acqs_done += 1
        self.acqs_this_batch += 1
     
    
@socketio.on('acq done')
def handle_acq_done(si):
    """
    Handles the SI 'acq done' message event. Send when a tiff/acquistion is completed. Calls
    a new caiman fit after acq_per_batch is satisfied.
    """
    si.update()
    print(f'SI says acq done. ({si.acqs_this_batch})')
    
    if si.acqs_this_batch >= si.acq_per_batch:
        si.acqs_this_batch = 0
        print('Starting caiman fit...')
        si.expt.do_next_group()
        
        # update data and send it out
        si.trial_lengths.append(si.expt.splits)
        si.traces.append(si.expt.C.tolist())
        
        out = {
            'trial_lengths': si.trial_lengths,
            'traces': si.traces
        }
        print('sending trial data to daq.')
        socketio.emit('new data', out)
    
@socketio.on('connect', namespace='/daq')
def connect_daq():
    print(f'[INFO] DAQ client sucessfully connected: {flask.request.sid()}')
    
@socketio.on('connect', namespace='/si')
def connect_si():
    print(f'[INFO] SI client sucessfully connected: {flask.request.sid()}')



if __name__ == '__main__':
    expt = OnlineAnalysis(caiman_params, **image_params)
    si = ScanImageSession(expt)
    
    print(f'[INFO] Starting server at http://localhost:{port}')
    socketio.run(app, host, port)