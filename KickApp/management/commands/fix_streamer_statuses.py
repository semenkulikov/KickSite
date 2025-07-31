from django.core.management.base import BaseCommand
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
        
        # Находим стримеров со статусом 'unknown'
        unknown_streamers = StreamerStatus.objects.filter(status='unknown')
        
        if not unknown_streamers:
            self.stdout.write(
                self.style.SUCCESS('Нет стримеров со статусом "unknown"')
            )
            return
        
        self.stdout.write(f'Найдено {unknown_streamers.count()} стримеров со статусом "unknown"')
        
        if dry_run:
            self.stdout.write('Стримеры которые будут изменены:')
            for streamer in unknown_streamers:
                self.stdout.write(f'- {streamer.vid} (статус: {streamer.status})')
            return
        
        # Обновляем статусы
        updated_count = 0
        for streamer in unknown_streamers:
            old_status = streamer.status
            streamer.status = 'inactive'
            streamer.save()
            self.stdout.write(
                self.style.SUCCESS(f'Обновлен {streamer.vid}: {old_status} -> inactive')
            )
            updated_count += 1
        
        self.stdout.write(
            self.style.SUCCESS(f'Успешно обновлено {updated_count} стримеров')
        ) 