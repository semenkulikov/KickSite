from django.core.management.base import BaseCommand
from ServiceApp.models import User
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from KickApp.models import KickAccount, KickAccountAssignment


class Command(BaseCommand):
    help = 'Обеспечивает наличие прав на модели KickApp для всех админов'

    def handle(self, *args, **options):
        try:
            # Получаем всех админов
            admins = User.objects.filter(role__name__in=['super_admin', 'admin'])
            self.stdout.write(f'Found {admins.count()} admins to update')
            
            # Получаем content types для моделей KickApp
            kick_ct = ContentType.objects.get_for_model(KickAccount)
            kick_assign_ct = ContentType.objects.get_for_model(KickAccountAssignment)
            
            # Получаем все права для этих моделей
            permissions = Permission.objects.filter(
                content_type__in=[kick_ct, kick_assign_ct]
            )
            
            self.stdout.write(f'Found {permissions.count()} KickApp permissions')
            
            # Обновляем права для каждого админа
            for admin in admins:
                self.stdout.write(f'Updating permissions for {admin.username} (role: {admin.role.name})')
                
                # Добавляем права пользователю
                admin.user_permissions.add(*permissions)
                
                # Проверяем права
                user_permissions = admin.get_all_permissions()
                self.stdout.write(f'  - {admin.username} now has {len(user_permissions)} total permissions')
            
            self.stdout.write(
                self.style.SUCCESS('Successfully updated all admin permissions!')
            )
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Error: {e}')
            ) 