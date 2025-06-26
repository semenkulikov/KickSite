from django.db import models
from django.contrib.auth import get_user_model
import requests
from ProxyApp.models import Proxy

# Create your models here.

class KickAccount(models.Model):
    login = models.CharField(max_length=100, unique=True)
    token = models.CharField(max_length=200)
    proxy = models.ForeignKey('ProxyApp.Proxy', null=True, blank=True, on_delete=models.SET_NULL)
    user = models.ForeignKey(get_user_model(), on_delete=models.CASCADE, related_name='kick_accounts')
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    status = models.CharField(max_length=16, choices=[('active', 'Active'), ('inactive', 'Inactive')], default='inactive')
    session_token = models.CharField(max_length=300, blank=True, null=True)

    def __str__(self):
        return self.login

    def check_kick_account_valid(self):
        proxies = None
        proxy_url = getattr(self.proxy, 'url', None)
        proxy_failed = False
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
                proxy_obj.status = False
                proxy_obj.save(update_fields=['status'])
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
