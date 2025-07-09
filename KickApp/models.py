from django.db import models
from django.contrib.auth import get_user_model
import requests
import asyncio
from ProxyApp.models import Proxy
from django.db.models.signals import post_save
from django.dispatch import receiver
import datetime
import os
from .playwright_utils import playwright_login_and_save_storage_state

# Create your models here.

class KickAccount(models.Model):
    """
    Модель аккаунта Kick
    """
    login = models.CharField(max_length=100, unique=True)
    token = models.CharField(max_length=200)
    proxy = models.ForeignKey('ProxyApp.Proxy', null=True, blank=True, on_delete=models.SET_NULL)
    user = models.ForeignKey(get_user_model(), on_delete=models.CASCADE, related_name='kick_accounts')
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    status = models.CharField(max_length=16, choices=[('active', 'Active'), ('inactive', 'Inactive')], default='active')
    session_token = models.CharField(max_length=400, blank=True, null=True)
    storage_state_path = models.CharField(max_length=400, blank=True, null=True, help_text='Путь к storage_state playwright')
    password = models.CharField(max_length=200, blank=True, null=True, help_text='Пароль от аккаунта Kick (используется только для playwright-логина)')
    def __str__(self):
        return self.login

    def check_kick_account_valid(self):
        """
        Проверка валидности аккаунта Kick через Playwright
        Fallback на requests если Playwright не работает
        """
        try:
            # Пробуем через Playwright
            from .playwright_utils import validate_kick_account_playwright
            
            proxy_url = getattr(self.proxy, 'url', None) if self.proxy else None
            token = str(self.token) if self.token else None
            session_token = str(self.session_token) if self.session_token else None
            
            # Запускаем async функцию в sync контексте
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            
            is_valid = loop.run_until_complete(
                validate_kick_account_playwright(token, session_token, proxy_url)
            )
            
            if is_valid:
                if self.status != 'active':
                    self.status = 'active'
                    self.save(update_fields=['status'])
                return True
            else:
                if self.status != 'inactive':
                    self.status = 'inactive'
                    self.save(update_fields=['status'])
                return False
                
        except Exception as e:
            # Fallback на старый метод через requests
            print(f"Playwright validation failed, falling back to requests: {e}")
            return self._check_kick_account_valid_requests()
    
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

@receiver(post_save, sender=KickAccount)
def ensure_storage_state(sender, instance, created, **kwargs):
    # Оптимизация: если нет логина или пароля — ничего не делаем
    if not instance.login or not instance.password:
        return
    storage_state_path = instance.storage_state_path
    if not storage_state_path:
        storage_state_path = f'{STORAGE_STATE_DIR}/{instance.login}.json'
    # Проверяем свежесть storage_state
    if not os.path.exists(storage_state_path) or not is_storage_state_fresh(storage_state_path):
        print(f'[KickAccount] Creating/updating storage_state for {instance.login}')
        loop = asyncio.get_event_loop()
        try:
            result = loop.run_until_complete(
                playwright_login_and_save_storage_state(
                    login=instance.login,
                    password=instance.password,
                    storage_state_path=storage_state_path,
                    proxy_url=str(getattr(instance.proxy, 'url', '')) if instance.proxy else ""
                )
            )
            if result:
                instance.storage_state_path = storage_state_path
                instance.save(update_fields=['storage_state_path'])
                print(f'[KickAccount] storage_state saved: {storage_state_path}')
            else:
                print(f'[KickAccount] Failed to create storage_state for {instance.login}')
        except Exception as e:
            print(f'[KickAccount] Exception in storage_state creation: {e}')
