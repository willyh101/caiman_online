import websockets
import asyncio

class BaseServer:
    def __init__(self, ip, port):
        self.ip = ip
        self.port = port
        self.url = f'ws://{ip}:{port}'
        print('Starting server...')
        start_server = websockets.serve(self.websocket_handler, self.ip, self.port)
        asyncio.get_event_loop().run_until_complete(start_server)
        asyncio.get_event_loop().run_forever()
        
    async def websocket_handler(self, websocket, path):
        consumer_task = asyncio.ensure_future(
            self.handle_incoming(websocket, path)
        ) 
        
        producer_task = asyncio.ensure_future(
            self.handle_outgoing(websocket, path)
        )
        
        done, pending = await asyncio.wait(
            [consumer_task, producer_task],
            return_when = asyncio.FIRST_COMPLETED,
        )
        
        for task in pending:
            task.cancel()
    
    async def handle_incoming(self, websocket, path):
        message = await websocket.recv()
        print(str(message))
        
    async def handle_outgoing(self, websocket, path):
        msg = input('message: ')
        await websocket.send(msg)