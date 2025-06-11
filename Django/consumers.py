import json
from channels.generic.websocket import AsyncJsonWebsocketConsumer


class DjangoWS(AsyncJsonWebsocketConsumer):

    async def connect(self):
        print("WS CONNECT 11111111111111")
        print(self.scope['url_route'])

        await self.accept()

    async def disconnect(self, close_code):
        print("WS DISCONNECT 33333333333", close_code)

    async def receive(self, text_data):
        print("WS RECEIVE 2222222")
        response = json.loads(text_data)
        print(response)
        event = response.get("event", None)
        message = response.get("message", None)
        await self.send_message({"message": message, "event": event})

    async def send_message(self, res):
        """ Receive message from room group """
        # Send message to WebSocket
        await self.send(text_data=json.dumps({
            "payload": res,
        }))