from typing import Union, Any
from django.db import models
from ServiceApp.Validators import validate_socks5_address
from ProxyApp.ModelsFunctional import ModelStatusManager


class Proxy(models.Model, ModelStatusManager):
    url = models.CharField(verbose_name='Url', max_length=100, validators=[validate_socks5_address],
                           help_text='socks5://«user»:«pass»@«host»:«port»', unique=True)
    status = models.BooleanField(verbose_name='Status', default=True, editable=False)

    def __str__(self) -> str:
        return f'{self.url} - {"valid" if self.status else "invalid"}'

    class Meta:
        verbose_name = 'Proxy'
        verbose_name_plural = 'Proxies'
