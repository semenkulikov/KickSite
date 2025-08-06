from django.db import models
from django.contrib.auth.models import AbstractUser, Permission
from django.contrib.contenttypes.models import ContentType

# Create your models here.
from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin


class UserRole(models.Model):
    """
    Роли пользователей в системе
    """
    SUPER_ADMIN = 'super_admin'
    ADMIN = 'admin'
    USER = 'user'
    
    ROLE_CHOICES = [
        (SUPER_ADMIN, 'Супер Админ'),
        (ADMIN, 'Админ'),
        (USER, 'Пользователь'),
    ]
    
    name = models.CharField(max_length=20, choices=ROLE_CHOICES, unique=True)
    description = models.TextField(blank=True)
    
    class Meta:
        verbose_name = 'Роль пользователя'
        verbose_name_plural = 'Роли пользователей'
    
    def __str__(self):
        return self.get_name_display()


class User(AbstractUser, PermissionsMixin):
    """
    Расширенная модель пользователя с ролями
    """
    
    # Роль пользователя
    role = models.ForeignKey(UserRole, on_delete=models.SET_NULL, null=True, blank=True, 
                           related_name='users', verbose_name='Роль')
    
    # Дополнительные поля
    phone = models.CharField(max_length=20, blank=True, verbose_name='Телефон')
    telegram = models.CharField(max_length=100, blank=True, verbose_name='Telegram')
    
    USERNAME_FIELD = 'username'
    REQUIRED_FIELDS = []

    class Meta:
        verbose_name = 'Пользователь'
        verbose_name_plural = 'Пользователи'
        permissions = [
            ("twitch_chatter", "Can use Twitch Chat"),
            ("kick_chatter", "Can use Kick Chat"),
            ("manage_kick_accounts", "Can manage Kick accounts"),
            ("assign_kick_accounts", "Can assign Kick accounts to users"),
            ("view_all_kick_accounts", "Can view all Kick accounts"),
        ]

    def __str__(self):
        return f'{self.username}'
    
    def save(self, *args, **kwargs):
        # Если это новый пользователь и роль не установлена, устанавливаем USER по умолчанию
        if not self.pk and not self.role:
            default_role, created = UserRole.objects.get_or_create(name=UserRole.USER)
            self.role = default_role

        # Сохраняем оригинальные права перед изменением
        original_is_superuser = self.is_superuser
        original_is_staff = self.is_staff

        # Присваиваем права в зависимости от роли
        if self.role:
            if self.role.name == UserRole.SUPER_ADMIN:
                self.is_staff = True
                self.is_superuser = True
                self.is_active = True
            elif self.role.name == UserRole.ADMIN:
                self.is_staff = True
                self.is_superuser = False  # Админ не суперпользователь
                self.is_active = True
            else:  # UserRole.USER
                self.is_staff = False
                self.is_superuser = False
                self.is_active = True
        
        # ВАЖНО: Если пользователь уже был суперпользователем (например, через createsuperuser),
        # НЕ понижаем его права
        if original_is_superuser:
            self.is_superuser = True
            self.is_staff = True  # Суперпользователь должен быть staff
        
        # Сохраняем пользователя
        super().save(*args, **kwargs)

        # После сохранения автоматически даем права на модели KickApp для админов
        if self.role and self.role.name in [UserRole.SUPER_ADMIN, UserRole.ADMIN]:
            self._ensure_kickapp_permissions()
    
    def _ensure_kickapp_permissions(self):
        """Обеспечивает наличие прав на модели KickApp для админов"""
        try:
            from django.contrib.auth.models import Permission
            from django.contrib.contenttypes.models import ContentType
            from KickApp.models import KickAccount, KickAccountAssignment
            
            # Получаем content types для моделей KickApp
            kick_ct = ContentType.objects.get_for_model(KickAccount)
            kick_assign_ct = ContentType.objects.get_for_model(KickAccountAssignment)
            
            # Получаем content type для модели User
            user_ct = ContentType.objects.get_for_model(self.__class__)
            
            # Получаем все права для этих моделей
            permissions = Permission.objects.filter(
                content_type__in=[kick_ct, kick_assign_ct, user_ct]
            )
            
            # Добавляем права пользователю (если их еще нет)
            for permission in permissions:
                if not self.has_perm(f"{permission.content_type.app_label}.{permission.codename}"):
                    self.user_permissions.add(permission)
                    
        except Exception as e:
            # Логируем ошибку, но не прерываем сохранение
            print(f"Warning: Could not ensure KickApp permissions for {self.username}: {e}")
    
    @property
    def is_super_admin(self):
        """Проверка является ли пользователь супер админом"""
        return self.role and self.role.name == UserRole.SUPER_ADMIN
    
    @property
    def is_admin(self):
        """Проверка является ли пользователь админом (включая супер админа)"""
        return self.role and self.role.name in [UserRole.SUPER_ADMIN, UserRole.ADMIN]
    
    @property
    def is_regular_user(self):
        """Проверка является ли пользователь обычным пользователем"""
        return self.role and self.role.name == UserRole.USER
    
    def can_manage_kick_accounts(self):
        """Может ли пользователь управлять кик аккаунтами"""
        return self.is_admin or self.has_perm('ServiceApp.assign_kick_accounts')
    
    def can_view_all_kick_accounts(self):
        """Может ли пользователь просматривать все кик аккаунты"""
        return self.is_admin or self.has_perm('ServiceApp.view_all_kick_accounts')
