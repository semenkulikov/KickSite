#!/usr/bin/env python3
"""
Django management команда для запуска автоматической отправки сообщений
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
import time
import signal
import sys
from KickApp.auto_message_sender import start_auto_messaging, stop_auto_messaging, get_auto_messaging_status


class Command(BaseCommand):
    help = 'Запускает сервис автоматической отправки сообщений к стримерам'

    def add_arguments(self, parser):
        parser.add_argument(
            '--daemon',
            action='store_true',
            help='Запуск в фоновом режиме',
        )
        parser.add_argument(
            '--sync-only',
            action='store_true',
            help='Только синхронизация данных без отправки сообщений',
        )

    def handle(self, *args, **options):
        # Обработчик сигналов для graceful shutdown
        def signal_handler(signum, frame):
            self.stdout.write(self.style.WARNING(f'\nПолучен сигнал {signum}, останавливаем сервис...'))
            stop_auto_messaging()
            self.stdout.write(self.style.SUCCESS('Сервис остановлен'))
            sys.exit(0)

        # Регистрируем обработчики сигналов
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        try:
            self.stdout.write(self.style.SUCCESS('🚀 Запуск сервиса автоматической отправки сообщений...'))
            
            # Показываем начальное состояние
            status = get_auto_messaging_status()
            self.stdout.write(f'📊 Начальное состояние:')
            self.stdout.write(f'  - Активных стримеров: {status["active_streamers_count"]}')
            self.stdout.write(f'  - Всего сообщений: {status["total_responses_count"]}')
            
            if options['sync_only']:
                self.stdout.write('🔄 Запуск только синхронизации...')
                from KickApp.supabase_sync import run_sync
                run_sync()
                self.stdout.write(self.style.SUCCESS('Синхронизация завершена'))
                return
            
            # Запускаем сервис
            start_auto_messaging()
            
            if options['daemon']:
                self.stdout.write('👻 Запуск в фоновом режиме...')
                self.stdout.write('💡 Для остановки используйте: python manage.py run_auto_messaging --stop')
                
                # Бесконечный цикл для daemon режима
                while True:
                    time.sleep(60)  # Проверяем каждую минуту
                    status = get_auto_messaging_status()
                    if not status['running']:
                        self.stdout.write(self.style.ERROR('Сервис остановлен'))
                        break
            else:
                self.stdout.write('📈 Мониторинг работы (Ctrl+C для остановки)...')
                
                # Интерактивный режим с выводом статистики
                while True:
                    time.sleep(30)  # Обновляем каждые 30 секунд
                    status = get_auto_messaging_status()
                    
                    self.stdout.write(f'⏰ {timezone.now().strftime("%H:%M:%S")} - '
                                   f'Стримеров: {status["active_streamers_count"]}, '
                                   f'Сообщений: {status["total_responses_count"]}')
                    
        except KeyboardInterrupt:
            self.stdout.write(self.style.WARNING('\nПолучен сигнал остановки...'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Ошибка: {e}'))
        finally:
            stop_auto_messaging()
            self.stdout.write(self.style.SUCCESS('✅ Сервис остановлен')) 