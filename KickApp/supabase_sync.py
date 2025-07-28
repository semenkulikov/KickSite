#!/usr/bin/env python3
"""
Сервис для синхронизации данных с Supabase
"""

import os
import requests
import json
from datetime import datetime, timedelta
from django.utils import timezone
from django.contrib.auth import get_user_model
from asgiref.sync import sync_to_async
from .models import StreamerStatus, AutoResponse, StreamerMessage
from dotenv import load_dotenv
import logging

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
    
    def get_active_streamers(self):
        """
        Получает список активных стримеров из Supabase
        """
        try:
            url = f"{self.supabase_url}/rest/v1/stream_status"
            params = {
                "status": "eq.active",
                "select": "order_id,vid,updated_at",
                "order": "updated_at.desc",
                "limit": "100"
            }
            
            response = requests.get(url, headers=self.headers, params=params)
            
            if response.status_code == 200:
                data = response.json()
                logger.info(f"Получено {len(data)} активных стримеров из Supabase")
                return data
            else:
                logger.error(f"Ошибка получения данных из Supabase: {response.status_code}")
                return []
                
        except Exception as e:
            logger.error(f"Ошибка подключения к Supabase: {e}")
            return []
    
    def sync_streamer_statuses(self):
        """
        Синхронизирует статусы стримеров с Supabase
        """
        try:
            active_streamers = self.get_active_streamers()
            
            # Получаем все существующие записи стримеров
            existing_streamers = {s.vid: s for s in StreamerStatus.objects.all()}
            
            # Обрабатываем активных стримеров
            for streamer_data in active_streamers:
                vid = streamer_data['vid']
                order_id = streamer_data['order_id']
                updated_at = streamer_data['updated_at']
                
                # Создаем или обновляем запись
                streamer, created = StreamerStatus.objects.get_or_create(
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
                    streamer.save()
                
                logger.info(f"Обновлен стример: {vid}")
            
            # Помечаем неактивных стримеров
            active_vids = {s['vid'] for s in active_streamers}
            inactive_count = 0
            
            for streamer in existing_streamers.values():
                if streamer.vid not in active_vids and streamer.status == 'active':
                    streamer.status = 'inactive'
                    streamer.save()
                    inactive_count += 1
            
            logger.info(f"Синхронизация завершена. Активных: {len(active_streamers)}, неактивных: {inactive_count}")
            
        except Exception as e:
            logger.error(f"Ошибка синхронизации статусов стримеров: {e}")
    
    def assign_users_to_streamers(self):
        """
        Назначает пользователей к активным стримерам
        """
        try:
            # Получаем активных стримеров без назначенных пользователей
            active_streamers = StreamerStatus.objects.filter(
                status='active',
                assigned_user__isnull=True
            )
            
            processed_count = 0
            
            for streamer in active_streamers:
                # Создаем пользователя с именем стримера
                user, created = User.objects.get_or_create(
                    username=streamer.vid,
                    defaults={
                        'email': f"{streamer.vid}@auto.local",
                        'is_staff': False,
                        'is_superuser': False
                    }
                )
                
                # Назначаем пользователя к стримеру
                streamer.assigned_user = user
                streamer.save()
                
                logger.info(f"Пользователь {streamer.vid} назначен к стримеру {streamer.vid}")
                processed_count += 1
            
            logger.info(f"Обработано {processed_count} стримеров")
            logger.info("Синхронизация завершена")
            
        except Exception as e:
            logger.error(f"Ошибка назначения пользователей к стримерам: {e}")
    
    def get_responses_for_streamer(self, vid):
        """
        Получает ответы для конкретного стримера
        """
        try:
            url = f"{self.supabase_url}/rest/v1/streamer_messages"
            params = {
                "vid": f"eq.{vid}",
                "select": "*"
            }
            
            response = requests.get(url, headers=self.headers, params=params)
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Ошибка получения ответов для {vid}: {response.status_code}")
                return []
                
        except Exception as e:
            logger.error(f"Ошибка получения ответов для {vid}: {e}")
            return []
    
    def sync_streamer_messages(self):
        """
        Синхронизирует сообщения стримеров с Supabase
        """
        try:
            # Получаем активных стримеров
            active_streamers = StreamerStatus.objects.filter(status='active')
            
            for streamer in active_streamers:
                # Получаем сообщения из Supabase
                messages_data = self.get_messages_for_streamer(streamer.vid)
                
                if not messages_data:
                    logger.debug(f"Нет сообщений для стримера {streamer.vid}")
                    continue
                
                # Обрабатываем сообщения
                for message_data in messages_data:
                    vid = message_data.get('vid', streamer.vid)
                    message_text = message_data.get('message', '')
                    
                    if not message_text:
                        continue
                    
                    # Создаем или обновляем сообщение
                    streamer_message, created = StreamerMessage.objects.get_or_create(
                        streamer=streamer,
                        message=message_text,
                        defaults={
                            'is_active': True,
                            'created_at': timezone.now()
                        }
                    )
                    
                    if not created:
                        # Обновляем существующее сообщение
                        streamer_message.is_active = True
                        streamer_message.save()
                
                logger.info(f"Синхронизировано {len(messages_data)} сообщений для {streamer.vid}")
            
            # Помечаем неактивные сообщения
            active_message_ids = set()
            for streamer in active_streamers:
                messages_data = self.get_messages_for_streamer(streamer.vid)
                for message_data in messages_data:
                    message_text = message_data.get('message', '')
                    if message_text:
                        active_message_ids.add((streamer.id, message_text))
            
            # Помечаем неактивные сообщения
            inactive_count = 0
            for message in StreamerMessage.objects.filter(is_active=True):
                if (message.streamer.id, message.message) not in active_message_ids:
                    message.is_active = False
                    message.save()
                    inactive_count += 1
            
            if inactive_count > 0:
                logger.info(f"Помечено {inactive_count} неактивных сообщений")
            
        except Exception as e:
            logger.error(f"Ошибка синхронизации сообщений стримеров: {e}")
    
    def get_messages_for_streamer(self, vid):
        """
        Получает сообщения для конкретного стримера
        """
        try:
            url = f"{self.supabase_url}/rest/v1/streamer_messages"
            params = {
                "vid": f"eq.{vid}",
                "select": "*"
            }
            
            response = requests.get(url, headers=self.headers, params=params)
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Ошибка получения сообщений для {vid}: {response.status_code}")
                return []
                
        except Exception as e:
            logger.error(f"Ошибка получения сообщений для {vid}: {e}")
            return []
    
    def create_sample_responses(self, streamer_vid, user):
        """
        Создает примеры ответов для тестирования
        """
        sample_messages = [
            "Привет! Отличный стрим!",
            "Круто играешь!",
            "Продолжай в том же духе!",
            "Спасибо за стрим!",
            "Удачи в игре!"
        ]
        
        # Получаем или создаем стримера
        streamer, created = StreamerStatus.objects.get_or_create(
            vid=streamer_vid,
            defaults={
                'status': 'active',
                'assigned_user': user,
                'last_updated': timezone.now()
            }
        )
        
        if not created:
            streamer.assigned_user = user
            streamer.save()
        
        # Создаем сообщения
        for message_text in sample_messages:
            StreamerMessage.objects.get_or_create(
                streamer=streamer,
                message=message_text,
                defaults={
                    'is_active': True,
                    'created_at': timezone.now()
                }
            )
        
        logger.info(f"Создано {len(sample_messages)} примеров сообщений для {streamer_vid}")


def run_sync():
    """
    Запускает полную синхронизацию
    """
    service = SupabaseSyncService()
    service.sync_streamer_statuses()
    service.assign_users_to_streamers()
    service.sync_streamer_messages()


if __name__ == "__main__":
    # Настройка Django
    import django
    import os
    import sys
    from pathlib import Path
    
    project_root = Path(__file__).parent.parent
    sys.path.insert(0, str(project_root))
    
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Django.settings')
    django.setup()
    
    # Запускаем синхронизацию
    run_sync() 