import asyncio
import json
import httpx
from channels.generic.websocket import AsyncWebsocketConsumer
from asgiref.sync import sync_to_async
from KickApp.models import KickAccount


async def send_kick_message(chatbot_id: int, channel: str, message: str, token: str):
    """Sends a message to a Kick chat."""
    async with httpx.AsyncClient() as client:
        try:
            # 1. Get chatteroom ID
            api_url = f"https://kick.com/api/v2/channels/{channel}"
            response = await client.get(api_url)
            response.raise_for_status()
            chatteroom_id = response.json().get("chatroom", {}).get("id")
            if not chatteroom_id:
                print(f"Could not find chatteroom ID for channel: {channel}")
                return

            # 2. Send message
            send_message_url = f"https://kick.com/api/v2/messages/send/{chatteroom_id}"
            headers = {
                'Authorization': token, # Токен уже содержит "Bearer "
                'Content-Type': 'application/json',
                'Accept': 'application/json',
            }
            payload = {
                'content': message,
                'type': 'message'
            }
            
            response = await client.post(send_message_url, headers=headers, json=payload, timeout=10)
            response.raise_for_status()
            
            print(f"Message sent successfully from account {chatbot_id} to {channel}")

        except httpx.HTTPStatusError as e:
            print(f"HTTP error sending message from {chatbot_id} to {channel}: {e.response.status_code} - {e.response.text}")
        except Exception as e:
            print(f"An error occurred sending message from {chatbot_id} to {channel}: {e}")


class KickAppChatWs(AsyncWebsocketConsumer):
    def __init__(self, *args, **kwargs):
        super().__init__(args, kwargs)
        self.channel_group_name = None
        self.work_task = None

    async def connect(self):
        await self.accept()

    async def disconnect(self, close_code):
        if self.work_task:
            self.work_task.cancel()
        
        if self.channel_group_name:
            await self.channel_layer.group_discard(
                self.channel_group_name,
                self.channel_name
            )

    async def receive(self, text_data=None, bytes_data=None):
        if not text_data:
            return
            
        json_data = json.loads(text_data)
        _type = json_data.get('type')

        if _type == 'KICK_SELECT_CHANNEL':
            channel_name = json_data.get('channel')
            if not channel_name:
                return

            self.channel_group_name = channel_name.replace(' ', '')
            await self.channel_layer.group_add(
                self.channel_group_name,
                self.channel_name
            )
            accounts = await sync_to_async(list)(KickAccount.objects.all().values('id', 'login'))
            await self.send(text_data=json.dumps({
                'type': 'KICK_ACCOUNTS',
                'accounts': accounts
            }))

        elif _type == 'KICK_START_WORK':
            if self.work_task and not self.work_task.done():
                print("Work is already in progress.")
                return

            message = json_data.get('message', 'Hello from the bot!')
            frequency = int(json_data.get('frequency', 60))
            self.work_task = asyncio.create_task(self.start_work(message, frequency))
            await self.send(text_data=json.dumps({'type': 'KICK_WORK_STARTED'}))

        elif _type == 'KICK_END_WORK':
            if self.work_task:
                self.work_task.cancel()
                self.work_task = None
                await self.send(text_data=json.dumps({'type': 'KICK_WORK_STOPPED'}))

    async def start_work(self, message: str, frequency: int):
        if not self.channel_group_name:
            print("Cannot start work without a channel selected.")
            return

        while True:
            try:
                accounts = await sync_to_async(list)(KickAccount.objects.filter(status=True).values('id', 'token'))
                if not accounts:
                    await self.send(text_data=json.dumps({
                        'type': 'KICK_ERROR',
                        'message': 'No active accounts found.'
                    }))
                    break 
                
                print(f"Starting message sending job for channel {self.channel_group_name} with {len(accounts)} accounts.")
                
                for account in accounts:
                    await send_kick_message(account['id'], self.channel_group_name, message, account['token'])
                    await asyncio.sleep(2) # Задержка между отправкой с разных аккаунтов

                await self.send(text_data=json.dumps({
                    'type': 'KICK_WORK_HEARTBEAT',
                    'message': f'Sent messages from {len(accounts)} accounts.'
                }))
                await asyncio.sleep(frequency) # Пауза перед следующим циклом рассылки

            except asyncio.CancelledError:
                print("Work task was cancelled.")
                break
            except Exception as e:
                print(f"An error occurred in the work loop: {e}")
                await self.send(text_data=json.dumps({
                    'type': 'KICK_ERROR',
                    'message': f'An error occurred: {str(e)}'
                }))
                break

class KickAppStatsWs(AsyncWebsocketConsumer):
    async def connect(self):
        await self.accept()
        
    async def disconnect(self, code):
        pass
        
    async def receive(self, text_data=None, bytes_data=None):
        pass
