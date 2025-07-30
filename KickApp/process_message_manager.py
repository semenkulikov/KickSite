import multiprocessing
import asyncio
import time
import logging
from enum import Enum
from concurrent.futures import ProcessPoolExecutor
import signal
import os
import threading

logger = logging.getLogger(__name__)

class MessageStatus(Enum):
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"

class MessageRequest:
    def __init__(self, request_id, channel, account, message, token, session_token, proxy_url):
        self.request_id = request_id
        self.channel = channel
        self.account = account
        self.message = message
        self.token = token
        self.session_token = session_token
        self.proxy_url = proxy_url
        self.status = MessageStatus.PENDING
        self.error = None
        self.response = None
        self.start_time = time.time()
        self.end_time = None

class ProcessMessageManager:
    def __init__(self, max_workers=4):
        self.max_workers = max_workers
        self.executor = ProcessPoolExecutor(max_workers=max_workers)
        self.requests = {}
        self._cancelled = False
    
    def cancel_all(self):
        """Отменяет все текущие запросы"""
        self._cancelled = True
        logger.info("Отмена всех запросов")
    
    async def send_message_async(self, request_id, channel, account, message, token, session_token, proxy_url):
        """
        Асинхронно отправляет сообщение через отдельный процесс
        Передаем только примитивные данные, а не Django объекты
        """
        if self._cancelled:
            logger.info(f"Запрос {request_id} отменен")
            return None
        
        # Создаем запрос с примитивными данными
        request = MessageRequest(request_id, channel, account, message, token, session_token, proxy_url)
        self.requests[request_id] = request
        
        try:
            # Подготавливаем данные для передачи в дочерний процесс
            # Передаем только примитивные типы данных
            process_data = {
                'request_id': request_id,
                'channel': channel,
                'account': account,
                'message': message,
                'token': token,
                'session_token': session_token,
                'proxy_url': proxy_url or ""
            }
            
            logger.info(f"Started process for request {request_id} (account: {account})")
            
            # Запускаем в отдельном процессе
            loop = asyncio.get_event_loop()
            future = loop.run_in_executor(
                self.executor, 
                send_message_process, 
                process_data
            )
            
            # Ждем результат
            result = await future
            
            # Обновляем статус запроса
            if result == "Success":
                request.status = MessageStatus.SUCCESS
            elif result == "Failed":
                request.status = MessageStatus.FAILED
            else:
                request.status = MessageStatus.FAILED
                request.error = result
            
            request.end_time = time.time()
            
            return request
            
        except Exception as e:
            logger.error(f"Process {request_id} failed: {e}")
            request.status = MessageStatus.FAILED
            request.error = str(e)
            request.end_time = time.time()
            return request
        finally:
            # Удаляем запрос из словаря
            if request_id in self.requests:
                del self.requests[request_id]

# Фабрика для создания изолированных менеджеров процессов
class ProcessMessageManagerFactory:
    """Фабрика для создания изолированных менеджеров процессов"""
    
    def __init__(self):
        self.managers = {}
        self._lock = threading.Lock()
    
    def get_manager(self, user_id, max_processes=50):
        """Получить менеджер для конкретного пользователя"""
        with self._lock:
            if user_id not in self.managers:
                self.managers[user_id] = ProcessMessageManager(max_workers=max_processes)
                logger.info(f"Created new ProcessMessageManager for user {user_id}")
            return self.managers[user_id]
    
    def remove_manager(self, user_id):
        """Удалить менеджер пользователя"""
        with self._lock:
            if user_id in self.managers:
                del self.managers[user_id]
                logger.info(f"Removed ProcessMessageManager for user {user_id}")
    
    def get_all_managers(self):
        """Получить все менеджеры"""
        with self._lock:
            return self.managers.copy()

# Создаем глобальную фабрику для обратной совместимости
process_message_manager_factory = ProcessMessageManagerFactory()

def send_message_process(request_data):
    """Функция для отправки сообщения в отдельном процессе"""
    import cloudscraper
    import urllib.parse
    import requests
    
    # Инициализируем Django в дочернем процессе
    import os
    import sys
    import django
    
    # Добавляем путь к проекту в sys.path
    project_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.path.insert(0, project_path)
    
    # Устанавливаем переменную окружения для Django
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Django.settings')
    
    # Инициализируем Django
    django.setup()
    
    # Настраиваем логирование в дочернем процессе
    import logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(levelname)s %(asctime)s %(module)s %(process)d %(thread)d %(message)s'
    )
    
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
        
        # Извлекаем данные запроса (все примитивные типы)
        channel = request_data['channel']
        account = request_data['account']
        message = request_data['message']
        token = request_data['token']
        session_token = request_data['session_token']
        proxy_url = request_data['proxy_url']
        
        logger.info(f"[PROCESS_SEND] account={account} channel={channel} message={message}")
        
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
            return result
        
        channel_data = channel_response.json()
        chatroom_id = channel_data.get('chatroom', {}).get('id')
        
        if not chatroom_id:
            error_msg = "No chatroom_id found in response"
            logger.error(f"[PROCESS_SEND] {error_msg}")
            result = error_msg
            return result
        
        # Проверяем отмену перед отправкой сообщения
        if hasattr(send_message_process, '_cancelled') and send_message_process._cancelled:
            logger.info(f"Process {os.getpid()} cancelled before sending message")
            result = "Cancelled by user"
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
            logger.info(f"[PROCESS_SEND] ✓ sent: {message}")
            print(f"✅ Сообщение успешно отправлено: {account} -> {channel}: {message}")
            result = "Success"
        else:
            try:
                error_data = response.json()
                error_message = error_data.get('status', {}).get('message', 'Unknown error')
                
                # Специальная обработка известных ошибок
                if "banned" in error_message.lower():
                    result = "BANNED_ERROR"
                    print(f"🚫 Аккаунт забанен: {account} -> {channel}: {error_message}")
                elif "followers only" in error_message.lower():
                    result = "FOLLOWERS_ONLY_ERROR"
                    print(f"👥 Только для подписчиков: {account} -> {channel}: {error_message}")
                elif "rate limit" in error_message.lower():
                    result = "RATE_LIMIT_ERROR"
                    print(f"⏱️ Превышен лимит: {account} -> {channel}: {error_message}")
                elif "security policy" in error_message.lower():
                    result = "SECURITY_POLICY_ERROR"
                    print(f"🔒 Политика безопасности: {account} -> {channel}: {error_message}")
                else:
                    logger.error(f"[PROCESS_SEND] Kick.com error: {error_message}")
                    print(f"❌ Ошибка Kick: {account} -> {channel}: {error_message}")
                    result = f"Kick.com error: {error_message}"
            except:
                result = f"HTTP {response.status_code}: {response.text[:100]}"
                print(f"❌ HTTP ошибка: {account} -> {channel}: {result}")
                
    except Exception as e:
        logger.error(f"[PROCESS_SEND] Exception: {e}")
        result = f"Exception: {str(e)}"
    
    return result 