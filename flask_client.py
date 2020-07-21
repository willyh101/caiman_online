import socketio

sio = socketio.Client()

@sio.event
def message(data):
    print(f'got message: {message}')
    
