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
from ServiceApp.models import User  # Используем кастомную модель пользователя
from asgiref.sync import sync_to_async
from .models import StreamerStatus, AutoResponse, StreamerMessage
from dotenv import load_dotenv
import logging
from .models import KickAccount, KickAccountAssignment

# Настройка логирования
logger = logging.getLogger(__name__)

# Загружаем переменные окружения
load_dotenv()

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
        if not self.session or self.session.closed:
            timeout = aiohttp.ClientTimeout(total=30, connect=10)
            self.session = aiohttp.ClientSession(timeout=timeout)
        return self.session
    
    async def get_all_streamers_async(self):
        """
        Асинхронно получает список ВСЕХ стримеров из Supabase (активных и неактивных)
        """
        try:
            session = await self._get_session()
            url = f"{self.supabase_url}/rest/v1/stream_status"
            
            all_streamers = []
            offset = 0
            limit = 1000  # Максимальный лимит Supabase
            
            while True:
                params = {
                    "select": "order_id,vid,updated_at,status",
                    "order": "updated_at.desc",
                    "limit": str(limit),
                    "offset": str(offset)
                }
                
                logger.info(f"🔍 Запрос к Supabase (offset={offset}): {url}")
                logger.info(f"🔍 Headers: {self.headers}")
                logger.info(f"🔍 Params: {params}")
                
                async with session.get(url, params=params, headers=self.headers) as response:
                    logger.info(f"🔍 Ответ от Supabase: {response.status}")
                    
                    if response.status == 200:
                        data = await response.json()
                        all_streamers.extend(data)
                        
                        # Если получили меньше записей чем лимит, значит это последняя страница
                        if len(data) < limit:
                            break
                        
                        offset += limit
                    elif response.status == 401:
                        logger.error(f"❌ Ошибка 401: Неверный API ключ или URL для Supabase")
                        logger.error(f"❌ URL: {self.supabase_url}")
                        logger.error(f"❌ API Key: {self.supabase_key[:10]}...")
                        break
                    else:
                        error_text = await response.text()
                        logger.error(f"❌ Ошибка получения данных из Supabase: {response.status}")
                        logger.error(f"❌ Ответ: {error_text}")
                        break
                
            logger.info(f"✅ Получено {len(all_streamers)} стримеров из Supabase")
            return all_streamers
                
        except Exception as e:
            logger.error(f"❌ Ошибка подключения к Supabase: {e}")
            import traceback
            traceback.print_exc()
            return []

    async def get_active_streamers_async(self):
        """
        Асинхронно получает список активных стримеров из Supabase
        """
        try:
            session = await self._get_session()
            url = f"{self.supabase_url}/rest/v1/stream_status"
            
            active_streamers = []
            offset = 0
            limit = 1000  # Максимальный лимит Supabase
            
            while True:
                params = {
                    "status": "eq.active",
                    "select": "order_id,vid,updated_at",
                    "order": "updated_at.desc",
                    "limit": str(limit),
                    "offset": str(offset)
                }
                
                logger.info(f"🔍 Запрос к Supabase (offset={offset}): {url}")
                logger.info(f"🔍 Headers: {self.headers}")
                logger.info(f"🔍 Params: {params}")
                
                async with session.get(url, params=params, headers=self.headers) as response:
                    logger.info(f"🔍 Ответ от Supabase: {response.status}")
                    
                    if response.status == 200:
                        data = await response.json()
                        active_streamers.extend(data)
                        
                        # Если получили меньше записей чем лимит, значит это последняя страница
                        if len(data) < limit:
                            break
                        
                        offset += limit
                    elif response.status == 401:
                        logger.error(f"❌ Ошибка 401: Неверный API ключ или URL для Supabase")
                        logger.error(f"❌ URL: {self.supabase_url}")
                        logger.error(f"❌ API Key: {self.supabase_key[:10]}...")
                        break
                    else:
                        error_text = await response.text()
                        logger.error(f"❌ Ошибка получения данных из Supabase: {response.status}")
                        logger.error(f"❌ Ответ: {error_text}")
                        break
                
            logger.info(f"✅ Получено {len(active_streamers)} активных стримеров из Supabase")
            return active_streamers
                
        except Exception as e:
            logger.error(f"❌ Ошибка подключения к Supabase: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    async def sync_streamer_statuses_async(self):
        """
        Асинхронно синхронизирует статусы стримеров с Supabase
        """
        try:
            all_streamers = await self.get_all_streamers_async()
            
            # Получаем все существующие записи стримеров
            existing_streamers = {s.vid: s for s in await sync_to_async(list)(StreamerStatus.objects.all())}
            
            # Обрабатываем всех стримеров
            updated_count = 0
            inactive_count = 0
            
            for streamer_data in all_streamers:
                vid = streamer_data['vid']
                order_id = streamer_data['order_id']
                updated_at = streamer_data['updated_at']
                
                # Определяем статус: если статус явно указан в данных, используем его
                # Если статус пустой, None, 'unknown' или 'offline', считаем стримера неактивным
                status = streamer_data.get('status', 'unknown')
                
                # Если статус пустой, None, 'unknown' или 'offline', считаем стримера неактивным
                if not status or status == '' or status == 'unknown' or status == 'offline':
                    status = 'inactive'
                
                # Создаем или обновляем запись
                streamer, created = await sync_to_async(StreamerStatus.objects.get_or_create)(
                    vid=vid,
                    defaults={
                        'status': status,
                        'order_id': order_id,
                        'last_updated': timezone.now()
                    }
                )
                
                if not created:
                    # Обновляем существующую запись
                    streamer.status = status
                    streamer.order_id = order_id
                    streamer.last_updated = timezone.now()
                    await sync_to_async(streamer.save)()
                
                # Назначаем пользователя к стримеру (если еще не назначен)
                if not streamer.assigned_user:
                    await self._assign_user_to_streamer_async(streamer)
                
                # Обновляем индивидуальные настройки стримера
                await self._update_streamer_hydra_settings_async(streamer)
                
                if status == 'active':
                    updated_count += 1
                else:
                    inactive_count += 1
            
            logger.info(f"📊 Синхронизация стримеров: {updated_count} активных, {inactive_count} неактивных")
            
        except Exception as e:
            logger.error(f"Ошибка синхронизации статусов стримеров: {e}")
    
    async def _assign_user_to_streamer_async(self, streamer):
        """
        Назначает пользователя к стримеру (создает нового или использует существующего)
        """
        try:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            
            # Создаем пользователя с именем стримера
            user, created = await sync_to_async(User.objects.get_or_create)(
                username=streamer.vid,
                defaults={
                    'email': f"{streamer.vid}@auto.local",
                    'first_name': streamer.vid,
                    'last_name': 'Streamer'
                }
            )
            
            if created:
                logger.info(f"👤 Создан новый пользователь {streamer.vid} для стримера {streamer.vid}")
            else:
                logger.info(f"👤 Использован существующий пользователь {streamer.vid} для стримера {streamer.vid}")
            
            # Назначаем пользователя к стримеру
            streamer.assigned_user = user
            await sync_to_async(streamer.save)()
            
            # Назначаем все доступные Kick аккаунты к этому пользователю
            available_accounts = await sync_to_async(list)(KickAccount.objects.filter(
                status='active',
                assignments__isnull=True  # Аккаунты без назначений
            ))
            
            accounts_assigned = 0
            for account in available_accounts:
                assignment, created = await sync_to_async(KickAccountAssignment.objects.get_or_create)(
                    kick_account=account,
                    user=user,
                    defaults={
                        'assignment_type': 'auto',
                        'assigned_by': user
                    }
                )
                if created:
                    accounts_assigned += 1
            
            logger.info(f"✅ Назначен пользователь {user.username} к стримеру {streamer.vid} (добавлено {accounts_assigned} аккаунтов)")
            
        except Exception as e:
            logger.error(f"❌ Ошибка назначения пользователя к стримеру {streamer.vid}: {e}")
    
    async def _update_streamer_hydra_settings_async(self, streamer, is_active=None):
        """
        Обновляет индивидуальные настройки Гидры для стримера
        """
        try:
            from .models import StreamerHydraSettings
            
            # Определяем статус активности
            if is_active is None:
                is_active = streamer.status == 'active' and streamer.is_hydra_enabled
            
            # Получаем или создаем индивидуальные настройки
            hydra_settings, created = await sync_to_async(StreamerHydraSettings.objects.get_or_create)(
                streamer=streamer,
                defaults={
                    'is_active': is_active,
                    'message_interval': None,
                    'cycle_interval': None,
                }
            )
            
            # Обновляем статус активности
            if not created or hydra_settings.is_active != is_active:
                hydra_settings.is_active = is_active
                await sync_to_async(hydra_settings.save)(update_fields=['is_active'])
                logger.info(f"🔄 Обновлены настройки Гидры для стримера {streamer.vid}: is_active={is_active}")
            
        except Exception as e:
            logger.error(f"❌ Ошибка обновления настроек Гидры для стримера {streamer.vid}: {e}")
    
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
            
            all_messages = []
            offset = 0
            limit = 1000  # Максимальный лимит Supabase
            
            while True:
                params = {
                    "vid": f"eq.{vid}",
                    "select": "vid,message",
                    "order": "created_at.desc",  # Сортируем по дате создания (новые сначала)
                    "limit": str(limit),
                    "offset": str(offset)
                }
                
                logger.info(f"🔍 Запрос сообщений для стримера {vid} (offset={offset}): {url}")
                
                async with session.get(url, params=params, headers=self.headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        all_messages.extend(data)
                        
                        # Если получили меньше записей чем лимит, значит это последняя страница
                        if len(data) < limit:
                            break
                        
                        offset += limit
                    else:
                        error_text = await response.text()
                        logger.error(f"❌ Ошибка получения сообщений для {vid}: HTTP {response.status} - {error_text}")
                        break
                
            logger.info(f"✅ Получено {len(all_messages)} сообщений для стримера {vid}")
            return all_messages
                
        except Exception as e:
            logger.error(f"❌ Ошибка получения сообщений для {vid}: {str(e)}")
            import traceback
            logger.error(f"🔍 Детали ошибки: {traceback.format_exc()}")
            return []
    
    async def sync_streamer_messages_async(self):
        """
        Асинхронно синхронизирует сообщения стримеров с Supabase
        """
        try:
            # Получаем активных стримеров (только с активным статусом)
            active_streamers = await sync_to_async(list)(StreamerStatus.objects.filter(status='active'))
            
            logger.info(f"🔄 Начинаем синхронизацию сообщений для {len(active_streamers)} активных стримеров")
            
            total_messages = 0
            inactive_count = 0
            
            for streamer in active_streamers:
                if not streamer:
                    continue
                
                # Получаем vid стримера
                streamer_vid = await sync_to_async(lambda: streamer.vid)()
                logger.info(f"📝 Обрабатываем стримера: {streamer_vid}")
                
                # Получаем сообщения для стримера
                messages_data = await self.get_messages_for_streamer_async(streamer_vid)
                
                if messages_data:
                    # Сначала удаляем все старые сообщения для этого стримера
                    await sync_to_async(streamer.messages.all().delete)()
                    logger.info(f"🗑️ Удалены старые сообщения для стримера {streamer_vid}")
                    
                    # Синхронизируем новые сообщения
                    for message_data in messages_data:
                        message_text = message_data.get('message', '')
                        
                        if message_text:
                            # Создаем новое сообщение (используем get_or_create для избежания дубликатов)
                            message_obj, created = await sync_to_async(StreamerMessage.objects.get_or_create)(
                                streamer=streamer,
                                message=message_text,
                                defaults={'is_active': True}
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
            else:
                logger.info(f"💬 Синхронизация сообщений завершена: {len(active_streamers)} стримеров обработано")
            
        except Exception as e:
            logger.error(f"❌ Ошибка синхронизации сообщений стримеров: {e}")
            import traceback
            logger.error(f"🔍 Детали ошибки: {traceback.format_exc()}")
    
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