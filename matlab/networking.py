"""
MATLAB interface for interacting with Caiman socket server. Functions inside can be called from
the command line as:
    python networking.py hi
    python networking.py send_

Requires websocket-client (pip install websocket-client)

Callbacks in run_caiman_ws.py must match exactly!
"""
import websocket
import sys
import json

# use to specify location of run_caiman_ws.py websocket server
IP = 'localhost'
PORT = 5001


def send_this(message, ip=IP, port=PORT):
    """
    Takes a message and sends it to the caiman WS server via formatted JSON.

    Args:
        message (str, dict): python string or dictionary to send, formatted to a JSON
        ip (str, optional): IP location of host. Defaults to IP.
        port (int, optional): WS port on host. Defaults to PORT.
    """
    message = json.dumps(message)
    url = f'ws://{ip}:{port}'
    ws = websocket.create_connection(url)
    ws.send(message)
    ws.close()
    
def setup(nchannels, nplanes):
    out = {
        'kind': 'setup',
        'nchannels': nchannels,
        'nplanes': nplanes
    }
    return send_this(out)
    
def hi():
    """Tests for connection, says hi."""
    return send_this('hi')

def trial_done():
    """Signals tiff/trial completed."""
    return send_this('acq done')

def session_done():
    """Signals acq/expt completed."""
    return send_this('session done')

def uhoh():
    """Causes the server to stop."""
    return send_this('uhoh')

def wtf():
    """Also causes the server to stop and throw a BAD ERROR. Mainly for internal 
    use by caiman_main.py"""
    return send_this('wtf')


if __name__ == '__main__':
    args = sys.argv[1:]
    func = args.pop(0)
    globals()[func](*args)