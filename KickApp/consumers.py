import asyncio
import json
import httpx
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from asgiref.sync import sync_to_async
from django.db import models
from KickApp.models import KickAccount
from ProxyApp.models import Proxy
import requests
import websockets
import sys
import logging
import cloudscraper
import urllib.parse
import time
import re
import subprocess


async def send_kick_message_cloudscraper(chatbot_id: int, channel: str, message: str, token: str, session_token: str, proxy_url: str = ""):
    """
    Отправляет сообщение в чат Kick.com используя cloudscraper
    Точная копия рабочего кода kickchatsend.py
    """
    logger = logging.getLogger("kick.send")
    logger.setLevel(logging.DEBUG)
    if not logger.hasHandlers():
        logger.addHandler(logging.StreamHandler())
    
    logger.info(f"[SEND_MESSAGE] account={chatbot_id} channel={channel} message={message}")
    logger.debug(f"[SEND_MESSAGE] token={token}")
    logger.debug(f"[SEND_MESSAGE] session_token={session_token}")
    
    # Пока что игнорируем прокси, так как cloudscraper не работает с SOCKS5
    if proxy_url:
        logger.warning(f"[SEND_MESSAGE] Proxy {proxy_url} ignored - cloudscraper doesn't support SOCKS5 properly")
    
    # Извлекаем данные точно как в рабочем коде
    # В рабочем коде session_token содержит USERID|TOKEN
    session_raw = f"{chatbot_id}|{token.split('|')[1] if '|' in token else token}"
    if not session_raw:
        logger.error("[SEND_MESSAGE] No session_token provided")
        return False
    
    # Декодируем session_token для Bearer токена
    session_decoded = urllib.parse.unquote(session_raw)
    
    # Извлекаем XSRF-TOKEN из token точно как в рабочем коде
    # В рабочем коде XSRF-TOKEN берется из второй части после | в token
    xsrf_token = None
    if '|' in token:
        xsrf_token = token.split('|')[1] if len(token.split('|')) > 1 else None
    
    # Формируем cookie строку точно как в рабочем коде
    cookie_parts = []
    if session_raw:
        # session_token содержит USERID|TOKEN
        cookie_parts.append(f"session_token={session_raw}")
    if xsrf_token:
        # XSRF-TOKEN тоже URL-encoded
        cookie_parts.append(f"XSRF-TOKEN={xsrf_token}")
    
    cookie_string = "; ".join(cookie_parts)
    
    logger.debug(f"[SEND_MESSAGE] SESSION_RAW: {session_raw}")
    logger.debug(f"[SEND_MESSAGE] XSRF_TOKEN: {xsrf_token}")
    logger.debug(f"[SEND_MESSAGE] SESSION_DECODED: {session_decoded}")
    logger.debug(f"[SEND_MESSAGE] Cookie string: {cookie_string}")
    
    # Создаем cloudscraper точно как в рабочем коде
    S = cloudscraper.create_scraper()
    S.headers.update({
        "cookie": cookie_string,
        "user-agent": "Mozilla/5.0"
    })
    
    try:
        # Получаем chatroom_id точно как в рабочем коде
        logger.info(f"[SEND_MESSAGE] Getting channel info for: {channel}")
        response = S.get(f"https://kick.com/api/v2/channels/{channel}", timeout=10)
        logger.debug(f"[SEND_MESSAGE] GET {response.url} status={response.status_code}")
        
        if response.status_code != 200:
            logger.error(f"[SEND_MESSAGE] Channel lookup failed: {response.status_code} {response.text[:400]}")
            return False
        
        chat_id = response.json()["chatroom"]["id"]
        logger.info(f"[SEND_MESSAGE] Got chatroom_id: {chat_id}")
        
    except Exception as e:
        logger.error(f"[SEND_MESSAGE] Could not fetch channel info: {e}")
        return False
    
    # Отправляем сообщение точно как в рабочем коде
    url = f"https://kick.com/api/v2/messages/send/{chat_id}"
    
    headers = {
        "Authorization": f"Bearer {session_decoded}",
        "X-XSRF-TOKEN": xsrf_token if xsrf_token else "",  # still URL-encoded!
        "X-Requested-With": "XMLHttpRequest",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Referer": f"https://kick.com/{channel}",
        "cluster": "v2",                      # Kick's front-end sends this
    }
    
    payload = {
        "content": message,
        "type": "message",
        "message_ref": str(int(time.time() * 1000))  # ms epoch
    }
    
    logger.debug(f"[SEND_MESSAGE] Sending POST to: {url}")
    logger.debug(f"[SEND_MESSAGE] Headers: {headers}")
    logger.debug(f"[SEND_MESSAGE] Payload: {payload}")
    
    try:
        r = S.post(url, headers=headers, json=payload, timeout=10)
        logger.debug(f"[SEND_MESSAGE] POST {url} status={r.status_code}")
        logger.debug(f"[SEND_MESSAGE] Response content: {r.text}")

        if r.status_code == 201:
            logger.info(f"[SEND_MESSAGE] ✓ sent: {message}")
            return True
        elif r.status_code == 200:
            try:
                response_json = r.json()
                if response_json.get("message") == []: # Check if "message" key exists and its value is an empty list
                    logger.error(f"[SEND_MESSAGE] ❌ failed: empty response (возможно, требуется подписка/фоллов)")
                    logger.error(f"[SEND_MESSAGE] Response: {r.text}")
                    return False
                elif "FOLLOWERS_ONLY_ERROR" in r.text: # Still keep text check for this specific error
                    logger.error(f"[SEND_MESSAGE] ❌ failed: FOLLOWERS_ONLY_ERROR (требуется подписка/фоллов)")
                    logger.error(f"[SEND_MESSAGE] Response: {r.text}")
                    return False
                else:
                    logger.info(f"[SEND_MESSAGE] ✓ sent: {message}")
                    return True
            except json.JSONDecodeError:
                logger.error(f"[SEND_MESSAGE] ❌ failed: non-JSON 200 response (возможно, требуется подписка/фоллов)")
                logger.error(f"[SEND_MESSAGE] Response: {r.text}")
                return False
        else:
            logger.error(f"[SEND_MESSAGE] ❌ failed: {r.status_code}")
            logger.error(f"[SEND_MESSAGE] Response: {r.text[:400]}")
            return False

    except Exception as e:
        logger.error(f"[SEND_MESSAGE] Failed to send message: {e}")
        return False


async def get_channel_id_by_slug(channel_slug: str, token: str = None):
    """Получить channel_id по slug через API"""
    import httpx
    url = f"https://kick.com/api/v2/channels/{channel_slug}"
    headers = {
        'User-Agent': 'Mozilla/5.0',
        'Accept': 'application/json',
    }
    if token:
        headers['Authorization'] = f'Bearer {token}'
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, headers=headers)
        resp.raise_for_status()
        data = resp.json()
        return str(data['id'])


def ws_connect_compat(url, origin):
    # websockets >=15 не поддерживает extra_headers/headers, только origin
    return websockets.connect(url, origin=origin)


class KickAppChatWs(AsyncWebsocketConsumer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.channel_group_name = None
        self.work_task = None

    async def connect(self):
        await self.accept()

    async def disconnect(self, close_code):
        if self.work_task:
            self.work_task.cancel()
        if self.channel_group_name and self.channel_layer is not None:
            await self.channel_layer.group_discard(
                self.channel_group_name,
                self.channel_name
            )

    async def receive(self, text_data=None, bytes_data=None):
        print('[KICK-WS] RECEIVE:', text_data)
        if not text_data:
            return
            
        json_data = json.loads(text_data)
        _type = json_data.get('type')
        event = json_data.get('event')

        if event == 'KICK_CONNECT' or _type == 'KICK_CONNECT':
            pass
        elif _type == 'KICK_SELECT_CHANNEL':
            print('[KICK-WS] KICK_SELECT_CHANNEL:', json_data)
            channel_name = json_data.get('channel')
            if not channel_name:
                return

            self.channel_group_name = channel_name.replace(' ', '')
            if self.channel_layer is not None:
                await self.channel_layer.group_add(
                    self.channel_group_name,
                    self.channel_name
                )
            # Получаем все аккаунты
            accounts = await sync_to_async(list)(KickAccount.objects.all())
            semaphore = asyncio.Semaphore(10)  # лимит одновременных проверок
            @sync_to_async
            def get_proxy_str(acc):
                if hasattr(acc, 'proxy') and acc.proxy:
                    return str(acc.proxy.url)
                return None
            async def check_and_send(acc):
                proxy_str = await get_proxy_str(acc)
                async with semaphore:
                    try:
                        await asyncio.wait_for(acc.acheck_kick_account_valid(proxy=proxy_str), timeout=10)
                    except Exception:
                        acc.status = 'timeout'
                    account_status = {
                        'id': acc.id,
                        'login': acc.login,
                        'status': acc.status
                    }
                    await self.send(text_data=json.dumps({
                        'event': 'KICK_ACCOUNT_STATUS',
                        'message': account_status
                    }))
            await asyncio.gather(*(check_and_send(acc) for acc in accounts))

        elif _type == 'KICK_START_WORK':
            if self.work_task and not self.work_task.done():
                print("Work is already in progress.")
                return

            channel = self.channel_group_name or 'default'
            print(f"Work started for channel {channel}. Ready to send messages.")
            
            # Сразу запускаем работу, не ждем загрузки всех аккаунтов
            self.work_task = asyncio.create_task(self.start_work(json_data.get('message', 'Hello from the bot!'), 1))

        elif _type == 'KICK_SEND_MESSAGE':
            # Обработка отправки одиночного сообщения
            await self.handle_send_message(json_data.get('message', {}))

        elif _type == 'KICK_END_WORK':
            await self.end_work()

    async def start_work(self, message: str, frequency: int):
        if not self.channel_group_name:
            print('No channel selected for work')
            return

        print(f'Starting work for channel: {self.channel_group_name}')
        
        # Отправляем событие о начале работы
        import time
        await self.send(text_data=json.dumps({
            'event': 'KICK_START_WORK',
            'message': {
                'startWorkTime': time.time() * 1000  # время в миллисекундах
            }
        }))
        
        # Ждем отмены задачи (когда пользователь нажмет "End Work")
        try:
            while True:
                await asyncio.sleep(1)  # Просто ждем, не отправляем сообщения автоматически
        except asyncio.CancelledError:
            print("Work task was cancelled.")
            return

    async def end_work(self):
        """Stop work task"""
        if self.work_task:
            self.work_task.cancel()
            self.work_task = None
            await self.send(text_data=json.dumps({
                'event': 'KICK_END_WORK',
                'message': 'Work stopped'
            }))

    async def handle_send_message(self, message_data):
        """Handle KICK_SEND_MESSAGE event"""
        try:
            print(f"[SEND_MESSAGE] Received message data: {message_data}")
            
            channel = message_data.get('channel')
            account_login = message_data.get('account')
            message_text = message_data.get('message')
            
            if not all([channel, account_login, message_text]):
                error_msg = 'Missing required fields: channel, account, or message'
                print(f"[SEND_MESSAGE] ERROR: {error_msg}")
                await self.send(text_data=json.dumps({
                    'type': 'KICK_ERROR',
                    'message': error_msg
                }))
                return
            
            # Получаем аккаунт из базы данных асинхронно
            account = await self.get_account_by_login(account_login)
            if not account:
                error_msg = f'Account {account_login} not found'
                print(f"[SEND_MESSAGE] ERROR: {error_msg}")
                await self.send(text_data=json.dumps({
                    'type': 'KICK_ERROR',
                    'message': error_msg
                }))
                return
            
            # Получаем данные аккаунта асинхронно
            account_data = await self.get_account_data(account)
            token = account_data['token'] or ""
            session_token = account_data['session_token'] or ""
            proxy_url = account_data['proxy_url']
            
            print(f"[SEND_MESSAGE] Sending message from {account_login} to {channel}: {message_text}")
            print(f"[SEND_MESSAGE] Token available: {bool(token)}")
            print(f"[SEND_MESSAGE] Session token available: {bool(session_token)}")
            print(f"[SEND_MESSAGE] Proxy URL: {proxy_url}")

            # Проверяем обязательные поля
            if not session_token:
                error_msg = f'No session_token for account {account_login}'
                print(f"[SEND_MESSAGE] ERROR: {error_msg}")
                await self.send(text_data=json.dumps({
                    'type': 'KICK_ERROR',
                    'message': error_msg
                }))
                return

            # Проверяем прокси - ОБЯЗАТЕЛЬНО
            if not proxy_url:
                error_msg = f'No proxy assigned to account {account_login}'
                print(f"[SEND_MESSAGE] ERROR: {error_msg}")
                await self.send(text_data=json.dumps({
                    'type': 'KICK_ERROR',
                    'message': error_msg
                }))
                return

            # Отправляем сообщение через cloudscraper
            success = await send_kick_message_cloudscraper(
                chatbot_id=account.id,
                channel=channel,
                message=message_text,
                token=token,
                session_token=session_token,
                proxy_url=proxy_url
            )
            
            if success:
                success_msg = f'✅ Message sent successfully from {account_login} to {channel}: "{message_text}"'
                print(f"[SEND_MESSAGE] {success_msg}")
                await self.send(text_data=json.dumps({
                    'type': 'KICK_MESSAGE_SENT',
                    'message': success_msg,
                    'account': account_login,
                    'channel': channel,
                    'text': message_text
                }))
            else:
                error_msg = f'❌ Failed to send message from {account_login} to {channel}: "{message_text}"'
                print(f"[SEND_MESSAGE] {error_msg}")
                await self.send(text_data=json.dumps({
                    'type': 'KICK_ERROR',
                    'message': error_msg,
                    'account': account_login,
                    'channel': channel,
                    'text': message_text
                }))
        except Exception as e:
            print(f"[SEND_MESSAGE] Exception: {e}")
            await self.send(text_data=json.dumps({
                'type': 'KICK_ERROR',
                'message': f'Exception: {str(e)}'
            }))

    @database_sync_to_async
    def get_account_by_login(self, login):
        """Get account by login from database"""
        try:
            return KickAccount.objects.filter(login=login, status='active').first()
        except Exception as e:
            print(f"[get_account_by_login] Error: {e}")
            return None

    @database_sync_to_async
    def get_account_data(self, account):
        """Get account data including proxy info"""
        try:
            data = {
                'token': account.token,
                'session_token': account.session_token,
                'proxy_url': str(account.proxy.url) if account.proxy else None
            }
            return data
        except Exception as e:
            print(f"[get_account_data] Error: {e}")
            return {
                'token': None,
                'session_token': None,
                'proxy_url': None
            }

    async def ping_accounts(self):
        """Получить и отправить список аккаунтов клиенту"""
        try:
            # Получаем аккаунты асинхронно
            accounts = await self.get_active_accounts()
            
            accounts_data = []
            for account in accounts:
                account_data = await self.get_account_data(account)
                accounts_data.append({
                    'id': account.id,
                    'login': account.login,
                    'status': 'active' if account.status == 'active' else 'inactive'
                })

            print(f"[KICK-WS] SEND ACCOUNTS: {accounts_data}")
            await self.send(text_data=json.dumps({
                'event': 'KICK_ACCOUNTS',
                'message': accounts_data
            }))
        except Exception as e:
            print(f"[ping_accounts] Error: {e}")
            await self.send(text_data=json.dumps({
                'type': 'KICK_ERROR',
                'message': f'Error loading accounts: {str(e)}'
            }))

    @database_sync_to_async
    def get_active_accounts(self):
        """Get active accounts from database"""
        try:
            return list(KickAccount.objects.filter(status='active'))
        except Exception as e:
            print(f"[get_active_accounts] Error: {e}")
            return []

    async def select_channel(self, channel: str):
        # Получаем аккаунты асинхронно для выбранного канала
        await self.ping_accounts()

class KickAppStatsWs(AsyncWebsocketConsumer):
    async def connect(self):
        await self.accept()
        
    async def disconnect(self, code):
        pass
        
    async def receive(self, text_data=None, bytes_data=None):
        pass
