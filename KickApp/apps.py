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
            print("✅ Сигналы загружены")
        except Exception as e:
            print(f"❌ Ошибка загрузки сигналов: {e}")
        
        # Проверяем, что это не команда управления Django
        import sys
        
        # Подробное логирование для диагностики
        current_process = os.getpid()
        current_thread = threading.current_thread().ident
        stack_trace = ''.join(traceback.format_stack())
        
        print(f"🔍 KickApp ready() вызван:")
        print(f"   - Аргументы: {sys.argv}")
        print(f"   - PID процесса: {current_process}")
        print(f"   - ID потока: {current_thread}")
        print(f"   - Имя потока: {threading.current_thread().name}")
        print(f"   - Сервисы уже запущены: {_services_started}")
        print(f"   - Стек вызовов:")
        for i, line in enumerate(traceback.format_stack()[-5:], 1):
            print(f"     {i}. {line.strip()}")
        
        # ПРОВЕРКА: Это не процесс ProcessMessageManager
        if 'process_message_manager.py' in stack_trace or 'send_message_process' in stack_trace:
            print(f"⚠️ Это процесс ProcessMessageManager (PID: {current_process}), пропускаем запуск сервисов")
            return
        
        # Запускаем только при запуске сервера (включая daphne)
        server_commands = ['runserver', 'daphne', 'uvicorn', 'gunicorn']
        # Проверяем любой аргумент на наличие команды сервера
        is_server = any(any(cmd in arg for cmd in server_commands) for arg in sys.argv)
        
        if is_server:
            print("✅ Обнаружен запуск сервера")
            
            # Проверяем, что это не миграции
            if any(cmd in ' '.join(sys.argv) for cmd in ['makemigrations', 'migrate', 'collectstatic']):
                print("❌ Это команда миграции, сервисы не запускаются")
                return
            
            print("✅ Не миграции, запускаем сервисы")
            
            # Защита от повторного запуска
            with _services_lock:
                if _services_started:
                    print("⚠️ Сервисы уже запущены, пропускаем")
                    return
                
                _services_started = True
                print(f"🔒 Блокируем запуск сервисов")
                print(f"   - Процесс: {current_process}")
                print(f"   - Поток: {current_thread}")
            
            # Запускаем сервисы в отдельном потоке с задержкой
            def start_services():
                try:
                    print("🚀 Инициализация сервисов...")
                    # Ждем полной загрузки Django
                    print("⏳ Ждем 15 секунд для полной загрузки Django...")
                    time.sleep(15)
                    
                    # Запускаем сервис синхронизации
                    print("🔄 Запуск сервиса синхронизации...")
                    from .sync_service import start_sync_service
                    start_sync_service()
                    print("✅ Сервис синхронизации запущен")
                    
                    # Запускаем сервис рассылки
                    print("🤖 Запуск сервиса рассылки...")
                    from .auto_message_sender import start_auto_messaging
                    start_auto_messaging()
                    print("✅ Сервис рассылки запущен")
                    
                except Exception as e:
                    print(f"❌ Ошибка запуска сервисов: {e}")
                    # Сбрасываем флаг при ошибке
                    global _services_started
                    _services_started = False
            
            # Запускаем в отдельном потоке
            service_thread = threading.Thread(target=start_services, daemon=True)
            service_thread.start()
            print("⏳ Сервисы будут запущены через 15 секунд...")
            
        else:
            print("❌ Не обнаружен запуск сервера, сервисы не запускаются")
