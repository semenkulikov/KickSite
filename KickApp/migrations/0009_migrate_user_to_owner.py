from django.db import migrations

def migrate_user_to_owner(apps, schema_editor):
    """
    Переносим данные из старого поля user в новое поле owner
    """
    KickAccount = apps.get_model('KickApp', 'KickAccount')
    
    # Получаем все аккаунты, у которых есть user но нет owner
    accounts = KickAccount.objects.filter(owner__isnull=True)
    
    for account in accounts:
        # Если есть старое поле user, переносим его в owner
        if hasattr(account, 'user') and account.user:
            account.owner = account.user
            account.save(update_fields=['owner'])

def reverse_migrate_user_to_owner(apps, schema_editor):
    """
    Обратная миграция (не используется, но нужна для совместимости)
    """
    pass

class Migration(migrations.Migration):

    dependencies = [
        ('KickApp', '0008_alter_kickaccount_options_remove_kickaccount_user_and_more'),
    ]

    operations = [
        migrations.RunPython(migrate_user_to_owner, reverse_migrate_user_to_owner),
    ] 