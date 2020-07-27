import json
import socketio

sio = socketio.Client()

daq_ip = '192.168.10.102'
daq_socket = 5000
url = f'http://{daq_ip}:{daq_socket}'

def send_trial_data(trial_data):
    sio.emit('trial data', namespace='/daq')

@sio.event
def new_data(data):
    # parse and plot data
    pass

sio.connect(url)
sio.wait()

# how do I call a python function from matlab to trigger data to
# be sent over while the client is running
# does matlab have a socketio?