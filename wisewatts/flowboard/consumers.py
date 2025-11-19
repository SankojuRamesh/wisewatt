# myapp/consumers.py
import json
from channels.generic.websocket import AsyncWebsocketConsumer
# myapp/consumers.py
class ClientConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        await self.accept()
        await self.channel_layer.group_add("sensors", self.channel_name)

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard("sensors", self.channel_name)

    async def sensor_update(self, event):
        payload = event.get("payload", {})

        # Here we send the payload **directly**, not wrapped in {type:"sensor", data:payload}
        await self.send(text_data=json.dumps(payload))
