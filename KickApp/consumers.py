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
    
    # Поддержка HTTP прокси для cloudscraper
    proxy_config = None
    if proxy_url:
        if proxy_url.startswith("socks5://"):
            # Конвертируем SOCKS5 в HTTP для cloudscraper
            try:
                # Извлекаем данные из SOCKS5 URL: socks5://user:pass@host:port
                proxy_parts = proxy_url.replace("socks5://", "").split("@")
                if len(proxy_parts) == 2:
                    auth, server = proxy_parts
                    username, password = auth.split(":")
                    host, port = server.split(":")
                    
                    # Создаем HTTP прокси конфигурацию
                    proxy_config = {
                        'http': f"http://{username}:{password}@{host}:{port}",
                        'https': f"http://{username}:{password}@{host}:{port}"
                    }
                    logger.info(f"[SEND_MESSAGE] Converted SOCKS5 to HTTP proxy: {host}:{port}")
                else:
                    logger.warning(f"[SEND_MESSAGE] Invalid SOCKS5 proxy format: {proxy_url}")
            except Exception as e:
                logger.error(f"[SEND_MESSAGE] Error converting SOCKS5 proxy: {e}")
        elif proxy_url.startswith("http://") or proxy_url.startswith("https://"):
            # Уже HTTP прокси
            proxy_config = {
                'http': proxy_url,
                'https': proxy_url
            }
            logger.info(f"[SEND_MESSAGE] Using HTTP proxy: {proxy_url}")
        else:
            # Пробуем парсить как host:port:user:pass формат
            try:
                parts = proxy_url.split(':')
                if len(parts) == 4:
                    host, port, username, password = parts
                    http_proxy = f"http://{username}:{password}@{host}:{port}"
                    proxy_config = {
                        'http': http_proxy,
                        'https': http_proxy
                    }
                    logger.info(f"[SEND_MESSAGE] Parsed proxy format: {host}:{port}")
                else:
                    logger.warning(f"[SEND_MESSAGE] Unknown proxy format: {proxy_url}")
            except Exception as e:
                logger.error(f"[SEND_MESSAGE] Error parsing proxy: {e}")
    
    # ИСПРАВЛЕНИЕ: Используем token вместо session_token для формирования куков
    # token содержит формат USERID|TOKEN, который нужен для куков
    # session_token зашифрован в формате Laravel и не подходит для прямого использования
    if not token or '|' not in token:
        logger.error("[SEND_MESSAGE] No valid token provided (should be in format USERID|TOKEN)")
        return "Invalid token format"
    
    # Извлекаем данные из token (формат: USERID|TOKEN)
    user_id, token_part = token.split('|', 1)
    session_raw = token  # Используем весь token как session_token
    xsrf_token = token_part  # XSRF-TOKEN это вторая часть после |
    
    # Декодируем session_token для Bearer токена (как в оригинальном скрипте)
    session_decoded = urllib.parse.unquote(session_raw)
    
    # Формируем cookie строку
    cookie_parts = []
    cookie_parts.append(f"session_token={session_raw}")
    cookie_parts.append(f"XSRF-TOKEN={xsrf_token}")
    
    cookie_string = "; ".join(cookie_parts)
    
    logger.debug(f"[SEND_MESSAGE] SESSION_RAW: {session_raw}")
    logger.debug(f"[SEND_MESSAGE] XSRF_TOKEN: {xsrf_token}")
    logger.debug(f"[SEND_MESSAGE] SESSION_DECODED: {session_decoded}")
    logger.debug(f"[SEND_MESSAGE] Cookie string: {cookie_string}")
    
    # Парсим куки
    cookies = {}
    for cookie in cookie_string.split(';'):
        if '=' in cookie:
            name, value = cookie.strip().split('=', 1)
            cookies[name] = value
    
    # Создаем scraper с прокси если настроен
    scraper = cloudscraper.create_scraper()
    if proxy_config:
        logger.info(f"[SEND_MESSAGE] Setting proxy config: {proxy_config}")
        scraper.proxies = proxy_config
    
    # Получаем информацию о канале
    logger.info(f"[SEND_MESSAGE] Getting channel info for: {channel}")
    try:
        # URL-кодируем название канала для поддержки кириллицы
        encoded_channel = urllib.parse.quote(channel)
        
        channel_response = scraper.get(
            f"https://kick.com/api/v2/channels/{encoded_channel}",
            cookies=cookies,
            headers={
                'Authorization': f'Bearer {session_decoded}',
                'X-XSRF-TOKEN': xsrf_token,
                'X-Requested-With': 'XMLHttpRequest',
                'Content-Type': 'application/json',
                'Accept': 'application/json',
                'Referer': f'https://kick.com/{encoded_channel}',
                'cluster': 'v2'
            }
        )
        logger.debug(f"[SEND_MESSAGE] GET https://kick.com/api/v2/channels/{channel} status={channel_response.status_code}")
        
        if channel_response.status_code != 200:
            logger.error(f"[SEND_MESSAGE] Channel lookup failed: {channel_response.status_code} {channel_response.text}")
            return f"Channel lookup failed: HTTP {channel_response.status_code}"
        
        channel_data = channel_response.json()
        chatroom_id = channel_data.get('chatroom', {}).get('id')
        
        if not chatroom_id:
            logger.error(f"[SEND_MESSAGE] No chatroom_id found in response: {channel_data}")
            return "No chatroom_id found in response"
        
        logger.info(f"[SEND_MESSAGE] Got chatroom_id: {chatroom_id}")
        
        # Отправляем сообщение
        message_ref = str(int(time.time() * 1000))
        payload = {
            'content': message,
            'type': 'message',
            'message_ref': message_ref
        }
        
        logger.debug(f"[SEND_MESSAGE] Sending POST to: https://kick.com/api/v2/messages/send/{chatroom_id}")
        logger.debug(f"[SEND_MESSAGE] Headers: {dict(scraper.headers)}")
        logger.debug(f"[SEND_MESSAGE] Payload: {payload}")
        
        response = scraper.post(
            f"https://kick.com/api/v2/messages/send/{chatroom_id}",
            cookies=cookies,
            headers={
                'Authorization': f'Bearer {session_decoded}',
                'X-XSRF-TOKEN': xsrf_token,
                'X-Requested-With': 'XMLHttpRequest',
                'Content-Type': 'application/json',
                'Accept': 'application/json',
                'Referer': f'https://kick.com/{channel}',
                'cluster': 'v2'
            },
            json=payload
        )
        
        logger.debug(f"[SEND_MESSAGE] POST https://kick.com/api/v2/messages/send/{chatroom_id} status={response.status_code}")
        logger.debug(f"[SEND_MESSAGE] Response content: {response.text}")
        
        if response.status_code == 200:
            logger.info(f"[SEND_MESSAGE] ✓ sent: {message}")
            return True
        else:
            logger.error(f"[SEND_MESSAGE] ❌ failed: {response.status_code}")
            logger.error(f"[SEND_MESSAGE] {response.text}")
            
            # Парсим ответ от Kick.com для показа пользователю
            try:
                error_data = response.json()
                error_message = error_data.get('status', {}).get('message', 'Unknown error')
                logger.error(f"[SEND_MESSAGE] Kick.com error: {error_message}")
                # Возвращаем ошибку с текстом для показа в алерте
                return f"Kick.com error: {error_message}"
            except:
                logger.error(f"[SEND_MESSAGE] Failed to parse error response")
                return f"HTTP {response.status_code}: {response.text[:100]}"
            
    except Exception as e:
        logger.error(f"[SEND_MESSAGE] Exception: {e}")
        return f"Proxy error: {str(e)}"


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
            # Загружаем все аккаунты без проверки
            accounts = await sync_to_async(list)(KickAccount.objects.all())
            for acc in accounts:
                account_status = {
                    'id': acc.id,
                    'login': acc.login,
                    'status': acc.status  # Используем текущий статус из БД
                }
                await self.send(text_data=json.dumps({
                    'event': 'KICK_ACCOUNT_STATUS',
                    'message': account_status
                }))

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
            result = await send_kick_message_cloudscraper(
                chatbot_id=account.id,
                channel=channel,
                message=message_text,
                token=token,
                session_token=session_token,
                proxy_url=proxy_url
            )
            
            if result is True:
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
                # result содержит текст ошибки
                error_msg = f'❌ Failed to send message from {account_login} to {channel}: {result}'
                print(f"[SEND_MESSAGE] {error_msg}")
                
                # Анализируем ошибку и обновляем статус аккаунта/прокси
                await self.handle_send_error(account, result, proxy_url)
                
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
    def handle_send_error(self, account, error_message, proxy_url):
        """Обрабатывает ошибки отправки и обновляет статусы аккаунтов/прокси"""
        try:
            print(f"[handle_send_error] Analyzing error for account {account.login}: {error_message}")
            
            # Преобразуем error_message в строку если это не строка
            if not isinstance(error_message, str):
                error_message = str(error_message)
            
            # Проверяем тип ошибки
            if "502" in error_message or "bad gateway" in error_message.lower() or "tunnel connection failed" in error_message.lower():
                # Ошибка прокси - помечаем прокси как невалидный
                if account.proxy:
                    account.proxy.status = 'invalid'
                    account.proxy.save()
                    print(f"[handle_send_error] Marked proxy {account.proxy.url} as invalid due to 502 error")
                # Аккаунт остается активным
                
            elif "proxy" in error_message.lower() or "connection" in error_message.lower():
                # Ошибка прокси - помечаем прокси как невалидный
                if account.proxy:
                    account.proxy.status = 'invalid'
                    account.proxy.save()
                    print(f"[handle_send_error] Marked proxy {account.proxy.url} as invalid")
                # Аккаунт остается активным
                
            elif "banned" in error_message.lower() or "blocked" in error_message.lower():
                # Бан - это нормально, аккаунт остается активным
                print(f"[handle_send_error] Account {account.login} is banned, keeping active status")
                
            elif "security policy" in error_message.lower():
                # Критическая ошибка - помечаем аккаунт как неактивный
                account.status = 'inactive'
                account.save()
                print(f"[handle_send_error] Marked account {account.login} as inactive due to security policy")
                
            else:
                # Другие ошибки - помечаем аккаунт как неактивный
                account.status = 'inactive'
                account.save()
                print(f"[handle_send_error] Marked account {account.login} as inactive due to unknown error")
                
        except Exception as e:
            print(f"[handle_send_error] Exception: {e}")

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
