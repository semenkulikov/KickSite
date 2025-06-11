from django.db import models
from django.db.transaction import atomic
from ServiceApp.Validators import validate_twitch_token
from ProxyApp.models import Proxy


class TwitchAccount(models.Model):
    login = models.CharField(verbose_name='Login', max_length=100, unique=True)
    token = models.CharField(verbose_name='Token', max_length=100, validators=[validate_twitch_token],
                             help_text='oauth:«token»')
    proxy = models.OneToOneField(Proxy, on_delete=models.SET_NULL,
                                 related_name='twitch_account', blank=True, null=True)

    @property
    def has_proxy(self) -> bool:
        return self.proxy is not None

    @property
    def has_not_proxy(self) -> bool:
        return self.proxy is None

    @atomic
    def update_self_proxy(self):
        free_proxy = Proxy.get_valid_twitch_free_proxy()
        if free_proxy:
            self.proxy = free_proxy
            self.save()
        return self

    def __str__(self) -> str:
        user_names = ', '.join([u.username for u in self.user.all()])
        return f'{self.login} | {user_names} | {self.proxy is not None}'

    def save(self, *args, **kwargs):
        # Если прокси не назначен, попробуем назначить при сохранении
        if not self.proxy and not self.pk:  # Только для новых объектов
            self.proxy = Proxy.get_valid_twitch_free_proxy()
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = 'Twitch Account'
        verbose_name_plural = 'Twitch Accounts'
