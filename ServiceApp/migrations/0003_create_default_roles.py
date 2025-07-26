from django.db import migrations

def create_default_roles(apps, schema_editor):
    """
    Создаем роли по умолчанию
    """
    UserRole = apps.get_model('ServiceApp', 'UserRole')
    
    # Создаем роли
    super_admin_role, created = UserRole.objects.get_or_create(
        name='super_admin',
        defaults={'description': 'Супер администратор с полными правами'}
    )
    
    admin_role, created = UserRole.objects.get_or_create(
        name='admin',
        defaults={'description': 'Администратор с правами управления пользователями и аккаунтами'}
    )
    
    user_role, created = UserRole.objects.get_or_create(
        name='user',
        defaults={'description': 'Обычный пользователь'}
    )
    
    # Назначаем супер админа первому пользователю (если есть)
    User = apps.get_model('ServiceApp', 'User')
    if User.objects.exists():
        first_user = User.objects.first()
        if not first_user.role:
            first_user.role = super_admin_role
            first_user.save(update_fields=['role'])

def reverse_create_default_roles(apps, schema_editor):
    """
    Удаляем роли (не рекомендуется)
    """
    UserRole = apps.get_model('ServiceApp', 'UserRole')
    UserRole.objects.all().delete()

class Migration(migrations.Migration):

    dependencies = [
        ('ServiceApp', '0002_userrole_alter_user_options_user_phone_user_telegram_and_more'),
    ]

    operations = [
        migrations.RunPython(create_default_roles, reverse_create_default_roles),
    ] 