#!/usr/bin/env python3
"""
Сервис для автоматической отправки сообщений к активным стримерам
"""

import asyncio
import threading
import time
from datetime import datetime, timedelta
from django.utils import timezone
from django.contrib.auth import get_user_model
from asgiref.sync import sync_to_async
from .models import StreamerStatus, AutoResponse, KickAccount, StreamerMessage
from .supabase_sync import SupabaseSyncService
from .process_message_manager import ProcessMessageManagerFactory
import logging

# Настройка логирования
logger = logging.getLogger(__name__)

User = get_user_model()

class AutoMessageSender:
    """
    Сервис для автоматической отправки сообщений к активным стримерам
    """
    
    def __init__(self):
        self.supabase_sync = SupabaseSyncService()
        self.running = False
        self.thread = None
        self.last_sync_time = None
        self.sync_interval = 180  # 3 минуты (как у вас обновляется)
        self.message_interval = 1  # 1 секунда между циклами (быстро как возможно)
        self.process_manager_factory = ProcessMessageManagerFactory()
        self.streamer_managers = {}  # Менеджеры для каждого стримера
        
    def start(self):
        """Запускает автоматическую отправку сообщений"""
        if self.running:
            logger.warning("Автоматическая отправка уже запущена")
            return
        
        self.running = True
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()
        logger.info("Автоматическая отправка сообщений запущена")
    
    def stop(self):
        """Останавливает автоматическую отправку сообщений"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
        
        # Останавливаем все менеджеры
        for manager in self.streamer_managers.values():
            try:
                asyncio.run(manager.cleanup())
            except:
                pass
        
        logger.info("Автоматическая отправка сообщений остановлена")
    
    def _run_loop(self):
        """Основной цикл отправки сообщений"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            while self.running:
                try:
                    # Синхронизируем данные с Supabase
                    loop.run_until_complete(self._sync_data())
                    
                    # Отправляем сообщения к активным стримерам
                    loop.run_until_complete(self._send_messages_to_active_streamers())
                    
                    # Ждем перед следующей итерацией
                    time.sleep(self.message_interval)
                    
                except Exception as e:
                    logger.error(f"Ошибка в цикле отправки сообщений: {e}")
                    time.sleep(30)  # Ждем 30 секунд при ошибке
        finally:
            loop.close()
    
    async def _sync_data(self):
        """Синхронизирует данные с Supabase"""
        try:
            current_time = timezone.now()
            
            # Синхронизируем только если прошло достаточно времени
            if (self.last_sync_time is None or 
                (current_time - self.last_sync_time).total_seconds() >= self.sync_interval):
                
                logger.info("Синхронизация данных с Supabase...")
                await sync_to_async(self.supabase_sync.sync_streamer_statuses)()
                await sync_to_async(self.supabase_sync.assign_users_to_streamers)()
                self.last_sync_time = current_time
                logger.info("Синхронизация завершена")
                
        except Exception as e:
            logger.error(f"Ошибка синхронизации данных: {e}")
    
    async def _send_messages_to_active_streamers(self):
        """Отправляет сообщения к активным стримерам"""
        try:
            # Получаем активных стримеров с назначенными пользователями
            active_streamers = await sync_to_async(list)(
                StreamerStatus.objects.filter(
                    status='active',
                    assigned_user__isnull=False
                ).select_related('assigned_user')
            )
            
            # Создаем задачи для параллельной отправки
            tasks = []
            for streamer in active_streamers:
                task = self._send_messages_for_streamer(streamer)
                tasks.append(task)
            
            # Выполняем все задачи параллельно
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
                
        except Exception as e:
            logger.error(f"Ошибка отправки сообщений к стримерам: {e}")
    
    async def _send_messages_for_streamer(self, streamer):
        """Отправляет сообщения для конкретного стримера"""
        try:
            # Получаем сообщения для этого стримера из Supabase
            messages = await sync_to_async(list)(streamer.get_messages())
            
            if not messages:
                logger.debug(f"Нет активных сообщений для стримера {streamer.vid}")
                return
            
            # Получаем аккаунты пользователя
            user_accounts = await sync_to_async(list)(
                KickAccount.objects.filter(
                    assigned_users=streamer.assigned_user,
                    status='active'
                )
            )
            
            if not user_accounts:
                logger.warning(f"Нет активных аккаунтов для пользователя {streamer.assigned_user.username}")
                return
            
            # Получаем или создаем менеджер для этого стримера
            streamer_manager = await self._get_streamer_manager(streamer)
            
            # Отправляем сообщения через существующий ProcessMessageManager
            for message in messages:
                if await self._should_send_message(message):
                    # Выбираем случайный аккаунт
                    account = user_accounts[0] if user_accounts else None
                    
                    if account:
                        await self._send_message_via_manager(
                            streamer_manager, 
                            account, 
                            streamer.vid, 
                            message.message
                        )
                        
                        # Обновляем время последней отправки
                        await self._update_last_sent_time(message)
                        logger.info(f"✅ Отправлено сообщение к {streamer.vid} от {account.login}: {message.message[:50]}...")
                
        except Exception as e:
            logger.error(f"Ошибка отправки сообщений для стримера {streamer.vid}: {e}")
    
    async def _get_streamer_manager(self, streamer):
        """Получает или создает ProcessMessageManager для стримера"""
        streamer_id = f"streamer_{streamer.vid}"
        
        if streamer_id not in self.streamer_managers:
            # Создаем новый менеджер для стримера
            manager = self.process_manager_factory.get_manager(
                user_id=streamer.assigned_user.id, 
                max_processes=1000  # Максимум процессов как в основном сайте
            )
            await manager.initialize()
            self.streamer_managers[streamer_id] = manager
            logger.info(f"Создан менеджер для стримера {streamer.vid}")
        
        return self.streamer_managers[streamer_id]
    
    async def _send_message_via_manager(self, manager, account, streamer_vid, message):
        """Отправляет сообщение через ProcessMessageManager"""
        try:
            # Получаем данные аккаунта
            token = account.token or ""
            session_token = account.session_token or ""
            proxy_url = ""
            
            # Получаем прокси для аккаунта
            if hasattr(account, 'proxy') and account.proxy:
                proxy_url = account.proxy.address
            
            # Отправляем через существующий менеджер
            request = await manager.send_message_async(
                request_id=f"auto_{account.id}_{int(time.time())}",
                channel=streamer_vid,
                account=account.login,
                message=message,
                token=token,
                session_token=session_token,
                proxy_url=proxy_url
            )
            
            return request
            
        except Exception as e:
            logger.error(f"Ошибка отправки через менеджер: {e}")
            return None
    
    async def _should_send_message(self, message_obj):
        """Проверяет, нужно ли отправлять сообщение"""
        # Проверяем время последней отправки
        if hasattr(message_obj, 'last_sent') and message_obj.last_sent:
            time_since_last = timezone.now() - message_obj.last_sent
            # Отправляем не чаще чем раз в 5 минут
            if time_since_last.total_seconds() < 300:
                return False
        return True
    
    async def _update_last_sent_time(self, message_obj):
        """Обновляет время последней отправки сообщения"""
        if hasattr(message_obj, 'last_sent'):
            message_obj.last_sent = timezone.now()
            await sync_to_async(message_obj.save)(update_fields=['last_sent'])


# Глобальный экземпляр сервиса
_auto_message_sender = None

def start_auto_messaging():
    """Запускает автоматическую отправку сообщений"""
    global _auto_message_sender
    if not _auto_message_sender:
        _auto_message_sender = AutoMessageSender()
    _auto_message_sender.start()

def stop_auto_messaging():
    """Останавливает автоматическую отправку сообщений"""
    global _auto_message_sender
    if _auto_message_sender:
        _auto_message_sender.stop()

def get_auto_messaging_status():
    """Возвращает статус автоматической отправки сообщений"""
    global _auto_message_sender
    
    if not _auto_message_sender:
        return {
            'running': False,
            'active_streamers_count': 0,
            'total_responses_count': 0
        }
    
    # Получаем статистику
    active_streamers_count = StreamerStatus.objects.filter(status='active').count()
    total_responses_count = StreamerMessage.objects.filter(is_active=True).count()
    
    return {
        'running': _auto_message_sender.running,
        'active_streamers_count': active_streamers_count,
        'total_responses_count': total_responses_count
    } 