#!/usr/bin/env python3
"""
Сервис для синхронизации данных с Supabase
"""

import os
import aiohttp
import asyncio
import json
from datetime import datetime, timedelta
from django.utils import timezone
from django.contrib.auth import get_user_model
from asgiref.sync import sync_to_async
from .models import StreamerStatus, AutoResponse, StreamerMessage
from dotenv import load_dotenv
import logging
from .models import KickAccount, KickAccountAssignment

# Настройка логирования
logger = logging.getLogger(__name__)

# Загружаем переменные окружения
load_dotenv()

User = get_user_model()

class SupabaseSyncService:
    """
    Сервис для синхронизации данных с Supabase
    """
    
    def __init__(self):
        self.supabase_url = os.getenv("SUPABASE_URL", "").strip('"')
        self.supabase_key = os.getenv("SUPABASE_KEY", "").strip('"')
        
        if not self.supabase_url or not self.supabase_key:
            raise ValueError("SUPABASE_URL и SUPABASE_KEY должны быть установлены в .env файле")
        
        self.headers = {
            "apikey": self.supabase_key,
            "Authorization": f"Bearer {self.supabase_key}",
            "Content-Type": "application/json"
        }
        self.session = None
    
    async def _get_session(self):
        """Получает или создает aiohttp сессию"""
        if self.session is None or self.session.closed:
            timeout = aiohttp.ClientTimeout(total=30)
            self.session = aiohttp.ClientSession(timeout=timeout, headers=self.headers)
        return self.session
    
    async def get_active_streamers_async(self):
        """
        Асинхронно получает список активных стримеров из Supabase
        """
        try:
            session = await self._get_session()
            url = f"{self.supabase_url}/rest/v1/stream_status"
            params = {
                "status": "eq.active",
                "select": "order_id,vid,updated_at",
                "order": "updated_at.desc",
                "limit": "100"
            }
            
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    logger.info(f"Получено {len(data)} активных стримеров из Supabase")
                    return data
                else:
                    logger.error(f"Ошибка получения данных из Supabase: {response.status}")
                    return []
                
        except Exception as e:
            logger.error(f"Ошибка подключения к Supabase: {e}")
            return []
    
    async def sync_streamer_statuses_async(self):
        """
        Асинхронно синхронизирует статусы стримеров с Supabase
        """
        try:
            active_streamers = await self.get_active_streamers_async()
            
            # Получаем все существующие записи стримеров
            existing_streamers = {s.vid: s for s in await sync_to_async(list)(StreamerStatus.objects.all())}
            
            # Обрабатываем активных стримеров
            updated_count = 0
            inactive_count = 0
            
            for streamer_data in active_streamers:
                vid = streamer_data['vid']
                order_id = streamer_data['order_id']
                updated_at = streamer_data['updated_at']
                
                # Создаем или обновляем запись
                streamer, created = await sync_to_async(StreamerStatus.objects.get_or_create)(
                    vid=vid,
                    defaults={
                        'status': 'active',
                        'order_id': order_id,
                        'last_updated': timezone.now()
                    }
                )
                
                if not created:
                    # Обновляем существующую запись
                    streamer.status = 'active'
                    streamer.order_id = order_id
                    streamer.last_updated = timezone.now()
                    await sync_to_async(streamer.save)()
                
                updated_count += 1
            
            # Помечаем неактивные стримеры
            active_vids = {s['vid'] for s in active_streamers}
            for streamer in existing_streamers.values():
                if streamer.vid not in active_vids and streamer.status == 'active':
                    streamer.status = 'inactive'
                    await sync_to_async(streamer.save)()
                    inactive_count += 1
            
            logger.info(f"📊 Синхронизация стримеров: {updated_count} активных, {inactive_count} неактивных")
            
        except Exception as e:
            logger.error(f"Ошибка синхронизации статусов стримеров: {e}")
    
    async def assign_users_to_streamers_async(self):
        """
        Асинхронно назначает пользователей к активным стримерам и добавляет аккаунты
        """
        try:
            # Получаем активных стримеров без назначенных пользователей
            active_streamers = await sync_to_async(list)(StreamerStatus.objects.filter(
                status='active',
                assigned_user__isnull=True
            ))
            
            processed_count = 0
            
            for streamer in active_streamers:
                # Создаем пользователя с именем стримера
                user, created = await sync_to_async(User.objects.get_or_create)(
                    username=streamer.vid,
                    defaults={
                        'email': f"{streamer.vid}@auto.local",
                        'is_staff': False,
                        'is_superuser': False
                    }
                )
                
                # Назначаем пользователя к стримеру
                streamer.assigned_user = user
                await sync_to_async(streamer.save)()
                
                # Добавляем аккаунты к пользователю (many-to-many)
                await self._add_accounts_to_user_async(user)
                
                processed_count += 1
            
            if processed_count > 0:
                logger.info(f"👥 Назначено пользователей: {processed_count}")
            
        except Exception as e:
            logger.error(f"Ошибка назначения пользователей к стримерам: {e}")
    
    async def _add_accounts_to_user_async(self, user):
        """
        Асинхронно добавляет аккаунты к пользователю через many-to-many
        """
        try:
            # Получаем активные аккаунты
            active_accounts = await sync_to_async(list)(KickAccount.objects.filter(status='active'))
            
            if not active_accounts:
                logger.warning("Нет активных аккаунтов для назначения")
                return
            
            # Берем первые 10 аккаунтов (или меньше, если их меньше)
            accounts_to_add = active_accounts[:10]
            
            added_count = 0
            for account in accounts_to_add:
                # Проверяем, не назначен ли уже этот аккаунт данному пользователю
                existing_assignment = await sync_to_async(KickAccountAssignment.objects.filter(
                    kick_account=account,
                    user=user
                ).exists)()
                
                if not existing_assignment:
                    # Создаем назначение аккаунта пользователю
                    await sync_to_async(KickAccountAssignment.objects.create)(
                        kick_account=account,
                        user=user,
                        assigned_by=user,
                        assignment_type='admin_assigned',
                        is_active=True
                    )
                    added_count += 1
            
            if added_count > 0:
                logger.info(f"🔑 Добавлено {added_count} аккаунтов к пользователю {user.username}")
            
        except Exception as e:
            logger.error(f"Ошибка добавления аккаунтов к пользователю {user.username}: {e}")
    
    async def get_messages_for_streamer_async(self, vid):
        """
        Асинхронно получает сообщения для конкретного стримера из Supabase
        """
        try:
            session = await self._get_session()
            url = f"{self.supabase_url}/rest/v1/streamer_messages"
            params = {
                "vid": f"eq.{vid}",
                "select": "vid,message"
            }
            
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    return data
                else:
                    error_text = await response.text()
                    logger.error(f"Ошибка получения сообщений для {vid}: HTTP {response.status} - {error_text}")
                    return []
                
        except Exception as e:
            logger.error(f"Ошибка получения сообщений для {vid}: {str(e)}")
            return []
    
    async def sync_streamer_messages_async(self):
        """
        Асинхронно синхронизирует сообщения стримеров с Supabase
        """
        try:
            # Получаем активных стримеров
            active_streamers = await sync_to_async(list)(StreamerStatus.objects.filter(status='active'))
            
            total_messages = 0
            inactive_count = 0
            
            for streamer in active_streamers:
                if not streamer:
                    continue
                
                # Получаем vid стримера
                streamer_vid = await sync_to_async(lambda: streamer.vid)()
                
                # Получаем сообщения для стримера
                messages_data = await self.get_messages_for_streamer_async(streamer_vid)
                
                if messages_data:
                    # Синхронизируем сообщения
                    for message_data in messages_data:
                        message_text = message_data.get('message', '')
                        
                        if message_text:
                            # Создаем или обновляем сообщение
                            message_obj, created = await sync_to_async(StreamerMessage.objects.get_or_create)(
                                streamer=streamer,
                                message=message_text,
                                defaults={
                                    'is_active': True
                                }
                            )
                            
                            if created:
                                total_messages += 1
                
                # Помечаем неактивные сообщения
                streamer_messages = await sync_to_async(list)(streamer.messages.filter(is_active=True))
                for message in streamer_messages:
                    if message.streamer and message.streamer.status == 'inactive':
                        message.is_active = False
                        await sync_to_async(message.save)()
                        inactive_count += 1
            
            if total_messages > 0 or inactive_count > 0:
                logger.info(f"💬 Синхронизация сообщений: {len(active_streamers)} стримеров, {total_messages} сообщений, {inactive_count} деактивировано")
            
        except Exception as e:
            logger.error(f"Ошибка синхронизации сообщений стримеров: {e}")
    
    async def cleanup(self):
        """Очищает ресурсы"""
        if self.session and not self.session.closed:
            await self.session.close()


# Глобальный экземпляр сервиса
_supabase_sync_service = None

def get_supabase_sync_service():
    """Получает глобальный экземпляр сервиса"""
    global _supabase_sync_service
    if _supabase_sync_service is None:
        _supabase_sync_service = SupabaseSyncService()
    return _supabase_sync_service

async def run_sync_async():
    """Асинхронная версия синхронизации"""
    service = get_supabase_sync_service()
    await service.sync_streamer_statuses_async()
    await service.assign_users_to_streamers_async()
    await service.sync_streamer_messages_async() 