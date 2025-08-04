from django.apps import AppConfig
import threading
import time
import os
import traceback

# Глобальная переменная для отслеживания запуска сервисов
_services_started = False
_services_lock = threading.Lock()

class KickappConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'KickApp'
    
    def ready(self):
        """Запускается при инициализации приложения"""
        global _services_started
        
        # Импортируем сигналы чтобы они зарегистрировались
        try:
            from . import signals
        except Exception as e:
            pass
        
        # Проверяем, что это не команда управления Django
        import sys
        
        # Подробное логирование для диагностики
        current_process = os.getpid()
        current_thread = threading.current_thread().ident
        stack_trace = ''.join(traceback.format_stack())
        
        # ПРОВЕРКА: Это не процесс ProcessMessageManager
        if 'process_message_manager.py' in stack_trace or 'send_message_process' in stack_trace:
            return
        
        # Запускаем только при запуске сервера (включая daphne)
        server_commands = ['runserver', 'daphne', 'uvicorn', 'gunicorn']
        # Проверяем любой аргумент на наличие команды сервера
        is_server = any(any(cmd in arg for cmd in server_commands) for arg in sys.argv)
        
        if is_server:
            # Проверяем, что это не миграции
            if any(cmd in ' '.join(sys.argv) for cmd in ['makemigrations', 'migrate', 'collectstatic']):
                return
            
            # Защита от повторного запуска
            with _services_lock:
                if _services_started:
                    return
                
                _services_started = True
            
            # Запускаем сервисы в отдельном потоке с задержкой
            def start_services():
                try:
                    # Ждем полной загрузки Django
                    time.sleep(15)
                    
                    # Запускаем сервис синхронизации
                    from .sync_service import start_sync_service
                    start_sync_service()
                    
                    # Запускаем сервис рассылки
                    from .auto_message_sender import start_auto_messaging
                    start_auto_messaging()
                    
                except Exception as e:
                    # Сбрасываем флаг при ошибке
                    global _services_started
                    _services_started = False
            
            # Запускаем в отдельном потоке
            service_thread = threading.Thread(target=start_services, daemon=True)
            service_thread.start()
            print("⏳ Сервисы будут запущены через 15 секунд...")
            
        else:
            print("❌ Не обнаружен запуск сервера, сервисы не запускаются")
