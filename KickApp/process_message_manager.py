import asyncio
import multiprocessing
import time
import logging
import threading
from concurrent.futures import ProcessPoolExecutor, as_completed
from typing import Dict, List, Optional, Callable
import json
import signal
import os
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger("kick.process_manager")

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
    auto: bool = False
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    result: Optional[str] = None
    error: Optional[str] = None
    process: Optional[multiprocessing.Process] = None

def send_message_process(request_data, result_queue=None):
    """Функция для отправки сообщения в отдельном процессе"""
    import cloudscraper
    import urllib.parse
    import requests
    
    process_id = os.getpid()
    account = request_data.get('account', 'unknown')
    logger.info(f"Process {process_id} starting for account {account}")
    
    try:
        # Устанавливаем обработчик сигнала для возможности отмены
        def signal_handler(signum, frame):
            logger.info(f"Process {os.getpid()} received signal {signum}, cancelling...")
            os._exit(1)
        
        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)
        
        # Проверяем флаг отмены в начале
        if hasattr(send_message_process, '_cancelled') and send_message_process._cancelled:
            logger.info(f"Process {os.getpid()} cancelled before start")
            result = "Cancelled by user"
            if result_queue:
                result_queue.put(result)
            return result
        
        # Извлекаем данные запроса
        channel = request_data['channel']
        account = request_data['account']
        message = request_data['message']
        token = request_data['token']
        session_token = request_data['session_token']
        proxy_url = request_data['proxy_url']
        auto = request_data.get('auto', False)
        
        logger.info(f"[PROCESS_SEND] account={account} channel={channel} message={message} auto={auto}")
        
        # Подготовка прокси
        proxy_config = None
        if proxy_url:
            if proxy_url.startswith("socks5://"):
                try:
                    proxy_parts = proxy_url.replace("socks5://", "").split("@")
                    if len(proxy_parts) == 2:
                        auth, server = proxy_parts
                        username, password = auth.split(":")
                        host, port = server.split(":")
                        
                        proxy_config = {
                            'http': f"http://{username}:{password}@{host}:{port}",
                            'https': f"http://{username}:{password}@{host}:{port}"
                        }
                except Exception as e:
                    logger.error(f"Error converting SOCKS5 proxy: {e}")
            elif proxy_url.startswith(("http://", "https://")):
                proxy_config = {
                    'http': proxy_url,
                    'https': proxy_url
                }
        
        # Подготовка токенов и куков
        if not token or '|' not in token:
            result = "Invalid token format"
            if result_queue:
                result_queue.put(result)
            return result
        
        user_id, token_part = token.split('|', 1)
        session_raw = token
        xsrf_token = token_part
        session_decoded = urllib.parse.unquote(session_raw)
        
        cookies = {
            'session_token': session_raw,
            'XSRF-TOKEN': xsrf_token
        }
        
        headers = {
            'Authorization': f'Bearer {session_decoded}',
            'X-XSRF-TOKEN': xsrf_token,
            'X-Requested-With': 'XMLHttpRequest',
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'cluster': 'v2'
        }
        
        # Создаем scraper
        scraper = cloudscraper.create_scraper()
        if proxy_config:
            scraper.proxies = proxy_config
        
        # Получаем chatroom_id
        encoded_channel = urllib.parse.quote(channel)
        
        # Проверяем отмену перед запросом
        if hasattr(send_message_process, '_cancelled') and send_message_process._cancelled:
            logger.info(f"Process {os.getpid()} cancelled before channel request")
            return "Cancelled by user"
        
        channel_response = scraper.get(
            f"https://kick.com/api/v2/channels/{encoded_channel}",
            cookies=cookies,
            headers=headers
        )
        
        if channel_response.status_code != 200:
            error_msg = f"Channel lookup failed: HTTP {channel_response.status_code}"
            logger.error(f"[PROCESS_SEND] {error_msg}")
            result = error_msg
            if result_queue:
                result_queue.put(result)
            return result
        
        channel_data = channel_response.json()
        chatroom_id = channel_data.get('chatroom', {}).get('id')
        
        if not chatroom_id:
            error_msg = "No chatroom_id found in response"
            logger.error(f"[PROCESS_SEND] {error_msg}")
            result = error_msg
            if result_queue:
                result_queue.put(result)
            return result
        
        # Проверяем отмену перед отправкой сообщения
        if hasattr(send_message_process, '_cancelled') and send_message_process._cancelled:
            logger.info(f"Process {os.getpid()} cancelled before sending message")
            result = "Cancelled by user"
            if result_queue:
                result_queue.put(result)
            return result
        
        # Отправляем сообщение
        message_ref = str(int(time.time() * 1000))
        payload = {
            'content': message,
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
            message_type = "AUTO" if auto else "MANUAL"
            logger.info(f"[PROCESS_SEND] ✓ sent ({message_type}): {message}")
            result = "SUCCESS"
        else:
            try:
                error_data = response.json()
                error_message = error_data.get('status', {}).get('message', 'Unknown error')
                
                # Специальная обработка известных ошибок
                if "banned" in error_message.lower():
                    result = "BANNED_ERROR"
                elif "followers only" in error_message.lower():
                    result = "FOLLOWERS_ONLY_ERROR"
                elif "rate limit" in error_message.lower():
                    result = "RATE_LIMIT_ERROR"
                elif "security policy" in error_message.lower():
                    result = "SECURITY_POLICY_ERROR"
                else:
                    logger.error(f"[PROCESS_SEND] Kick.com error: {error_message}")
                    result = f"Kick.com error: {error_message}"
            except:
                result = f"HTTP {response.status_code}: {response.text[:100]}"
                
    except Exception as e:
        logger.error(f"[PROCESS_SEND] Exception: {e}")
        result = f"Exception: {str(e)}"
    
    # Отправляем результат в очередь если она предоставлена
    if result_queue:
        result_queue.put(result)
    
    logger.info(f"Process {process_id} finished for account {account} with result: {result}")
    return result

class ProcessMessageManager:
    """Менеджер сообщений с использованием отдельных процессов"""
    
    def __init__(self, max_concurrent_processes: int = 50):
        self.max_concurrent_processes = max_concurrent_processes
        self.active_requests: Dict[str, MessageRequest] = {}
        self.cancellation_event = threading.Event()
        self._lock = threading.Lock()
        self._shutdown = False
        self._processes_to_kill: List[multiprocessing.Process] = []
        
    async def initialize(self):
        """Инициализация менеджера"""
        # Сбрасываем флаг отмены
        send_message_process._cancelled = False
        
        logger.info(f"ProcessMessageManager initialized with {self.max_concurrent_processes} concurrent processes")
    
    async def reset_state(self):
        """Сброс состояния менеджера для возобновления работы"""
        with self._lock:
            self._shutdown = False
            self.cancellation_event.clear()
            send_message_process._cancelled = False
            logger.info("ProcessMessageManager state reset - ready for new work")
    
    async def cleanup(self):
        """Очистка ресурсов"""
        self._shutdown = True
        await self.cancel_all_requests()
        logger.info("ProcessMessageManager cleaned up")
    
    async def cancel_all_requests(self):
        """Отменить все активные запросы агрессивно"""
        logger.info("Starting aggressive cancellation of all processes...")
        
        with self._lock:
            # Устанавливаем флаг отмены
            self.cancellation_event.set()
            self._shutdown = True
            
            # Убиваем все активные процессы
            killed_count = 0
            for request_id, request in self.active_requests.items():
                if request.status in [MessageStatus.PENDING, MessageStatus.SENDING]:
                    request.status = MessageStatus.CANCELLED
                    request.completed_at = time.time()
                    request.error = "Cancelled by user"
                    
                    # Убиваем процесс если он существует
                    if request.process and request.process.is_alive():
                        try:
                            request.process.terminate()
                            request.process.kill()  # Принудительное завершение
                            killed_count += 1
                            logger.info(f"Killed process {request.process.pid} for request {request_id}")
                        except Exception as e:
                            logger.error(f"Error killing process: {e}")
            
            logger.info(f"Killed {killed_count} active processes")
        
        # Очищаем активные запросы немедленно
        with self._lock:
            self.active_requests.clear()
        
        # Останавливаем все процессы
        logger.info("All processes stopped")
        
        # Устанавливаем глобальный флаг отмены
        send_message_process._cancelled = True
        
        # Принудительно завершаем все процессы
        import psutil
        current_process = psutil.Process()
        children = current_process.children(recursive=True)
        for child in children:
            try:
                child.terminate()
                child.kill()
                logger.info(f"Killed child process {child.pid}")
            except Exception as e:
                logger.error(f"Error killing child process: {e}")
        
        # Дополнительно убиваем все процессы Python, связанные с нашим приложением
        try:
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                if proc.info['name'] == 'python' and proc.info['cmdline']:
                    cmdline = ' '.join(proc.info['cmdline'])
                    if 'send_message_process' in cmdline or 'kick' in cmdline.lower():
                        if proc.pid != os.getpid():
                            proc.terminate()
                            proc.kill()
                            logger.info(f"Killed related process {proc.pid}")
        except Exception as e:
            logger.error(f"Error killing related processes: {e}")
        
        logger.info("All processes terminated")
    
    async def send_message_async(self, 
                                request_id: str,
                                channel: str, 
                                account: str, 
                                message: str, 
                                token: str, 
                                session_token: str, 
                                proxy_url: str,
                                auto: bool = False,
                                callback: Optional[Callable] = None) -> MessageRequest:
        """Асинхронная отправка сообщения в отдельном процессе"""
        
        # Проверяем отмену перед созданием запроса
        if self.cancellation_event.is_set() or self._shutdown or getattr(send_message_process, '_cancelled', False):
            logger.info(f"Request {request_id} cancelled before processing - manager shutting down")
            request = MessageRequest(
                id=request_id,
                channel=channel,
                account=account,
                message=message,
                token=token,
                session_token=session_token,
                proxy_url=proxy_url,
                status=MessageStatus.CANCELLED,
                auto=auto,
                created_at=time.time(),
                completed_at=time.time(),
                error="Manager is shutting down"
            )
            return request
        
        # Дополнительная проверка - если активных запросов слишком много, отклоняем
        with self._lock:
            if len(self.active_requests) >= self.max_concurrent_processes:
                logger.info(f"Too many active requests ({len(self.active_requests)}), rejecting request {request_id}")
                request = MessageRequest(
                    id=request_id,
                    channel=channel,
                    account=account,
                    message=message,
                    token=token,
                    session_token=session_token,
                    proxy_url=proxy_url,
                    status=MessageStatus.CANCELLED,
                    auto=auto,
                    created_at=time.time(),
                    completed_at=time.time(),
                    error="Too many active requests"
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
            auto=auto,
            created_at=time.time()
        )
        
        # Добавляем в активные запросы
        with self._lock:
            self.active_requests[request_id] = request
        
        try:
            # Проверяем отмену
            if self.cancellation_event.is_set() or self._shutdown:
                request.status = MessageStatus.CANCELLED
                request.error = "Cancelled by user"
                return request
            
            request.status = MessageStatus.SENDING
            request.started_at = time.time()
            
            # Подготавливаем данные для процесса
            process_data = {
                'channel': channel,
                'account': account,
                'message': message,
                'token': token,
                'session_token': session_token,
                'proxy_url': proxy_url,
                'auto': auto
            }
            
            # Создаем очередь для получения результата
            result_queue = multiprocessing.Queue()
            
            # Создаем отдельный процесс для отправки сообщения
            process = multiprocessing.Process(
                target=send_message_process,
                args=(process_data, result_queue)
            )
            
            # Сохраняем процесс в запросе для возможности отмены
            request.process = process
            
            # Запускаем процесс и не ждем его завершения
            process.start()
            logger.info(f"Started process {process.pid} for request {request_id} (account: {account})")
            
            # Создаем задачу для мониторинга процесса
            async def monitor_process():
                try:
                    # Проверяем отмену каждые 100мс
                    for _ in range(300):  # 30 секунд / 0.1 секунды
                        if self.cancellation_event.is_set() or self._shutdown:
                            # Убиваем процесс если он еще работает
                            if process.is_alive():
                                process.terminate()
                                process.kill()
                            request.status = MessageStatus.CANCELLED
                            request.error = "Cancelled by user"
                            request.completed_at = time.time()
                            break
                        
                        if not process.is_alive():
                            # Процесс завершился
                            try:
                                # Получаем результат из очереди
                                result = result_queue.get(timeout=1.0)
                            except:
                                # Если не удалось получить результат
                                if process.exitcode == 0:
                                    result = "SUCCESS"
                                else:
                                    result = "Process failed"
                            
                            request.completed_at = time.time()
                            
                            if result == "SUCCESS":
                                request.status = MessageStatus.SUCCESS
                                request.result = "Message sent successfully"
                                logger.info(f"Process {process.pid} completed successfully for request {request_id}")
                            else:
                                request.status = MessageStatus.FAILED
                                request.error = result
                                logger.info(f"Process {process.pid} failed for request {request_id}: {result}")
                            break
                        
                        await asyncio.sleep(0.1)
                    else:
                        # Таймаут - убиваем процесс
                        if process.is_alive():
                            process.terminate()
                            process.kill()
                        request.status = MessageStatus.FAILED
                        request.error = "Timeout exceeded"
                        request.completed_at = time.time()
                        
                except Exception as e:
                    # Ошибка - убиваем процесс
                    if process.is_alive():
                        process.terminate()
                        process.kill()
                    request.status = MessageStatus.FAILED
                    request.error = f"Process error: {str(e)}"
                    request.completed_at = time.time()
                
                # Вызываем callback если предоставлен
                if callback and not self._shutdown:
                    try:
                        await callback(request)
                    except Exception as e:
                        logger.error(f"Callback error: {e}")
                
                # Удаляем из активных запросов
                with self._lock:
                    if request_id in self.active_requests:
                        del self.active_requests[request_id]
            
            # Запускаем мониторинг в фоне
            asyncio.create_task(monitor_process())
            
            # Возвращаем запрос сразу, не ждем завершения
            return request
            
        except Exception as e:
            request.status = MessageStatus.FAILED
            request.error = str(e)
            request.completed_at = time.time()
            logger.error(f"Error sending message {request_id}: {e}")
            
            # Удаляем из активных запросов при ошибке
            with self._lock:
                if request_id in self.active_requests:
                    del self.active_requests[request_id]
            
            return request
    
    def get_stats(self) -> Dict:
        """Получить статистику менеджера"""
        with self._lock:
            stats = {
                'active_requests': len(self.active_requests),
                'max_processes': self.max_concurrent_processes,
                'shutdown': self._shutdown,
                'cancellation_event_set': self.cancellation_event.is_set()
            }
        return stats

# Создаем фабрику для изолированных менеджеров
class ProcessMessageManagerFactory:
    """Фабрика для создания изолированных менеджеров процессов"""
    
    def __init__(self):
        self.managers: Dict[int, ProcessMessageManager] = {}
        self._lock = threading.Lock()
    
    def get_manager(self, user_id: int, max_processes: int = 50) -> ProcessMessageManager:
        """Получить менеджер для конкретного пользователя"""
        with self._lock:
            if user_id not in self.managers:
                self.managers[user_id] = ProcessMessageManager(max_concurrent_processes=max_processes)
                logger.info(f"Created new ProcessMessageManager for user {user_id}")
            else:
                # Если менеджер уже существует, сбрасываем его состояние
                manager = self.managers[user_id]
                asyncio.create_task(manager.reset_state())
                logger.info(f"Reset existing ProcessMessageManager for user {user_id}")
            return self.managers[user_id]
    
    def remove_manager(self, user_id: int):
        """Удалить менеджер пользователя"""
        with self._lock:
            if user_id in self.managers:
                manager = self.managers[user_id]
                asyncio.create_task(manager.cleanup())
                del self.managers[user_id]
                logger.info(f"Removed ProcessMessageManager for user {user_id}")
    
    def get_all_managers(self) -> Dict[int, ProcessMessageManager]:
        """Получить все менеджеры"""
        with self._lock:
            return self.managers.copy()

# Создаем глобальную фабрику
process_message_manager_factory = ProcessMessageManagerFactory()

# Оставляем глобальный менеджер для обратной совместимости (но не используем его)
process_message_manager = ProcessMessageManager() 