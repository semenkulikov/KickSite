from django.core.management.base import BaseCommand
from django.db import models
from KickApp.models import StreamerStatus

class Command(BaseCommand):
    help = 'Исправляет статусы стримеров: unknown -> inactive'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Показать что будет изменено без внесения изменений',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        # Находим стримеров с пустым статусом, 'unknown' или 'offline'
        problematic_streamers = StreamerStatus.objects.filter(
            models.Q(status='') | 
            models.Q(status__isnull=True) | 
            models.Q(status='unknown') |
            models.Q(status='offline')
        )
        
        if not problematic_streamers:
            self.stdout.write(
                self.style.SUCCESS('Нет стримеров с проблемными статусами')
            )
            return
        
        self.stdout.write(f'Найдено {problematic_streamers.count()} стримеров с проблемными статусами')
        
        if dry_run:
            self.stdout.write('Стримеры которые будут изменены:')
            for streamer in problematic_streamers:
                current_status = streamer.status or 'пустой'
                self.stdout.write(f'- {streamer.vid} (статус: {current_status})')
            return
        
        # Обновляем статусы
        updated_count = 0
        for streamer in problematic_streamers:
            old_status = streamer.status or 'пустой'
            streamer.status = 'inactive'
            streamer.save()
            self.stdout.write(
                self.style.SUCCESS(f'Обновлен {streamer.vid}: {old_status} -> inactive')
            )
            updated_count += 1
        
        self.stdout.write(
            self.style.SUCCESS(f'Успешно обновлено {updated_count} стримеров')
        ) 