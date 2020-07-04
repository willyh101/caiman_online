"""
MATLAB interface for interacting with Caiman socket server.
Requires websockets (pip install websockets)
"""
import websockets
import asyncio

IP = 'localhost'
PORT = 5000

async def send_this(message, ip=IP, port=PORT):
    url = f'ws://{ip}:{port}'
    async with websockets.connect(url) as websocket:
        await websocket.send(message)
        
def send_trial_done():
    asyncio.get_event_loop().run_until_complete(send_this('acq done'))
    
def send_session_done():
    asyncio.get_event_loop().run_until_complete(send_this('session end'))