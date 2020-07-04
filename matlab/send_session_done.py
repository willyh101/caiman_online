import asyncio
from network_utils import send_this
   
if __name__ == '__main__':
    asyncio.get_event_loop().run_until_complete(send_this('session end'))