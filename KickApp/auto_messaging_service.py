#!/usr/bin/env python3
"""
Сервис для автоматического запуска автоматической отправки сообщений
"""

import threading
import time
import logging
from django.apps import AppConfig
from django.conf import settings
from django.core.management import call_command
from django.db import connection

logger = logging.getLogger(__name__)

# Глобальная переменная для хранения потока
_auto_messaging_thread = None
_auto_messaging_running = False


def start_auto_messaging_background():
    """
    Запускает автоматическую отправку сообщений в фоновом режиме
    """
    global _auto_messaging_thread, _auto_messaging_running
    
    if _auto_messaging_running:
        logger.info("Автоматическая отправка сообщений уже запущена")
        return
    
    def run_auto_messaging():
        global _auto_messaging_running
        try:
            logger.info("🚀 Запуск автоматической отправки сообщений в фоновом режиме...")
            _auto_messaging_running = True
            
            # Импортируем здесь, чтобы избежать циклических импортов
            from KickApp.auto_message_sender import start_auto_messaging, stop_auto_messaging
            
            # Запускаем сервис
            start_auto_messaging()
            
            # Держим поток живым
            while _auto_messaging_running:
                time.sleep(60)  # Проверяем каждую минуту
                
        except Exception as e:
            logger.error(f"Ошибка в автоматической отправке сообщений: {e}")
        finally:
            _auto_messaging_running = False
            logger.info("Автоматическая отправка сообщений остановлена")
    
    # Создаем поток
    _auto_messaging_thread = threading.Thread(
        target=run_auto_messaging,
        daemon=True,  # Поток завершится вместе с основным процессом
        name="AutoMessagingThread"
    )
    
    # Запускаем поток
    _auto_messaging_thread.start()
    logger.info("✅ Автоматическая отправка сообщений запущена в фоновом режиме")


def stop_auto_messaging_background():
    """
    Останавливает автоматическую отправку сообщений
    """
    global _auto_messaging_running
    
    if not _auto_messaging_running:
        logger.info("Автоматическая отправка сообщений уже остановлена")
        return
    
    try:
        logger.info("🛑 Остановка автоматической отправки сообщений...")
        _auto_messaging_running = False
        
        # Импортируем здесь, чтобы избежать циклических импортов
        from KickApp.auto_message_sender import stop_auto_messaging
        stop_auto_messaging()
        
        # Ждем завершения потока
        if _auto_messaging_thread and _auto_messaging_thread.is_alive():
            _auto_messaging_thread.join(timeout=10)
            
        logger.info("✅ Автоматическая отправка сообщений остановлена")
        
    except Exception as e:
        logger.error(f"Ошибка при остановке автоматической отправки сообщений: {e}")


def is_auto_messaging_running():
    """
    Проверяет, запущена ли автоматическая отправка сообщений
    """
    return _auto_messaging_running


class AutoMessagingService:
    """
    Сервис для управления автоматической отправкой сообщений
    """
    
    @staticmethod
    def start():
        """Запускает сервис"""
        start_auto_messaging_background()
    
    @staticmethod
    def stop():
        """Останавливает сервис"""
        stop_auto_messaging_background()
    
    @staticmethod
    def is_running():
        """Проверяет статус сервиса"""
        return is_auto_messaging_running() 