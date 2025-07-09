import asyncio
import json
import httpx
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from asgiref.sync import sync_to_async
from django.db import models
from KickApp.models import KickAccount
from ProxyApp.models import Proxy
from .playwright_utils import KickPlaywrightClient, send_kick_message_phoenix_ws
import requests


async def send_kick_message(chatbot_id: int, channel: str, message: str, token: str, proxy_url: str = "", session_token: str = None, storage_state_path: str = None):
    """
    Отправляет сообщение в чат Kick.com
    Использует Phoenix WebSocket (storage_state) в первую очередь, затем Playwright (DOM), затем httpx
    """
    print(f"[SEND_MESSAGE] Starting message send from account {chatbot_id} to channel {channel}")
    print(f"[SEND_MESSAGE] Message: {message}")
    print(f"[SEND_MESSAGE] Has token: {bool(token)}")
    print(f"[SEND_MESSAGE] Has session_token: {bool(session_token)}")
    print(f"[SEND_MESSAGE] Proxy URL: {proxy_url}")
    print(f"[SEND_MESSAGE] Storage state: {storage_state_path}")
    
    # Преобразуем SOCKS5 прокси в HTTP для Playwright или отключаем его
    playwright_proxy_url = None
    if proxy_url:
        if proxy_url.startswith('socks5://'):
            print(f"[SEND_MESSAGE] WARNING: SOCKS5 proxy detected ({proxy_url}), Playwright will run without proxy")
            playwright_proxy_url = None
        elif proxy_url.startswith('http://') or proxy_url.startswith('https://'):
            playwright_proxy_url = proxy_url
        else:
            print(f"[SEND_MESSAGE] WARNING: Unknown proxy format ({proxy_url}), Playwright will run without proxy")
            playwright_proxy_url = None
    
    # 1. Пробуем Phoenix WebSocket (storage_state)
    try:
        print(f"[SEND_MESSAGE] Attempting Phoenix WebSocket method for account {chatbot_id}")
        if storage_state_path and isinstance(storage_state_path, str):
            success = await send_kick_message_phoenix_ws(
                channel=channel,
                message=message,
                storage_state_path=storage_state_path,
                proxy_url=playwright_proxy_url if playwright_proxy_url else ""
            )
            if success:
                print(f"[SEND_MESSAGE] ✅ SUCCESS: Message sent via Phoenix WS from account {chatbot_id} to {channel}")
                return True
            else:
                print(f"[SEND_MESSAGE] ❌ FAILED: Phoenix WS method failed for account {chatbot_id}")
        else:
            print(f"[SEND_MESSAGE] No storage_state_path provided, skipping Phoenix WS method")
    except Exception as e:
        print(f"[SEND_MESSAGE] ❌ ERROR: Phoenix WS method error for account {chatbot_id}: {e}")
        import traceback
        traceback.print_exc()
    
    # 2. Пробуем Playwright (DOM)
    try:
        print(f"[SEND_MESSAGE] Attempting Playwright DOM method for account {chatbot_id}")
        playwright_client = KickPlaywrightClient(headless=True, timeout=30000)
        success = await playwright_client.send_message(
            channel=channel,
            message=message,
            token=token,
            session_token=session_token,
            proxy_url=playwright_proxy_url
        )
        if success:
            print(f"[SEND_MESSAGE] ✅ SUCCESS: Message sent via Playwright DOM from account {chatbot_id} to {channel}")
            return True
        else:
            print(f"[SEND_MESSAGE] ❌ FAILED: Playwright DOM method failed for account {chatbot_id}")
    except Exception as e:
        print(f"[SEND_MESSAGE] ❌ ERROR: Playwright DOM method error for account {chatbot_id}: {e}")
        import traceback
        traceback.print_exc()
    
    # 3. Fallback на httpx если Playwright не сработал
    try:
        print(f"[SEND_MESSAGE] Attempting httpx fallback method for account {chatbot_id}")
        proxy_url_str = proxy_url if proxy_url else ""
        success = await send_kick_message_httpx(chatbot_id, channel, message, token, proxy_url_str)
        if success:
            print(f"[SEND_MESSAGE] ✅ SUCCESS: Message sent via httpx fallback from account {chatbot_id} to {channel}")
            return True
        else:
            print(f"[SEND_MESSAGE] ❌ FAILED: httpx fallback method failed for account {chatbot_id}")
    except Exception as e:
        print(f"[SEND_MESSAGE] ❌ ERROR: httpx fallback method error for account {chatbot_id}: {e}")
        import traceback
        traceback.print_exc()
    
    print(f"[SEND_MESSAGE] ❌ FINAL FAILURE: All methods failed for account {chatbot_id} to {channel}")
    return False


async def send_kick_message_httpx(chatbot_id: int, channel: str, message: str, token: str, proxy_url: str = None):
    """Fallback method: Sends a message to a Kick chat using httpx (may not work due to Cloudflare)."""
    proxies = None
    if proxy_url:
        proxy_url = str(proxy_url)
        proxies = {
            "http://": proxy_url,
            "https://": proxy_url,
        }
    
    async with httpx.AsyncClient(proxies=proxies, timeout=30.0) as client:
        try:
            # 1. Получаем информацию о канале и chatroom_id
            channel_api_url = f"https://kick.com/api/v2/channels/{channel}"
            headers = {
                'Authorization': f'Bearer {token}',
                'Content-Type': 'application/json',
                'Accept': 'application/json',
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            }
            
            response = await client.get(channel_api_url, headers=headers)
            response.raise_for_status()
            channel_data = response.json()
            
            chatroom_id = channel_data.get("chatroom", {}).get("id")
            if not chatroom_id:
                print(f"Could not find chatroom ID for channel: {channel}")
                return False

            # 2. Отправляем сообщение используя правильный API эндпоинт
            # Пробуем сначала новый API v2
            send_message_url = f"https://kick.com/api/v2/messages/send/{chatroom_id}"
            payload = {
                'content': message,
                'type': 'message'
            }
            
            try:
                response = await client.post(send_message_url, headers=headers, json=payload)
                response.raise_for_status()
                print(f"Message sent successfully from account {chatbot_id} to {channel} via httpx (API v2)")
                return True
            except httpx.HTTPStatusError as e:
                print(f"API v2 failed: {e.response.status_code} - {e.response.text}")
                # Fallback на старый API v1
                send_message_url = f"https://kick.com/api/v1/chat-messages"
                payload = {
                    'chatroom_id': chatroom_id,
                    'message': message,
                    'type': 'message'
                }
                
                response = await client.post(send_message_url, headers=headers, json=payload)
                response.raise_for_status()
                print(f"Message sent successfully from account {chatbot_id} to {channel} via httpx (API v1)")
                return True

        except httpx.HTTPStatusError as e:
            error_text = ""
            try:
                error_text = e.response.text
            except:
                error_text = str(e)
            print(f"HTTP error sending message from {chatbot_id} to {channel}: {e.response.status_code} - {error_text}")
            return False
        except Exception as e:
            print(f"An error occurred sending message from {chatbot_id} to {channel}: {e}")
            return False


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
            # Проверяем валидность каждого аккаунта (асинхронно через sync_to_async)
            checked_accounts = []
            for acc in accounts:
                is_valid = await sync_to_async(acc.check_kick_account_valid)()
                checked_accounts.append({
                    'id': acc.id,
                    'login': acc.login,
                    'status': acc.status
                })
            print('[KICK-WS] SEND ACCOUNTS:', checked_accounts)
            await self.send(text_data=json.dumps({
                'event': 'KICK_ACCOUNTS',
                'message': checked_accounts
            }))

        elif _type == 'KICK_START_WORK':
            if self.work_task and not self.work_task.done():
                print("Work is already in progress.")
                return

            channel = self.channel_group_name or 'default'
            print(f"Work started for channel {channel}. Ready to send messages.")
            
            await self.send(text_data=json.dumps({
                'type': 'KICK_WORK_READY',
                'message': f'Work mode activated for channel {channel}. Ready to send messages.'
            }))

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
            storage_state_path = message_data.get('storage_state_path')
            
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
            token = account_data['token']
            session_token = account_data['session_token']
            proxy_url = account_data['proxy_url'] if account_data['proxy_url'] else ""
            # storage_state_path можно хранить в account_data, если есть
            if not storage_state_path:
                storage_state_path = account_data.get('storage_state_path')
            
            print(f"[SEND_MESSAGE] Sending message from {account_login} to {channel}: {message_text}")
            print(f"[SEND_MESSAGE] Token available: {bool(token)}")
            print(f"[SEND_MESSAGE] Session token available: {bool(session_token)}")
            print(f"[SEND_MESSAGE] Proxy URL: {proxy_url}")
            print(f"[SEND_MESSAGE] Storage state: {storage_state_path}")
            
            # Отправляем сообщение
            success = await send_kick_message(
                chatbot_id=account.id,
                channel=channel,
                message=message_text,
                token=token,
                proxy_url=proxy_url,
                session_token=session_token,
                storage_state_path=storage_state_path if storage_state_path else ""
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
            error_msg = f"❌ Exception sending message: {str(e)}"
            print(f"[SEND_MESSAGE] {error_msg}")
            import traceback
            traceback.print_exc()
            await self.send(text_data=json.dumps({
                'type': 'KICK_ERROR',
                'message': error_msg
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
            if hasattr(account, 'storage_state_path') and account.storage_state_path:
                data['storage_state_path'] = account.storage_state_path
            else:
                data['storage_state_path'] = None
            return data
        except Exception as e:
            print(f"[get_account_data] Error: {e}")
            return {
                'token': None,
                'session_token': None,
                'proxy_url': None,
                'storage_state_path': None
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
