from channels.generic.websocket import AsyncJsonWebsocketConsumer
import requests
from .models import KickAccount
from django.contrib.auth import get_user_model

class KickAppChatWs(AsyncJsonWebsocketConsumer):
    async def connect(self):
        await self.accept()
        await self.send_json({"event": "KICK_CONNECT", "message": "HELLO"})

    async def receive_json(self, content, **kwargs):
        event = content.get("event")
        message = content.get("message", {})
        if event == "KICK_SELECT_CHANNEL":
            channel = message.get("channel")
            if not channel:
                await self.send_json({"event": "KICK_CHANNEL_INFO", "error": "No channel specified"})
                return
            url = f"https://kick.com/api/v2/channels/{channel}"
            try:
                resp = requests.get(url, timeout=5)
                if resp.status_code == 200:
                    data = resp.json()
                    await self.send_json({"event": "KICK_CHANNEL_INFO", "message": data})
                    # --- Логика аккаунтов ---
                    user = self.scope.get("user")
                    if user and user.is_authenticated:
                        accounts = KickAccount.objects.filter(user=user)
                    else:
                        accounts = KickAccount.objects.all()
                    accounts_dict = {acc.login: bool(acc.token) for acc in accounts}
                    await self.send_json({"event": "KICK_LOAD_ACCOUNTS", "message": accounts_dict})
                else:
                    await self.send_json({"event": "KICK_CHANNEL_INFO", "error": f"Kick API error: {resp.status_code}"})
            except Exception as e:
                await self.send_json({"event": "KICK_CHANNEL_INFO", "error": str(e)})
        else:
            await self.send_json({"event": "KICK_ECHO", "data": content})

    async def disconnect(self, code):
        pass

class KickAppStatsWs(AsyncJsonWebsocketConsumer):
    async def connect(self):
        await self.accept()
        await self.send_json({"event": "KICK_STATS_CONNECT", "message": "HELLO"})

    async def receive_json(self, content, **kwargs):
        await self.send_json({"event": "KICK_STATS_ECHO", "data": content})

    async def disconnect(self, code):
        pass 