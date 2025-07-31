from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from KickApp.models import StreamerStatus, KickAccount, KickAccountAssignment
import random

User = get_user_model()

class Command(BaseCommand):
    help = 'Назначает пользователей к стримерам для работы гидры'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Принудительно переназначить пользователей',
        )
        parser.add_argument(
            '--user',
            type=str,
            help='Конкретный пользователь для назначения',
        )

    def handle(self, *args, **options):
        force = options['force']
        specific_user = options['user']
        
        # Получаем активных пользователей с аккаунтами
        users_with_accounts = []
        
        if specific_user:
            try:
                user = User.objects.get(username=specific_user)
                if user.assigned_kick_accounts.exists():
                    users_with_accounts.append(user)
                else:
                    self.stdout.write(
                        self.style.ERROR(f'Пользователь {specific_user} не имеет назначенных аккаунтов')
                    )
                    return
            except User.DoesNotExist:
                self.stdout.write(
                    self.style.ERROR(f'Пользователь {specific_user} не найден')
                )
                return
        else:
            # Получаем всех пользователей с назначенными аккаунтами
            users_with_accounts = list(User.objects.filter(
                assigned_kick_accounts__isnull=False
            ).distinct())
        
        if not users_with_accounts:
            self.stdout.write(
                self.style.ERROR('Нет пользователей с назначенными аккаунтами')
            )
            return
        
        # Получаем активных стримеров без назначенных пользователей
        streamers_without_users = StreamerStatus.objects.filter(
            status='active',
            assigned_user__isnull=True
        )
        
        if not streamers_without_users:
            self.stdout.write(
                self.style.SUCCESS('Все активные стримеры уже имеют назначенных пользователей')
            )
            return
        
        self.stdout.write(f'Найдено {len(streamers_without_users)} стримеров без назначенных пользователей')
        self.stdout.write(f'Доступно {len(users_with_accounts)} пользователей с аккаунтами')
        
        assigned_count = 0
        
        for streamer in streamers_without_users:
            # Выбираем случайного пользователя
            user = random.choice(users_with_accounts)
            
            # Проверяем, не назначен ли уже этот пользователь к другому стримеру
            if not force and StreamerStatus.objects.filter(assigned_user=user).exists():
                self.stdout.write(f'Пользователь {user.username} уже назначен к другому стримеру, пропускаем')
                continue
            
            # Назначаем пользователя к стримеру
            streamer.assigned_user = user
            streamer.save()
            
            self.stdout.write(
                self.style.SUCCESS(f'Назначен пользователь {user.username} к стримеру {streamer.vid}')
            )
            assigned_count += 1
        
        self.stdout.write(
            self.style.SUCCESS(f'Успешно назначено {assigned_count} пользователей к стримерам')
        ) 