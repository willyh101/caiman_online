import asyncio
import websockets

class DaqClient:
    
    def __init__(self, ip, port):
        self.ip = ip
        self.port = port
        self.url = f'ws://{ip}:{port}'
        
        self.acqs_recvd = 0
        
        print('Starting DAQ WS Client...')
        self.loop = asyncio.get_event_loop().run_until_complete(self.run_ws())
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

                
    def handle_data(self, data):
        print('got data')
        print(str(data))
        
        
if __name__ == '__main__':
    DaqClient('localhost', 5001)