from django.db import models
from django.contrib.auth import get_user_model
import requests

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
        if self.session_token:
            cookies = {'__Secure-next-auth.session-token': str(self.session_token)}
            resp = requests.get('https://kick.com/api/v1/user/me', cookies=cookies, timeout=5)
        else:
            token_str = str(self.token)
            token = token_str.split('|')[0] if '|' in token_str else token_str
            headers = {'Authorization': token}
            resp = requests.get('https://kick.com/api/v1/user/me', headers=headers, timeout=5)
        try:
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
