import asyncio
import threading
import logging
from asgiref.sync import sync_to_async
from .models import StreamerStatus, StreamerMessage
from .supabase_sync import SupabaseSyncService

logger = logging.getLogger(__name__)

class SyncService:
    """Отдельный сервис для синхронизации данных с Supabase"""
    
    def __init__(self):
        self.is_running = False
        self.thread = None
        self._loop = None
        self.sync_interval = 180  # 3 минуты по умолчанию
        self.supabase_sync = SupabaseSyncService()
    
    def start(self):
        """Запускает сервис синхронизации в отдельном потоке"""
        if self.is_running:
            return
            
        self.is_running = True
        self.thread = threading.Thread(target=self._run_sync_loop, daemon=True)
        self.thread.start()
        logger.info("🔄 Сервис синхронизации запущен")
    
    def stop(self):
        """Останавливает сервис синхронизации"""
        if not self.is_running:
            return
            
        self.is_running = False
        if self._loop and self._loop.is_running():
            self._loop.call_soon_threadsafe(self._loop.stop)
        
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=5)
        
        logger.info("🛑 Сервис синхронизации остановлен")
    
    def _run_sync_loop(self):
        """Запускает асинхронный цикл синхронизации"""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        
        try:
            self._loop.run_until_complete(self._sync_loop())
        except Exception as e:
            logger.error(f"Ошибка в цикле синхронизации: {e}")
        finally:
            self._loop.close()
    
    async def _sync_loop(self):
        """Основной цикл синхронизации"""
        logger.info("🔄 Запуск цикла синхронизации")
        
        while self.is_running:
            try:
                await self._perform_sync()
                await asyncio.sleep(self.sync_interval)
            except Exception as e:
                logger.error(f"Ошибка синхронизации: {e}")
                await asyncio.sleep(30)  # Ждем 30 секунд при ошибке
        
        logger.info("🛑 Цикл синхронизации остановлен")
    
    async def _perform_sync(self):
        """Выполняет синхронизацию данных"""
        try:
            logger.info("🔄 Начинаем синхронизацию данных...")
            
            # Синхронизируем стримеров
            await self.supabase_sync.sync_streamer_statuses_async()
            
            # Синхронизируем сообщения
            await self.supabase_sync.sync_streamer_messages_async()
            
            logger.info("✅ Синхронизация завершена")
            
        except Exception as e:
            logger.error(f"Ошибка синхронизации: {e}")

# Глобальный экземпляр сервиса синхронизации
_sync_service = None

def get_sync_service():
    """Возвращает глобальный экземпляр сервиса синхронизации"""
    global _sync_service
    if _sync_service is None:
        _sync_service = SyncService()
    return _sync_service

def start_sync_service():
    """Запускает сервис синхронизации"""
    service = get_sync_service()
    service.start()

def stop_sync_service():
    """Останавливает сервис синхронизации"""
    service = get_sync_service()
    service.stop() 