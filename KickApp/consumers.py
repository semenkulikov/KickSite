from channels.generic.websocket import AsyncJsonWebsocketConsumer
import requests
from .models import KickAccount
from django.contrib.auth import get_user_model
import json
from playwright.sync_api import sync_playwright

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
            # Получаем инфу о канале через playwright
            try:
                with sync_playwright() as p:
                    browser = p.chromium.launch(headless=True)
                    page = browser.new_page()
                    page.goto(f"https://kick.com/api/v2/channels/{channel}")
                    # Ждём загрузки json (body.innerText)
                    json_data = page.evaluate("() => document.body.innerText")
                    browser.close()
                data = json.loads(json_data)
                await self.send_json({"event": "KICK_CHANNEL_INFO", "data": data})
                # --- Логика аккаунтов ---
                user = self.scope.get("user")
                if user and user.is_authenticated:
                    accounts = KickAccount.objects.filter(user=user)
                else:
                    accounts = KickAccount.objects.all()
                accounts_dict = {acc.login: bool(acc.token) for acc in accounts}
                await self.send_json({"event": "KICK_LOAD_ACCOUNTS", "message": accounts_dict})
            except Exception as e:
                await self.send_json({"event": "KICK_CHANNEL_INFO", "error": f"Kick API error: {e}"})
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