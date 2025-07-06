from django.db import models
from django.contrib.auth import get_user_model
import requests
import asyncio
from ProxyApp.models import Proxy

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
            
            proxy_url = getattr(self.proxy, 'url', None)
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
        Fallback метод валидации через requests (может не работать из-за Cloudflare)
        """
        proxies = None
        proxy_url = getattr(self.proxy, 'url', None)
        if proxy_url:
            proxies = {
                "http": proxy_url,
                "https": proxy_url,
            }
        try:
            if self.session_token:
                cookies = {'__Secure-next-auth.session-token': str(self.session_token)}
                resp = requests.get('https://kick.com/api/v1/user/me', cookies=cookies, timeout=5, proxies=proxies)
            else:
                token = str(self.token)
                headers = {'Authorization': f'Bearer {token}'}
                resp = requests.get('https://kick.com/api/v1/user/me', headers=headers, timeout=5, proxies=proxies)
            if resp.status_code == 200:
                if self.status != 'active':
                    self.status = 'active'
                    self.save(update_fields=['status'])
                return True
            else:
                if self.status != 'inactive':
                    self.status = 'inactive'
                    self.save(update_fields=['status'])
                return False
        except Exception:
            # Если был прокси — помечаем его как невалидный, но пробуем без прокси
            proxy_obj = self.proxy
            if proxy_obj:
                # Пробуем ещё раз без прокси
                try:
                    if self.session_token:
                        cookies = {'__Secure-next-auth.session-token': str(self.session_token)}
                        resp = requests.get('https://kick.com/api/v1/user/me', cookies=cookies, timeout=5)
                    else:
                        token = str(self.token)
                        headers = {'Authorization': f'Bearer {token}'}
                        resp = requests.get('https://kick.com/api/v1/user/me', headers=headers, timeout=5)
                    if resp.status_code == 200:
                        if self.status != 'active':
                            self.status = 'active'
                            self.save(update_fields=['status'])
                        return True
                    else:
                        if self.status != 'inactive':
                            self.status = 'inactive'
                            self.save(update_fields=['status'])
                        return False
                except Exception:
                    if self.status != 'inactive':
                        self.status = 'inactive'
                        self.save(update_fields=['status'])
                    return False
            else:
                if self.status != 'inactive':
                    self.status = 'inactive'
                    self.save(update_fields=['status'])
                return False
