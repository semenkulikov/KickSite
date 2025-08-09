import csv
import os
from django.core.management.base import BaseCommand
from KickApp.models import KickAccount
from ProxyApp.models import Proxy
from django.utils import timezone


class Command(BaseCommand):
    help = 'Импортирует KickAccount из CSV-файла с созданием Proxy объектов'

    def add_arguments(self, parser):
        parser.add_argument(
            '--input',
            type=str,
            default='kickaccounts_export.csv',
            help='Путь к входному CSV файлу (по умолчанию: kickaccounts_export.csv)'
        )
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Очистить все существующие KickAccount перед импортом'
        )

    def handle(self, *args, **options):
        input_file = options['input']
        clear_existing = options['clear']
        
        # Проверяем существование файла
        if not os.path.exists(input_file):
            self.stdout.write(
                self.style.ERROR(f'Файл {input_file} не найден')
            )
            return
        
        # Очищаем существующие аккаунты если нужно
        if clear_existing:
            count = KickAccount.objects.count()
            KickAccount.objects.all().delete()
            self.stdout.write(
                self.style.WARNING(f'Удалено {count} существующих KickAccount')
            )
        
        # Импортируем данные
        imported_count = 0
        skipped_count = 0
        proxy_created_count = 0
        
        with open(input_file, 'r', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            
            for row in reader:
                try:
                    # Проверяем, существует ли уже аккаунт с таким login
                    if KickAccount.objects.filter(login=row['login']).exists():
                        self.stdout.write(
                            self.style.WARNING(f'Аккаунт с login {row["login"]} уже существует, пропускаем')
                        )
                        skipped_count += 1
                        continue
                    
                    # Обрабатываем Proxy
                    proxy = None
                    if row.get('proxy_url') and row['proxy_url'].strip():
                        proxy_url = row['proxy_url'].strip()
                        proxy_status = row.get('proxy_status', 'True').lower() == 'true' if row.get('proxy_status') else True
                        
                        # Проверяем, существует ли уже такой прокси
                        try:
                            proxy = Proxy.objects.get(url=proxy_url)
                        except Proxy.DoesNotExist:
                            # Создаем новый прокси
                            proxy = Proxy(url=proxy_url, status=proxy_status)
                            proxy.save()
                            proxy_created_count += 1
                            self.stdout.write(
                                self.style.SUCCESS(f'Создан новый Proxy: {proxy_url}')
                            )
                    
                    # Создаем новый аккаунт
                    account = KickAccount(
                        login=row['login'],
                        token=row['token'],
                        status=row['status'] if row['status'] else 'active',
                        session_token=row['session_token'] if row['session_token'] else None,
                        storage_state_path=row['storage_state_path'] if row['storage_state_path'] else None,
                        password=row['password'] if row['password'] else None,
                        storage_state_status=row['storage_state_status'] if row['storage_state_status'] else 'pending',
                        proxy=proxy
                    )
                    
                    account.save()
                    imported_count += 1
                    
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(f'Ошибка при импорте аккаунта {row.get("login", "unknown")}: {str(e)}')
                    )
                    skipped_count += 1
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Импорт завершен. Импортировано: {imported_count} KickAccount, '
                f'Создано: {proxy_created_count} Proxy, Пропущено: {skipped_count}'
            )
        )
