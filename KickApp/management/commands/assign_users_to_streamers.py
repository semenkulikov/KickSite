from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from KickApp.models import StreamerStatus, KickAccount, KickAccountAssignment
from KickApp.models import KickAccount

User = get_user_model()

class Command(BaseCommand):
    help = 'Создает отдельного пользователя для каждого стримера с именем стримера'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Принудительно переназначить пользователей',
        )
        parser.add_argument(
            '--user',
            type=str,
            help='Конкретный пользователь для назначения (не используется в новой логике)',
        )

    def handle(self, *args, **options):
        force = options['force']
        
        # Получаем всех стримеров без назначенных пользователей (активных и неактивных)
        streamers_without_users = StreamerStatus.objects.filter(
            assigned_user__isnull=True
        )
        
        if not streamers_without_users:
            self.stdout.write(
                self.style.SUCCESS('Все стримеры уже имеют назначенных пользователей')
            )
            return
        
        self.stdout.write(f'Найдено {len(streamers_without_users)} стримеров без назначенных пользователей')
        
        assigned_count = 0
        
        for streamer in streamers_without_users:
            streamer_name = streamer.vid
            
            # Проверяем, существует ли уже пользователь с таким именем
            user, created = User.objects.get_or_create(
                username=streamer_name,
                defaults={
                    'email': f'{streamer_name}@kick.com',
                    'first_name': streamer_name,
                    'last_name': 'Streamer'
                }
            )
            
            if created:
                self.stdout.write(
                    self.style.SUCCESS(f'Создан новый пользователь {streamer_name}')
                )
            else:
                self.stdout.write(
                    self.style.WARNING(f'Пользователь {streamer_name} уже существует')
                )
            
            # Проверяем, не назначен ли уже этот пользователь к другому стримеру
            if not force and StreamerStatus.objects.filter(assigned_user=user).exclude(id=streamer.id).exists():
                self.stdout.write(f'Пользователь {user.username} уже назначен к другому стримеру, пропускаем')
                continue
            
            # Назначаем пользователя к стримеру
            streamer.assigned_user = user
            streamer.save()
            
            # Назначаем все доступные Kick аккаунты к этому пользователю
            available_accounts = KickAccount.objects.filter(
                status='active',
                assignments__isnull=True  # Аккаунты без назначений
            )
            
            accounts_assigned = 0
            for account in available_accounts:
                assignment, created = KickAccountAssignment.objects.get_or_create(
                    kick_account=account,
                    user=user,
                    defaults={
                        'assignment_type': 'auto',
                        'assigned_by': user
                    }
                )
                if created:
                    accounts_assigned += 1
            
            self.stdout.write(
                self.style.SUCCESS(f'Назначен пользователь {user.username} к стримеру {streamer.vid} (добавлено {accounts_assigned} аккаунтов)')
            )
            assigned_count += 1
        
        self.stdout.write(
            self.style.SUCCESS(f'Успешно назначено {assigned_count} пользователей к стримерам')
        ) 