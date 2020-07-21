import json
from run_caiman_ws import SISocketServer
import socketio


class SISocketServer:
    
    def __init__(self, ip, port):
        self.ip = ip
        self.port = port
        self.url = f'http://{ip}:{port}'
        
        self.acqs_done = 0
        self.acqs_this_batch = 0
        self.acq_per_batch = 5
        self.expt.batch_size = self.acq_per_batch
        
        self.trial_lengths = []
        self.traces = []
        self.stim_times = []
        self.stim_conds = []
        
        self.sio = socketio.Client()
        self.sio.connect(self.url)

    @socketio.on('message')
    def handle_message(message):
        print(f'got message: {message}')
        
    @socketio.on('json')
    def handle_json(json_data):
        print(f'recd generic json data {json_data}')
        
    @socketio.on('acq done')
    def handle_acq_done(self):
        """
        Handles the SI 'acq done' message event. Send when a tiff/acquistion is completed. Calls
        a new caiman fit after acq_per_batch is satisfied.
        """
        self.update()
        print(f'SI says acq done. ({self.acqs_this_batch})')
        
        if self.acqs_this_batch >= self.acq_per_batch:
            self.acqs_this_batch = 0
            print('Starting caiman fit...')
            self.expt.do_next_group()
            
            # update data and send it out
            self.trial_lengths.append(self.expt.splits)
            self.traces.append(self.expt.C.tolist())
            self.send_outgoing()


if __name__ == '__main__':
    socketio.run(app)