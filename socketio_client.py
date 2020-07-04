"""
Uses socket-io to recieve messages.
"""

import socketio

sio = socketio.Client()
ip = 'http://localhost:5000'

sio.connect(ip)
sio.emit('message', 'acq done')

# @sio.event
# def message(data):
#     pass

# @sio.event
# def json(data):
#     pass

# @sio.event
# def plot(data):
#     pass