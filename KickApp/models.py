from django.db import models
from django.contrib.auth import get_user_model
import requests
import asyncio
from ProxyApp.models import Proxy
from django.db.models.signals import post_save
from django.dispatch import receiver
import datetime
import os
# from .playwright_utils import playwright_login_and_save_storage_state
import threading
from concurrent.futures import ThreadPoolExecutor
from asgiref.sync import sync_to_async
from django.utils import timezone

# Create your models here.

class KickAccount(models.Model):
    """
    Модель аккаунта Kick
    """
    login = models.CharField(max_length=100, unique=True)
    token = models.CharField(max_length=200)
    proxy = models.ForeignKey('ProxyApp.Proxy', null=True, blank=True, on_delete=models.SET_NULL)
    
    # Владелец аккаунта (кто создал/добавил)
    owner = models.ForeignKey(get_user_model(), on_delete=models.CASCADE, related_name='owned_kick_accounts', 
                             verbose_name='Владелец', null=True, blank=True)
    
    # Пользователи, которым назначен этот аккаунт (многие ко многим)
    assigned_users = models.ManyToManyField(get_user_model(), through='KickAccountAssignment', 
                                          through_fields=('kick_account', 'user'),
                                          related_name='assigned_kick_accounts', verbose_name='Назначенные пользователи')
    
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    status = models.CharField(max_length=16, choices=[('active', 'Active'), ('inactive', 'Inactive')], default='active')
    session_token = models.CharField(max_length=400, blank=True, null=True)
    storage_state_path = models.CharField(max_length=400, blank=True, null=True, help_text='Путь к storage_state playwright')
    password = models.CharField(max_length=200, blank=True, null=True, help_text='Пароль от аккаунта Kick (используется только для playwright-логина)')
    storage_state_status = models.CharField(max_length=16, blank=True, null=True, default='pending', help_text='Статус генерации storage_state: pending/success/fail')
    
    class Meta:
        verbose_name = 'Kick аккаунт'
        verbose_name_plural = 'Kick аккаунты'
    
    def __str__(self):
        return self.login
    
    def get_all_users(self):
        """Получить всех пользователей, связанных с этим аккаунтом"""
        return self.assigned_users.all()
    
    def is_assigned_to_user(self, user):
        """Проверить, назначен ли аккаунт пользователю"""
        return self.assigned_users.filter(id=user.id).exists()


class KickAccountAssignment(models.Model):
    """
    Связь между Kick аккаунтом и пользователем с дополнительной информацией
    """
    ASSIGNMENT_TYPE_CHOICES = [
        ('admin_assigned', 'Назначен админом'),
    ]
    
    kick_account = models.ForeignKey(KickAccount, on_delete=models.CASCADE, related_name='assignments')
    user = models.ForeignKey(get_user_model(), on_delete=models.CASCADE, related_name='kick_account_assignments')
    
    # Кто назначил (админ или сам пользователь)
    assigned_by = models.ForeignKey(get_user_model(), on_delete=models.CASCADE, related_name='kick_accounts_assigned_by_me')
    
    # Тип назначения
    assignment_type = models.CharField(max_length=20, choices=ASSIGNMENT_TYPE_CHOICES, default='admin_assigned')
    
    # Дата назначения
    assigned_at = models.DateTimeField(auto_now_add=True)
    
    # Активно ли назначение
    is_active = models.BooleanField(default=True)
    
    # Дополнительные поля
    notes = models.TextField(blank=True, verbose_name='Заметки')
    
    class Meta:
        verbose_name = 'Назначение Kick аккаунта'
        verbose_name_plural = 'Назначения Kick аккаунтов'
        unique_together = ['kick_account', 'user']
    
    def __str__(self):
        return f"{self.kick_account.login} -> {self.user.username}"
    
    @property
    def can_user_edit(self):
        """Может ли пользователь редактировать это назначение"""
        # Обычные пользователи не могут редактировать назначения
        return False

    async def acheck_kick_account_valid(self, proxy=None):
        """
        Асинхронная проверка валидности аккаунта Kick через Playwright (или fallback requests)
        """
        try:
            from .playwright_utils import validate_kick_account_playwright
            proxy_url = proxy if proxy else (getattr(self.proxy, 'url', None) if self.proxy else None)
            token = str(self.token) if self.token else None
            session_token = str(self.session_token) if self.session_token else None
            is_valid = await validate_kick_account_playwright(token, session_token, proxy_url)
            if is_valid:
                if self.status != 'active':
                    self.status = 'active'
                    await sync_to_async(self.save)(update_fields=['status'])
                return True
            else:
                if self.status != 'inactive':
                    self.status = 'inactive'
                    await sync_to_async(self.save)(update_fields=['status'])
                return False
        except Exception as e:
            print(f"Playwright validation failed, falling back to requests: {e}")
            return await sync_to_async(self._check_kick_account_valid_requests)()
    
    def _check_kick_account_valid_requests(self):
        """
        Fallback валидация аккаунта через requests (может не работать из-за Cloudflare)
        """
        try:
            # Настройка прокси
            proxies = {}
            proxy_url = getattr(self.proxy, 'url', None) if self.proxy else None
            if proxy_url:
                if proxy_url.startswith(('http://', 'https://')):
                    proxies = {
                        'http': proxy_url,
                        'https': proxy_url
                    }
                # SOCKS прокси поддерживаются через httpx[socks]
                elif proxy_url.startswith('socks'):
                    proxies = {
                        'http': proxy_url,
                        'https': proxy_url
                    }
            
            headers = {
                'Accept': 'application/json, text/plain, */*',
                'Accept-Language': 'en-US,en;q=0.9',
                'Content-Type': 'application/json',
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            }
            
            if self.token:
                headers['Authorization'] = f'Bearer {self.token}'
            
            # Пробуем разные API эндпоинты для валидации
            api_endpoints = [
                'https://kick.com/api/v1/user',
                'https://kick.com/api/v1/user/me',
                'https://kick.com/api/v2/user/me'
            ]
            
            for api_url in api_endpoints:
                try:
                    response = requests.get(
                        api_url,
                        headers=headers,
                        proxies=proxies,
                        timeout=10,
                        verify=False
                    )
                    
                    if response.status_code == 200:
                        # Проверяем, что ответ содержит данные пользователя
                        try:
                            data = response.json()
                            if isinstance(data, dict) and ('username' in data or 'user_id' in data or 'id' in data):
                                print(f"Account validation successful via {api_url}")
                                return True
                        except:
                            # Если не JSON, проверяем текст
                            content = response.text.lower()
                            if 'username' in content or 'user_id' in content or '"id"' in content:
                                print(f"Account validation successful via {api_url}")
                                return True
                                
                except requests.exceptions.RequestException as e:
                    print(f"Failed to validate via {api_url}: {e}")
                    continue
            
            # Если API не работает, пробуем через основную страницу
            try:
                response = requests.get(
                    'https://kick.com/',
                    headers=headers,
                    proxies=proxies,
                    timeout=10,
                    verify=False
                )
                
                if response.status_code == 200:
                    content = response.text.lower()
                    # Ищем признаки авторизации
                    auth_indicators = ['dashboard', 'profile', 'user-menu', 'go live', 'settings']
                    
                    for indicator in auth_indicators:
                        if indicator in content:
                            print(f"Account validation successful via page content indicator: {indicator}")
                            return True
                            
            except requests.exceptions.RequestException as e:
                print(f"Failed to validate via main page: {e}")
            
            print("Account validation failed - no valid indicators found")
            return False
            
        except Exception as e:
            print(f"Error during account validation: {e}")
            return False

STORAGE_STATE_DIR = 'storage_states'
STORAGE_STATE_MAX_AGE_DAYS = 7

def is_storage_state_fresh(path):
    try:
        mtime = os.path.getmtime(path)
        age = (datetime.datetime.now() - datetime.datetime.fromtimestamp(mtime)).days
        return age < STORAGE_STATE_MAX_AGE_DAYS
    except Exception:
        return False

def async_generate_storage_state(instance_id):
    from django.apps import apps
    KickAccount = apps.get_model('KickApp', 'KickAccount')
    acc = KickAccount.objects.get(id=instance_id)
    storage_state_path = f'storage_states/{acc.login}.json'
    acc.storage_state_status = 'pending'
    acc.save(update_fields=["storage_state_status"])
    import asyncio
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    # try:
    #     result = loop.run_until_complete(
    #         playwright_login_and_save_storage_state(
    #             login=acc.login,
    #             password=acc.password,
    #             storage_state_path=storage_state_path,
    #             proxy_url=str(getattr(acc.proxy, 'url', '')) if acc.proxy else ""
    #         )
    #     )
    # finally:
    #     loop.close()
    # if result:
    #     acc.storage_state_path = storage_state_path
    #     acc.storage_state_status = 'success'
    #     acc.save(update_fields=["storage_state_path", "storage_state_status"])
    # else:
    #     acc.storage_state_status = 'fail'
    #     acc.save(update_fields=["storage_state_status"])
    
    # Временно отключаем playwright авторизацию
    acc.storage_state_status = 'disabled'
    acc.save(update_fields=["storage_state_status"])

storage_state_executor = ThreadPoolExecutor(max_workers=2)

@receiver(post_save, sender=KickAccount)
def ensure_storage_state(sender, instance, created, **kwargs):
    """
    Обеспечивает генерацию storage_state для новых аккаунтов
    """
    if created and not instance.storage_state_path:
        # Запускаем генерацию в отдельном потоке
        threading.Thread(target=async_generate_storage_state, args=(instance.id,), daemon=True).start()


class AutoResponse(models.Model):
    """
    Модель для автоматических ответов к стримерам
    """
    RESPONSE_TYPE_CHOICES = [
        ('chat', 'Чат сообщение'),
        ('donation', 'Донат сообщение'),
        ('subscription', 'Подписка сообщение'),
    ]
    
    # Стример, к которому относится ответ
    streamer_vid = models.CharField(max_length=100, verbose_name='VID стримера')
    
    # Тип ответа
    response_type = models.CharField(max_length=20, choices=RESPONSE_TYPE_CHOICES, default='chat', verbose_name='Тип ответа')
    
    # Текст ответа
    message = models.TextField(verbose_name='Сообщение')
    
    # Частота отправки (в секундах)
    frequency = models.IntegerField(default=60, verbose_name='Частота отправки (сек)')
    
    # Активен ли ответ
    is_active = models.BooleanField(default=True, verbose_name='Активен')
    
    # Приоритет (чем выше, тем важнее)
    priority = models.IntegerField(default=1, verbose_name='Приоритет')
    
    # Время создания и обновления
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Создан')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Обновлен')
    
    # Кто создал
    created_by = models.ForeignKey(get_user_model(), on_delete=models.CASCADE, verbose_name='Создан пользователем')
    
    class Meta:
        verbose_name = 'Автоматический ответ'
        verbose_name_plural = 'Автоматические ответы'
        ordering = ['-priority', '-created_at']
        unique_together = ['streamer_vid', 'response_type', 'message']
    
    def __str__(self):
        return f"{self.streamer_vid} - {self.get_response_type_display()} - {self.message[:50]}"


class StreamerStatus(models.Model):
    """
    Модель для отслеживания статуса стримеров
    """
    STATUS_CHOICES = [
        ('active', 'Активен'),
        ('inactive', 'Неактивен'),
        ('unknown', 'Неизвестно'),
    ]
    
    # VID стримера
    vid = models.CharField(max_length=100, unique=True, verbose_name='VID стримера')
    
    # Статус стримера
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='unknown', verbose_name='Статус')
    
    # Последнее обновление статуса
    last_updated = models.DateTimeField(auto_now=True, verbose_name='Последнее обновление')
    
    # Дополнительная информация
    order_id = models.IntegerField(null=True, blank=True, verbose_name='ID заказа')
    
    # Пользователь, который будет отправлять сообщения к этому стримеру
    assigned_user = models.ForeignKey(get_user_model(), on_delete=models.SET_NULL, null=True, blank=True, 
                                    verbose_name='Назначенный пользователь')
    
    class Meta:
        verbose_name = 'Статус стримера'
        verbose_name_plural = 'Статусы стримеров'
        ordering = ['-last_updated']
    
    def __str__(self):
        return f"{self.vid} - {self.get_status_display()}"
    
    @property
    def is_streaming(self):
        """Проверяет, стримит ли стример"""
        return self.status == 'active'
    
    def get_responses(self):
        """Получает все активные ответы для этого стримера"""
        return AutoResponse.objects.filter(
            streamer_vid=self.vid,
            is_active=True
        ).order_by('-priority')
    
    def get_messages(self):
        """Получает сообщения для этого стримера из Supabase"""
        return StreamerMessage.objects.filter(
            streamer=self,
            is_active=True
        ).order_by('?')  # Случайный порядок для разнообразия


class StreamerMessage(models.Model):
    """
    Модель для хранения сообщений стримеров из Supabase
    """
    # Связь со стримером
    streamer = models.ForeignKey(StreamerStatus, on_delete=models.CASCADE, related_name='messages', verbose_name='Стример', null=True, blank=True)
    
    # Текст сообщения
    message = models.TextField(verbose_name='Сообщение')
    
    # Время создания
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Создано')
    
    # Время последней отправки
    last_sent = models.DateTimeField(null=True, blank=True, verbose_name='Последняя отправка')
    
    # Активно ли сообщение
    is_active = models.BooleanField(default=True, verbose_name='Активно')
    
    class Meta:
        verbose_name = 'Сообщение стримера'
        verbose_name_plural = 'Сообщения стримеров'
        ordering = ['-created_at']
        unique_together = ['streamer', 'message']
    
    def __str__(self):
        return f"{self.streamer.vid if self.streamer else 'Unknown'}: {self.message[:50]}..."


class HydraBotSettings(models.Model):
    """
    Настройки бота "Гидра" для автоматической отправки сообщений
    """
    # Включен ли бот
    is_enabled = models.BooleanField(default=True, verbose_name='Бот включен')
    
    # Интервал между сообщениями (в секундах)
    message_interval = models.IntegerField(default=1, verbose_name='Интервал между сообщениями (сек)',
                                        help_text='Интервал между отдельными сообщениями в одном цикле')
    
    # Интервал между циклами (в секундах) - новый цикл = отправка всех сообщений
    cycle_interval = models.IntegerField(default=3, verbose_name='Интервал между циклами (сек)',
                                       help_text='Интервал между полными циклами отправки всех сообщений')
    
    # Интервал синхронизации с Supabase (в секундах)
    sync_interval = models.IntegerField(default=180, verbose_name='Интервал синхронизации (сек)')
    
    # Максимальное количество одновременных отправок
    max_concurrent_sends = models.IntegerField(default=1000, verbose_name='Макс. одновременных отправок')
    
    # Минимальный интервал между отправкой одного сообщения (в секундах)
    min_message_interval = models.IntegerField(default=300, verbose_name='Мин. интервал между сообщениями (сек)')
    
    # Время создания и обновления
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Создано')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Обновлено')
    
    class Meta:
        verbose_name = 'Настройки бота Гидра'
        verbose_name_plural = 'Настройки бота Гидра'
    
    def __str__(self):
        status = "✅ Включен" if self.is_enabled else "❌ Выключен"
        return f"Гидра: {status}"
    
    @classmethod
    def get_settings(cls):
        """Получает настройки бота (создает если не существует)"""
        settings, created = cls.objects.get_or_create(
            id=1,
            defaults={
                'is_enabled': True,
                'message_interval': 1,
                'cycle_interval': 3,  # 3 секунды между циклами
                'sync_interval': 180,
                'max_concurrent_sends': 1000,
                'min_message_interval': 300
            }
        )
        return settings

@receiver(post_save, sender=HydraBotSettings)
def restart_hydra_on_settings_change(sender, instance, created, **kwargs):
    """
    Перезапускает бота "Гидра" при изменении настроек
    """
    # Не срабатываем при создании новой записи
    if created:
        return
        
    try:
        # Импортируем здесь чтобы избежать циклических импортов
        from .auto_message_sender import restart_auto_messaging
        
        # Запускаем перезапуск в отдельном потоке
        def restart_in_thread():
            import time
            time.sleep(2)  # Небольшая пауза для применения изменений
            
            # Проверяем актуальные настройки из базы данных
            instance.refresh_from_db()
            
            if instance.is_enabled:
                print("🚀 Включаем бота Гидру...")
                restart_auto_messaging()
            else:
                print("🛑 Отключаем бота Гидру...")
                from .auto_message_sender import stop_auto_messaging
                stop_auto_messaging()
        
        threading.Thread(target=restart_in_thread, daemon=True).start()
        
    except Exception as e:
        print(f"Ошибка перезапуска Гидры: {e}")
