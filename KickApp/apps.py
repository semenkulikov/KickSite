from django.apps import AppConfig
import threading
import time


class KickappConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'KickApp'
    
    def ready(self):
        """
        Запускается при инициализации приложения Django
        """
        # Проверяем, что это не команда управления Django
        import sys
        if 'manage.py' in sys.argv and any(cmd in sys.argv for cmd in ['runserver', 'run_auto_messaging', 'migrate', 'makemigrations']):
            return
        
        # Запускаем автоматическую отправку сообщений в фоновом режиме
        def start_auto_messaging_delayed():
            """Запускает сервис с небольшой задержкой"""
            time.sleep(5)  # Ждем 5 секунд для полной инициализации Django
            try:
                from KickApp.auto_messaging_service import start_auto_messaging_background
                start_auto_messaging_background()
            except Exception as e:
                print(f"Ошибка запуска автоматической отправки сообщений: {e}")
        
        # Запускаем в отдельном потоке
        thread = threading.Thread(
            target=start_auto_messaging_delayed,
            daemon=True,
            name="AutoMessagingStartupThread"
        )
        thread.start()
