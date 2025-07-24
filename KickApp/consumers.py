import asyncio
import json
import httpx
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from asgiref.sync import sync_to_async
from django.db import models
from KickApp.models import KickAccount
from ProxyApp.models import Proxy
from StatsApp.shift_manager import get_shift_manager, cleanup_shift_manager
from KickApp.process_message_manager import process_message_manager
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
        self.shift_manager = None
        self.user = None

    @database_sync_to_async
    def get_user_from_scope(self):
        """Получить пользователя из scope"""
        return self.scope.get('user')

    async def connect(self):
        await self.accept()
        # Получаем пользователя и инициализируем менеджер смен
        self.user = await self.get_user_from_scope()
        print(f"[CONNECT] User: {self.user}")
        print(f"[CONNECT] User authenticated: {self.user.is_authenticated if self.user else False}")
        
        if self.user and self.user.is_authenticated:
            self.shift_manager = await sync_to_async(get_shift_manager)(self.user)
            print(f"[CONNECT] Shift manager created: {self.shift_manager is not None}")
            
            # Инициализируем менеджер процессов сообщений если еще не инициализирован
            if not hasattr(process_message_manager, '_initialized'):
                try:
                    await process_message_manager.initialize()
                    process_message_manager._initialized = True
                    print(f"[CONNECT] Process message manager initialized")
                except Exception as e:
                    print(f"[CONNECT] Failed to initialize process message manager: {e}")
        else:
            print(f"[CONNECT] Cannot create shift manager: user={self.user}, authenticated={self.user.is_authenticated if self.user else False}")

    async def disconnect(self, close_code):
        print(f"[DISCONNECT] User {self.user.username if self.user else 'Anonymous'} disconnected with code {close_code}")
        
        # Отменяем задачу работы если она активна
        if self.work_task and not self.work_task.done():
            print("[DISCONNECT] Cancelling work task")
            self.work_task.cancel()
            try:
                await self.work_task
            except asyncio.CancelledError:
                print("[DISCONNECT] Work task cancelled successfully")
        
        # Завершаем смену при отключении
        if self.shift_manager and self.user:
            await sync_to_async(self.shift_manager.end_shift)()
            await sync_to_async(cleanup_shift_manager)(self.user.id)
        
        # Отключаемся от группы канала
        if self.channel_group_name and self.channel_layer is not None:
            await self.channel_layer.group_discard(
                self.channel_group_name,
                self.channel_name
            )

    async def start_shift(self):
        """Начать смену"""
        if self.shift_manager and self.user:
            shift = await sync_to_async(self.shift_manager.start_shift)()
            await self.send(text_data=json.dumps({
                'event': 'SHIFT_STARTED',
                'message': {
                    'shift_id': shift.id,
                    'start_time': shift.start_time.isoformat()
                }
            }))
            return shift
        return None

    async def end_shift(self):
        """Завершить смену"""
        if self.shift_manager and self.user:
            success = await sync_to_async(self.shift_manager.end_shift)()
            if success:
                await self.send(text_data=json.dumps({
                    'event': 'SHIFT_ENDED',
                    'message': {'status': 'success'}
                }))
            return success
        return False

    async def log_message_to_shift(self, channel: str, account: str, message_type: str, message: str):
        """Записать сообщение в лог смены"""
        print(f"[LOG_MESSAGE] Attempting to log: channel={channel}, account={account}, type={message_type}, message={message}")
        print(f"[LOG_MESSAGE] shift_manager exists: {self.shift_manager is not None}")
        print(f"[LOG_MESSAGE] user exists: {self.user is not None}")
        print(f"[LOG_MESSAGE] user authenticated: {self.user.is_authenticated if self.user else False}")
        
        if self.shift_manager and self.user:
            # Проверяем таймауты
            await sync_to_async(self.shift_manager.check_timeout)()
            
            # Логируем сообщение
            success = await sync_to_async(self.shift_manager.log_message)(
                channel, account, message_type, message
            )
            print(f"[LOG_MESSAGE] Logging result: {success}")
            return success
        else:
            print(f"[LOG_MESSAGE] Cannot log: shift_manager={self.shift_manager}, user={self.user}")
        return False

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
            
            # Логируем выбор канала
            if self.shift_manager and self.user:
                await sync_to_async(self.shift_manager.log_action)(
                    'channel_select', 
                    f'Выбран канал: {channel_name}',
                    {'channel': channel_name}
                )
            
            # Сбрасываем статус всех аккаунтов для нового сеанса
            # Аккаунты помечаются как активные только для текущего сеанса
            accounts = await sync_to_async(list)(KickAccount.objects.all())
            for acc in accounts:
                # Для нового сеанса все аккаунты активны (кроме тех что помечены как неактивные в БД)
                account_status = {
                    'id': acc.id,
                    'login': acc.login,
                    'status': 'active' if acc.status == 'active' else acc.status  # Используем статус из БД
                }
                await self.send(text_data=json.dumps({
                    'event': 'KICK_ACCOUNT_STATUS',
                    'message': account_status
                }))
            
            print(f"[KICK-WS] Channel changed to {channel_name}, all accounts reset for new session")

        elif _type == 'KICK_START_WORK':
            if self.work_task and not self.work_task.done():
                print("Work is already in progress.")
                return

            channel = self.channel_group_name or 'default'
            print(f"Work started for channel {channel}. Ready to send messages.")
            
            # Логируем начало работы
            if self.shift_manager and self.user:
                await sync_to_async(self.shift_manager.log_action)(
                    'work_start', 
                    f'Начало работы в канале: {channel}',
                    {'channel': channel, 'message': json_data.get('message', 'Hello from the bot!')}
                )
            
            # Сразу запускаем работу, не ждем загрузки всех аккаунтов
            self.work_task = asyncio.create_task(self.start_work(json_data.get('message', 'Hello from the bot!'), 1))

        elif _type == 'KICK_SEND_MESSAGE':
            # Обработка отправки одиночного сообщения
            await self.handle_send_message(json_data.get('message', {}))

        elif _type == 'KICK_END_WORK':
            await self.end_work()
        
        elif _type == 'KICK_LOGOUT':
            # Пользователь выходит из системы
            print(f"[LOGOUT] User {self.user.username if self.user else 'Anonymous'} is logging out")
            await self.end_work()
            # Закрываем соединение
            await self.close()
        elif _type == 'KICK_LOG_ACTION':
            await self.handle_log_action(json_data)

    async def handle_log_action(self, data):
        """Handle KICK_LOG_ACTION event"""
        try:
            action_type = data.get('action_type')
            description = data.get('description')
            details = data.get('details', {})
            
            if not all([action_type, description]):
                print(f"[LOG_ACTION] Missing required fields: action_type or description")
                return
            
            # Логируем действие в смену
            if self.shift_manager and self.user:
                await sync_to_async(self.shift_manager.log_action)(
                    action_type, 
                    description,
                    details
                )
                print(f"[LOG_ACTION] Logged action: {action_type} - {description}")
            
        except Exception as e:
            print(f"[LOG_ACTION] Error logging action: {e}")

    async def start_work(self, message: str, frequency: int):
        if not self.channel_group_name:
            print('No channel selected for work')
            return

        print(f'Starting work for channel: {self.channel_group_name}')
        
        # Начинаем смену
        shift = await self.start_shift()
        
        # Отправляем событие о начале работы
        import time
        await self.send(text_data=json.dumps({
            'event': 'KICK_START_WORK',
            'message': {
                'startWorkTime': time.time() * 1000,  # время в миллисекундах
                'shift_id': shift.id if shift else None
            }
        }))
        
        # Запускаем периодическую проверку таймаутов
        timeout_check_task = asyncio.create_task(self.check_timeouts_periodically())
        
        # Ждем отмены задачи (когда пользователь нажмет "End Work" или перезагрузит страницу)
        try:
            while True:
                await asyncio.sleep(1)  # Просто ждем, не отправляем сообщения автоматически
        except asyncio.CancelledError:
            print("Work task was cancelled.")
            timeout_check_task.cancel()  # Отменяем проверку таймаутов
            
            # Отменяем все активные запросы при отмене задачи
            try:
                if hasattr(process_message_manager, 'cancel_all_requests'):
                    await process_message_manager.cancel_all_requests()
                    print("Cancelled all active processes due to work task cancellation")
            except Exception as e:
                print(f"Error cancelling processes: {e}")
            
            # Завершаем смену при отмене задачи
            await self.end_shift()
            return
    
    async def check_timeouts_periodically(self):
        """Периодически проверять таймауты"""
        while True:
            try:
                await asyncio.sleep(30)  # Проверяем каждые 30 секунд
                if self.shift_manager and self.user:
                    await sync_to_async(self.shift_manager.check_timeout)()
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Error checking timeouts: {e}")
                break

    async def end_work(self):
        """Stop work task and cancel all active requests"""
        print("[END_WORK] Starting work termination...")
        
        # Отменяем задачу работы
        if self.work_task:
            self.work_task.cancel()
            self.work_task = None
            print("[END_WORK] Work task cancelled")
        
        try:
            # Отменяем все активные запросы
            if hasattr(process_message_manager, 'cancel_all_requests'):
                await process_message_manager.cancel_all_requests()
                print("[END_WORK] Cancelled all active processes")
                
                # Ждем завершения всех процессов (максимум 5 секунд)
                import time
                start_time = time.time()
                while time.time() - start_time < 5:
                    stats = process_message_manager.get_stats()
                    if stats['active_requests'] == 0:
                        print("[END_WORK] All processes completed")
                        break
                    await asyncio.sleep(0.1)
                else:
                    print("[END_WORK] Some processes may still be running")
                    
        except Exception as e:
            print(f"[END_WORK] Error cancelling processes: {e}")
        
        # Логируем остановку работы
        if self.shift_manager and self.user:
            await sync_to_async(self.shift_manager.log_action)(
                'work_stop', 
                'Остановка работы',
                {'channel': self.channel_group_name}
            )
        
        # Завершаем смену
        await self.end_shift()
        
        # Отправляем событие завершения работы
        await self.send(text_data=json.dumps({
            'event': 'KICK_END_WORK',
            'message': 'Work stopped'
        }))
        
        print("[END_WORK] Work termination completed")

    async def handle_send_message(self, message_data):
        """Handle KICK_SEND_MESSAGE event with async manager"""
        try:
            print(f"[SEND_MESSAGE] Received message data: {message_data}")
            
            # Проверяем, не остановлена ли работа
            if not hasattr(self, 'work_task') or not self.work_task or self.work_task.done():
                print(f"[SEND_MESSAGE] Work not active, rejecting message from {message_data.get('account', 'unknown')}")
                await self.send(text_data=json.dumps({
                    'type': 'KICK_ERROR',
                    'message': 'Work is not active. Please start work first.',
                    'account': message_data.get('account', 'unknown'),
                    'channel': message_data.get('channel', 'unknown'),
                    'text': message_data.get('message', '')
                }))
                return
            
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

            # Создаем уникальный ID для запроса
            request_id = f"{account_login}_{channel}_{int(time.time() * 1000)}"
            
            # Определяем тип сообщения (авто или ручное)
            message_type = 'a' if message_data.get('auto', False) else 'm'
            
            # Логируем попытку отправки сообщения
            await self.log_message_to_shift(channel, account_login, message_type, message_text)
            
            # Отправляем сообщение через асинхронный менеджер
            async def message_callback(request):
                """Callback для обработки результата отправки"""
                if request.status.value == 'success':
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
                    error_msg = f'❌ Failed to send message from {account_login} to {channel}: {request.error}'
                    print(f"[SEND_MESSAGE] {error_msg}")
                    
                    # Логируем ошибку отправки
                    await self.log_message_to_shift(channel, account_login, 'e', f"ERROR: {request.error}")
                    
                    # Анализируем ошибку и обновляем статус аккаунта/прокси
                    status_for_session = await self.handle_send_error(account, request.error, proxy_url)
                    
                    # Отправляем событие о смене статуса аккаунта только если это не channel_restriction
                    if status_for_session != "channel_restriction":
                        await self.send(text_data=json.dumps({
                            'type': 'KICK_ACCOUNT_STATUS',
                            'message': {
                                'id': account.id,
                                'login': account.login,
                                'status': 'inactive'
                            }
                        }))
                    
                    await self.send(text_data=json.dumps({
                        'type': 'KICK_ERROR',
                        'message': error_msg,
                        'account': account_login,
                        'channel': channel,
                        'text': message_text
                    }))
            
            # Проверяем, не отменена ли работа
            if hasattr(self, 'work_task') and self.work_task and self.work_task.cancelled():
                print(f"[SEND_MESSAGE] Work cancelled, skipping message from {account_login}")
                return
            
            # Запускаем отправку через менеджер процессов
            await process_message_manager.send_message_async(
                request_id=request_id,
                channel=channel,
                account=account_login,
                message=message_text,
                token=token,
                session_token=session_token,
                proxy_url=proxy_url,
                callback=message_callback
            )
            
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
            if "502" in error_message or "500" in error_message or "bad gateway" in error_message.lower() or "tunnel connection failed" in error_message.lower():
                # Ошибка прокси - помечаем прокси как неактивный в БД
                if account.proxy:
                    account.proxy.status = False  # Boolean False для неактивного прокси
                    account.proxy.save()
                    print(f"[handle_send_error] Marked proxy {account.proxy.url} as inactive in DB due to proxy error")
                # Аккаунт помечается крестиком только на текущий сеанс (не в БД)
                print(f"[handle_send_error] Account {account.login} marked as inactive for current session due to proxy error")
                return "session_inactive"  # Возвращаем статус для пометки на сеанс
                
            elif "proxy" in error_message.lower() or "connection" in error_message.lower():
                # Ошибка прокси - помечаем прокси как неактивный в БД
                if account.proxy:
                    account.proxy.status = False  # Boolean False для неактивного прокси
                    account.proxy.save()
                    print(f"[handle_send_error] Marked proxy {account.proxy.url} as inactive in DB")
                # Аккаунт помечается крестиком только на текущий сеанс (не в БД)
                print(f"[handle_send_error] Account {account.login} marked as inactive for current session due to proxy error")
                return "session_inactive"  # Возвращаем статус для пометки на сеанс
                
            elif "banned" in error_message.lower() or "blocked" in error_message.lower() or "BANNED_ERROR" in error_message:
                # Бан - аккаунт помечается крестиком только на текущий сеанс (не в БД)
                print(f"[handle_send_error] Account {account.login} is banned, marked as inactive for current session")
                return "session_inactive"  # Возвращаем статус для пометки на сеанс
                
            elif "followers only" in error_message.lower() or "FOLLOWERS_ONLY_ERROR" in error_message:
                # Ошибка followers only - это не проблема аккаунта, а канала
                # Не помечаем аккаунт как неактивный, просто логируем
                print(f"[handle_send_error] Channel requires followers only for account {account.login}")
                return "channel_restriction"  # Возвращаем специальный статус
                
            elif "security policy" in error_message.lower():
                # Критическая ошибка - помечаем аккаунт как неактивный в БД
                account.status = 'inactive'
                account.save()
                print(f"[handle_send_error] Marked account {account.login} as inactive in DB due to security policy")
                return "db_inactive"  # Возвращаем статус для пометки в БД
                
            elif "invalid token" in error_message.lower() or "unauthorized" in error_message.lower():
                # Ошибка токена - помечаем аккаунт как неактивный в БД
                account.status = 'inactive'
                account.save()
                print(f"[handle_send_error] Marked account {account.login} as inactive in DB due to invalid token")
                return "db_inactive"  # Возвращаем статус для пометки в БД
                
            else:
                # Другие ошибки - аккаунт помечается крестиком только на текущий сеанс (не в БД)
                print(f"[handle_send_error] Account {account.login} marked as inactive for current session due to unknown error")
                return "session_inactive"  # Возвращаем статус для пометки на сеанс
                
        except Exception as e:
            print(f"[handle_send_error] Exception: {e}")
            return "session_inactive"  # По умолчанию помечаем как неактивный на сеанс

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
