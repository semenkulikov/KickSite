from channels.generic.websocket import AsyncJsonWebsocketConsumer
import requests
from .models import KickAccount
from django.contrib.auth import get_user_model
import json
from playwright.async_api import async_playwright
from channels.db import database_sync_to_async

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
            # Получаем инфу о канале через playwright (async)
            try:
                data = await self.get_channel_info(channel)
                await self.send_json({"event": "KICK_CHANNEL_INFO", "data": data})

                # --- Логика аккаунтов (теперь асинхронная) ---
                user = self.scope.get("user")
                accounts_dict = await self.get_user_accounts(user)
                await self.send_json({"event": "KICK_LOAD_ACCOUNTS", "message": accounts_dict})

            except Exception as e:
                await self.send_json({"event": "KICK_CHANNEL_INFO", "error": f"Kick API error: {e}"})
        else:
            await self.send_json({"event": "KICK_ECHO", "data": content})

    @database_sync_to_async
    def get_user_accounts(self, user):
        if user and user.is_authenticated:
            accounts = KickAccount.objects.filter(user=user)
        else:
            accounts = KickAccount.objects.all()
        return {acc.login: bool(acc.token) for acc in accounts}

    async def get_channel_info(self, channel):
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.goto(f"https://kick.com/api/v2/channels/{channel}")
            # Ждём загрузки json (body.innerText)
            json_data = await page.evaluate("() => document.body.innerText")
            await browser.close()
        return json.loads(json_data)

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