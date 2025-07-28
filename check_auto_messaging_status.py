#!/usr/bin/env python3
"""
Скрипт для проверки статуса автоматической отправки сообщений
"""

import os
import sys
import django

# Настройка Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Django.settings')
django.setup()

from KickApp.auto_messaging_service import is_auto_messaging_running
from KickApp.models import StreamerStatus, StreamerMessage
from django.contrib.auth import get_user_model

User = get_user_model()

def check_status():
    """Проверяет статус автоматической отправки сообщений"""
    
    print("🔍 Проверка статуса автоматической отправки сообщений...")
    print("=" * 50)
    
    # Проверяем, запущен ли сервис
    is_running = is_auto_messaging_running()
    print(f"📊 Сервис запущен: {'✅ ДА' if is_running else '❌ НЕТ'}")
    
    # Статистика стримеров
    active_streamers = StreamerStatus.objects.filter(status='active')
    total_streamers = StreamerStatus.objects.count()
    
    print(f"📈 Активных стримеров: {active_streamers.count()}")
    print(f"📊 Всего стримеров: {total_streamers}")
    
    # Статистика сообщений
    total_messages = StreamerMessage.objects.count()
    active_messages = StreamerMessage.objects.filter(is_active=True).count()
    
    print(f"💬 Всего сообщений: {total_messages}")
    print(f"✅ Активных сообщений: {active_messages}")
    
    # Пользователи для стримеров
    users_with_streamers = User.objects.filter(streamerstatus__isnull=False).distinct()
    print(f"👤 Пользователей для стримеров: {users_with_streamers.count()}")
    
    # Показываем активных стримеров
    if active_streamers.exists():
        print("\n🎯 Активные стримеры:")
        for streamer in active_streamers[:10]:  # Показываем первые 10
            assigned_user = "✅ Назначен" if streamer.assigned_user else "❌ Не назначен"
            print(f"  - {streamer.vid} ({assigned_user})")
    
    # Показываем пользователей
    if users_with_streamers.exists():
        print("\n👤 Пользователи для стримеров:")
        for user in users_with_streamers[:10]:  # Показываем первые 10
            accounts_count = user.kickaccount_set.count()
            print(f"  - {user.username} (аккаунтов: {accounts_count})")
    
    print("\n" + "=" * 50)
    print("💡 Для запуска сервиса используйте: ./start_site_with_auto_messaging.sh")

if __name__ == "__main__":
    check_status() 