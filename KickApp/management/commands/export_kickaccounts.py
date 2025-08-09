import csv
import os
from django.core.management.base import BaseCommand
from KickApp.models import KickAccount
from django.utils import timezone


class Command(BaseCommand):
    help = 'Экспортирует все KickAccount в CSV-файл с полной информацией о Proxy'

    def add_arguments(self, parser):
        parser.add_argument(
            '--output',
            type=str,
            default='kickaccounts_export.csv',
            help='Путь к выходному CSV файлу (по умолчанию: kickaccounts_export.csv)'
        )

    def handle(self, *args, **options):
        output_file = options['output']
        
        # Получаем все KickAccount с связанными Proxy
        kick_accounts = KickAccount.objects.select_related('proxy').all()
        
        if not kick_accounts.exists():
            self.stdout.write(self.style.WARNING('Нет KickAccount для экспорта'))
            return
        
        # Подсчитываем статистику
        total_accounts = kick_accounts.count()
        accounts_with_proxy = kick_accounts.filter(proxy__isnull=False).count()
        accounts_without_proxy = kick_accounts.filter(proxy__isnull=True).count()
        
        self.stdout.write(f'Всего KickAccount: {total_accounts}')
        self.stdout.write(f'С Proxy: {accounts_with_proxy}')
        self.stdout.write(f'Без Proxy: {accounts_without_proxy}')
        
        # Создаем CSV файл
        with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            
            # Записываем заголовки
            headers = [
                'login',
                'token', 
                'status',
                'session_token',
                'storage_state_path',
                'password',
                'storage_state_status',
                'proxy_url',
                'proxy_status'
            ]
            writer.writerow(headers)
            
            # Записываем данные
            exported_with_proxy = 0
            exported_without_proxy = 0
            
            for account in kick_accounts:
                # Получаем данные о Proxy
                proxy_url = ''
                proxy_status = ''
                
                if account.proxy:
                    proxy_url = account.proxy.url
                    proxy_status = str(account.proxy.status)
                    exported_with_proxy += 1
                else:
                    exported_without_proxy += 1
                
                row = [
                    account.login,
                    account.token,
                    account.status,
                    account.session_token or '',
                    account.storage_state_path or '',
                    account.password or '',
                    account.storage_state_status or '',
                    proxy_url,
                    proxy_status
                ]
                writer.writerow(row)
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Успешно экспортировано {total_accounts} KickAccount в {output_file}\n'
                f'  - С Proxy: {exported_with_proxy}\n'
                f'  - Без Proxy: {exported_without_proxy}'
            )
        )
