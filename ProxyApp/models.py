from typing import Union, Any
from django.db import models
from ServiceApp.Validators import validate_socks5_address
from ProxyApp.ModelsFunctional import ModelStatusManager, ModelTwitchAccountManager


class Proxy(models.Model, ModelStatusManager, ModelTwitchAccountManager):
    url = models.CharField(verbose_name='Url', max_length=100, validators=[validate_socks5_address],
                           help_text='socks5://«user»:«pass»@«host»:«port»', unique=True)
    status = models.BooleanField(verbose_name='Status', default=True, editable=False)

    @classmethod
    def get_valid_twitch_free_proxy(cls) -> Union[None, Any]:
        """Получает первый доступный свободный прокси"""
        return cls.objects.filter(status=True, twitch_account=None).first()

    @classmethod
    def get_free_proxy_count(cls) -> int:
        """Подсчитывает количество свободных прокси"""
        return cls.objects.filter(status=True, twitch_account=None).count()

    @classmethod
    def assign_proxies_to_accounts_without_proxy(cls):
        """Назначает прокси всем аккаунтам без прокси"""
        from TwitchApp.models import TwitchAccount
        
        accounts_without_proxy = TwitchAccount.objects.filter(proxy=None)
        free_proxies = cls.objects.filter(status=True, twitch_account=None)
        
        assignments = []
        for account, proxy in zip(accounts_without_proxy, free_proxies):
            account.proxy = proxy
            assignments.append(account)
        
        # Массовое сохранение для эффективности
        TwitchAccount.objects.bulk_update(assignments, ['proxy'])
        return len(assignments)

    def __str__(self) -> str:
        return f'{self.url} - {"valid" if self.status else "invalid"}'

    class Meta:
        verbose_name = 'Proxy'
        verbose_name_plural = 'Proxies'
