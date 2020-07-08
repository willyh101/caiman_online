import websockets
import asyncio

IP = 'localhost'
PORT = 5050 # needs to be different than the experiment runner

class DataServer:
    
    def __init__(self, ip, port):
        self.ip = ip
        self.port = port
        self.url = f'ws://{ip}:{port}'
        
        print('Starting Online Data Server...', end=' ')
        self.start_server()
        
        
    def start_server(self):
        print('ready to send!')
        websockets.serve(handle_outgoing, self.ip, self.port)
        self.loop = asyncio.get_event_loop()
        self.loop.run_forever()
        
    async def handle_outgoing(self, data, websocket, path):
        await websocket.send(data)
        print('Sent new data to DAQ.')
        
    def prep_outgoing(self, data, type):
        pass