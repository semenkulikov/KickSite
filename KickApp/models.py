from django.db import models
from django.contrib.auth import get_user_model

# Create your models here.

class KickAccount(models.Model):
    login = models.CharField(max_length=100, unique=True)
    token = models.CharField(max_length=200)
    proxy = models.ForeignKey('ProxyApp.Proxy', null=True, blank=True, on_delete=models.SET_NULL)
    user = models.ForeignKey(get_user_model(), on_delete=models.CASCADE, related_name='kick_accounts')
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.login
