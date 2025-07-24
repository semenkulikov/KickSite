import asyncio
import aiohttp
import cloudscraper
import time
import logging
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional, Callable
import urllib.parse
import json
from dataclasses import dataclass
from enum import Enum
import signal
import os

logger = logging.getLogger("kick.async_manager")

class MessageStatus(Enum):
    PENDING = "pending"
    SENDING = "sending"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"

@dataclass
class MessageRequest:
    id: str
    channel: str
    account: str
    message: str
    token: str
    session_token: str
    proxy_url: str
    status: MessageStatus
    created_at: float
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    result: Optional[str] = None
    error: Optional[str] = None
    future: Optional[asyncio.Future] = None

class AsyncMessageManager:
    """Асинхронный менеджер для отправки сообщений с высокой производительностью"""
    
    def __init__(self, max_concurrent_requests: int = 100, max_workers: int = 50):
        self.max_concurrent_requests = max_concurrent_requests
        self.max_workers = max_workers
        self.active_requests: Dict[str, MessageRequest] = {}
        self.request_semaphore = asyncio.Semaphore(max_concurrent_requests)
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.cancellation_event = threading.Event()
        self.loop = None
        self.session = None
        self._lock = threading.Lock()
        self._shutdown = False
        
    async def initialize(self):
        """Инициализация менеджера"""
        self.loop = asyncio.get_event_loop()
        connector = aiohttp.TCPConnector(
            limit=self.max_concurrent_requests * 2,
            limit_per_host=100,
            ttl_dns_cache=300,
            use_dns_cache=True,
            keepalive_timeout=30
        )
        self.session = aiohttp.ClientSession(
            connector=connector,
            timeout=aiohttp.ClientTimeout(total=30, connect=10)
        )
        logger.info(f"AsyncMessageManager initialized with {self.max_concurrent_requests} concurrent requests")
    
    async def cleanup(self):
        """Очистка ресурсов"""
        self._shutdown = True
        self.cancel_all_requests()
        
        if self.session:
            await self.session.close()
        if self.executor:
            self.executor.shutdown(wait=False)  # Не ждем завершения
        logger.info("AsyncMessageManager cleaned up")
    
    def cancel_all_requests(self):
        """Отменить все активные запросы агрессивно"""
        logger.info("Starting aggressive cancellation of all requests...")
        
        with self._lock:
            # Устанавливаем флаг отмены
            self.cancellation_event.set()
            
            # Отменяем все запросы
            cancelled_count = 0
            for request_id, request in self.active_requests.items():
                if request.status in [MessageStatus.PENDING, MessageStatus.SENDING]:
                    request.status = MessageStatus.CANCELLED
                    request.completed_at = time.time()
                    request.error = "Cancelled by user"
                    cancelled_count += 1
                    
                    # Отменяем связанный Future если есть
                    if request.future and not request.future.done():
                        request.future.cancel()
            
            logger.info(f"Cancelled {cancelled_count} active requests")
        
        # Очищаем активные запросы немедленно
        with self._lock:
            self.active_requests.clear()
    
    async def send_message_async(self, 
                                request_id: str,
                                channel: str, 
                                account: str, 
                                message: str, 
                                token: str, 
                                session_token: str, 
                                proxy_url: str,
                                callback: Optional[Callable] = None) -> MessageRequest:
        """Асинхронная отправка сообщения"""
        
        # Проверяем отмену перед созданием запроса
        if self.cancellation_event.is_set() or self._shutdown:
            request = MessageRequest(
                id=request_id,
                channel=channel,
                account=account,
                message=message,
                token=token,
                session_token=session_token,
                proxy_url=proxy_url,
                status=MessageStatus.CANCELLED,
                created_at=time.time(),
                completed_at=time.time(),
                error="Manager is shutting down"
            )
            return request
        
        # Создаем запрос
        request = MessageRequest(
            id=request_id,
            channel=channel,
            account=account,
            message=message,
            token=token,
            session_token=session_token,
            proxy_url=proxy_url,
            status=MessageStatus.PENDING,
            created_at=time.time()
        )
        
        # Добавляем в активные запросы
        with self._lock:
            self.active_requests[request_id] = request
        
        try:
            async with self.request_semaphore:
                # Проверяем отмену
                if self.cancellation_event.is_set() or self._shutdown:
                    request.status = MessageStatus.CANCELLED
                    request.error = "Cancelled by user"
                    return request
                
                request.status = MessageStatus.SENDING
                request.started_at = time.time()
                
                # Создаем Future для возможности отмены
                request.future = asyncio.Future()
                
                # Запускаем отправку в отдельном потоке
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(
                    self.executor,
                    self._send_message_sync,
                    request
                )
                
                request.completed_at = time.time()
                
                if result == "SUCCESS":
                    request.status = MessageStatus.SUCCESS
                    request.result = "Message sent successfully"
                else:
                    request.status = MessageStatus.FAILED
                    request.error = result
                
                # Вызываем callback если предоставлен
                if callback and not self._shutdown:
                    try:
                        await callback(request)
                    except Exception as e:
                        logger.error(f"Callback error: {e}")
                
                return request
                
        except asyncio.CancelledError:
            request.status = MessageStatus.CANCELLED
            request.error = "Request was cancelled"
            request.completed_at = time.time()
            logger.info(f"Request {request_id} was cancelled")
            return request
        except Exception as e:
            request.status = MessageStatus.FAILED
            request.error = str(e)
            request.completed_at = time.time()
            logger.error(f"Error sending message {request_id}: {e}")
            return request
        finally:
            # Удаляем из активных запросов немедленно
            with self._lock:
                if request_id in self.active_requests:
                    del self.active_requests[request_id]
    
    def _send_message_sync(self, request: MessageRequest) -> str:
        """Синхронная отправка сообщения (выполняется в отдельном потоке)"""
        try:
            # Проверяем отмену
            if self.cancellation_event.is_set():
                request.status = MessageStatus.CANCELLED
                request.error = "Cancelled by user"
                return "Cancelled by user"
            
            logger.info(f"[ASYNC_SEND] account={request.account} channel={request.channel} message={request.message}")
            
            # Подготовка прокси
            proxy_config = self._prepare_proxy_config(request.proxy_url)
            
            # Подготовка токенов и куков
            cookies, headers = self._prepare_auth_data(request.token, request.session_token)
            
            # Создаем scraper
            scraper = cloudscraper.create_scraper()
            if proxy_config:
                scraper.proxies = proxy_config
            
            # Получаем chatroom_id
            encoded_channel = urllib.parse.quote(request.channel)
            channel_response = scraper.get(
                f"https://kick.com/api/v2/channels/{encoded_channel}",
                cookies=cookies,
                headers=headers
            )
            
            if channel_response.status_code != 200:
                error_msg = f"Channel lookup failed: HTTP {channel_response.status_code}"
                logger.error(f"[ASYNC_SEND] {error_msg}")
                return error_msg
            
            channel_data = channel_response.json()
            chatroom_id = channel_data.get('chatroom', {}).get('id')
            
            if not chatroom_id:
                error_msg = "No chatroom_id found in response"
                logger.error(f"[ASYNC_SEND] {error_msg}")
                return error_msg
            
            # Отправляем сообщение
            message_ref = str(int(time.time() * 1000))
            payload = {
                'content': request.message,
                'type': 'message',
                'message_ref': message_ref
            }
            
            response = scraper.post(
                f"https://kick.com/api/v2/messages/send/{chatroom_id}",
                cookies=cookies,
                headers=headers,
                json=payload
            )
            
            if response.status_code == 200:
                logger.info(f"[ASYNC_SEND] ✓ sent: {request.message}")
                return "SUCCESS"
            else:
                try:
                    error_data = response.json()
                    error_message = error_data.get('status', {}).get('message', 'Unknown error')
                    
                    # Специальная обработка известных ошибок
                    if "banned" in error_message.lower():
                        return "BANNED_ERROR"
                    elif "followers only" in error_message.lower():
                        return "FOLLOWERS_ONLY_ERROR"
                    elif "rate limit" in error_message.lower():
                        return "RATE_LIMIT_ERROR"
                    elif "security policy" in error_message.lower():
                        return "SECURITY_POLICY_ERROR"
                    
                    logger.error(f"[ASYNC_SEND] Kick.com error: {error_message}")
                    return f"Kick.com error: {error_message}"
                except:
                    return f"HTTP {response.status_code}: {response.text[:100]}"
                    
        except Exception as e:
            logger.error(f"[ASYNC_SEND] Exception: {e}")
            return f"Exception: {str(e)}"
    
    def _prepare_proxy_config(self, proxy_url: str) -> Optional[Dict]:
        """Подготовка конфигурации прокси"""
        if not proxy_url:
            return None
            
        if proxy_url.startswith("socks5://"):
            try:
                proxy_parts = proxy_url.replace("socks5://", "").split("@")
                if len(proxy_parts) == 2:
                    auth, server = proxy_parts
                    username, password = auth.split(":")
                    host, port = server.split(":")
                    
                    return {
                        'http': f"http://{username}:{password}@{host}:{port}",
                        'https': f"http://{username}:{password}@{host}:{port}"
                    }
            except Exception as e:
                logger.error(f"Error converting SOCKS5 proxy: {e}")
        elif proxy_url.startswith(("http://", "https://")):
            return {
                'http': proxy_url,
                'https': proxy_url
            }
        
        return None
    
    def _prepare_auth_data(self, token: str, session_token: str) -> tuple:
        """Подготовка данных аутентификации"""
        if not token or '|' not in token:
            raise ValueError("Invalid token format")
        
        user_id, token_part = token.split('|', 1)
        session_raw = token
        xsrf_token = token_part
        session_decoded = urllib.parse.unquote(session_raw)
        
        # Формируем куки
        cookies = {
            'session_token': session_raw,
            'XSRF-TOKEN': xsrf_token
        }
        
        # Формируем заголовки
        headers = {
            'Authorization': f'Bearer {session_decoded}',
            'X-XSRF-TOKEN': xsrf_token,
            'X-Requested-With': 'XMLHttpRequest',
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'cluster': 'v2'
        }
        
        return cookies, headers
    
    async def _cleanup_request(self, request_id: str, delay: int = 60):
        """Очистка запроса из памяти через задержку"""
        await asyncio.sleep(delay)
        with self._lock:
            if request_id in self.active_requests:
                del self.active_requests[request_id]
    
    def get_stats(self) -> Dict:
        """Получить статистику менеджера"""
        with self._lock:
            total = len(self.active_requests)
            pending = sum(1 for r in self.active_requests.values() if r.status == MessageStatus.PENDING)
            sending = sum(1 for r in self.active_requests.values() if r.status == MessageStatus.SENDING)
            success = sum(1 for r in self.active_requests.values() if r.status == MessageStatus.SUCCESS)
            failed = sum(1 for r in self.active_requests.values() if r.status == MessageStatus.FAILED)
            cancelled = sum(1 for r in self.active_requests.values() if r.status == MessageStatus.CANCELLED)
            
            return {
                'total_requests': total,
                'pending': pending,
                'sending': sending,
                'success': success,
                'failed': failed,
                'cancelled': cancelled,
                'max_concurrent': self.max_concurrent_requests,
                'max_workers': self.max_workers
            }

# Глобальный экземпляр менеджера
message_manager = AsyncMessageManager(max_concurrent_requests=200, max_workers=100) 