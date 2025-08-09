import csv
import os
from django.core.management.base import BaseCommand
from KickApp.models import KickAccount
from django.utils import timezone


class Command(BaseCommand):
    help = 'Экспортирует все KickAccount в CSV-файл'

    def add_arguments(self, parser):
        parser.add_argument(
            '--output',
            type=str,
            default='kickaccounts_export.csv',
            help='Путь к выходному CSV файлу (по умолчанию: kickaccounts_export.csv)'
        )

    def handle(self, *args, **options):
        output_file = options['output']
        
        # Получаем все KickAccount
        kick_accounts = KickAccount.objects.all()
        
        if not kick_accounts.exists():
            self.stdout.write(self.style.WARNING('Нет KickAccount для экспорта'))
            return
        
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
                'storage_state_status'
            ]
            writer.writerow(headers)
            
            # Записываем данные
            for account in kick_accounts:
                row = [
                    account.login,
                    account.token,
                    account.status,
                    account.session_token or '',
                    account.storage_state_path or '',
                    account.password or '',
                    account.storage_state_status or ''
                ]
                writer.writerow(row)
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Успешно экспортировано {kick_accounts.count()} KickAccount в {output_file}'
            )
        )
