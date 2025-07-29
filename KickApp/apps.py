from django.apps import AppConfig
import threading
import time
import os


class KickappConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'KickApp'
    
    def ready(self):
        """Запускается при инициализации приложения"""
        # Проверяем, что это не команда управления Django
        import sys
        
        print(f"🔍 KickApp ready() вызван с аргументами: {sys.argv}")
        
        # Запускаем только при запуске сервера (включая daphne)
        server_commands = ['runserver', 'daphne', 'uvicorn', 'gunicorn']
        # Проверяем любой аргумент на наличие команды сервера
        is_server = any(any(cmd in arg for cmd in server_commands) for arg in sys.argv)
        
        if is_server:
            print("✅ Обнаружен запуск сервера")
            # Проверяем что это не миграции или другие команды
            if not any(arg in sys.argv for arg in ['migrate', 'makemigrations', 'collectstatic', 'test']):
                print("✅ Не миграции, запускаем автоматическую рассылку")
                print("🚀 Инициализация автоматической рассылки...")
                
                # Запускаем автоматическую рассылку в отдельном потоке
                def start_auto_messaging_delayed():
                    """Запускает автоматическую рассылку с задержкой"""
                    print("⏳ Ждем 15 секунд для полной загрузки Django...")
                    time.sleep(15)  # Ждем 15 секунд чтобы Django полностью загрузился
                    try:
                        from .auto_message_sender import start_auto_messaging
                        print("🤖 Запуск автоматической рассылки...")
                        start_auto_messaging()
                        print("✅ Автоматическая рассылка запущена")
                    except Exception as e:
                        print(f"❌ Ошибка запуска автоматической рассылки: {e}")
                
                # Запускаем в отдельном потоке
                thread = threading.Thread(target=start_auto_messaging_delayed, daemon=True)
                thread.start()
                print("⏳ Автоматическая рассылка будет запущена через 15 секунд...")
            else:
                print("❌ Обнаружены миграции или другие команды, автоматическая рассылка не запускается")
        else:
            print("❌ Не обнаружен запуск сервера, автоматическая рассылка не запускается")
