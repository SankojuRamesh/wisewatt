# device_ws.py (python websockets)
import asyncio
import websockets
import json
from datetime import datetime

WS_URL = "ws://your-server-host:8000/ws/device/"

async def run():
    while True:
        try:
            async with websockets.connect(WS_URL) as ws:
                while True:
                    data = {
                        "device_id": "tank-1",
                        "distance_cm": 400,
                        "pump_on": True,
                        "battery": 3.75,
                        "ts": datetime.utcnow().isoformat() + "Z"
                    }
                    await ws.send(json.dumps(data))
                    await asyncio.sleep(1)
        except Exception as e:
            print("ws error", e)
            await asyncio.sleep(2)

asyncio.run(run())
