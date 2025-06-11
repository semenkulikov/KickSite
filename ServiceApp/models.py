from django.db import models
from django.contrib.auth.models import AbstractUser

# Create your models here.
from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin


class User(AbstractUser, PermissionsMixin):
    """
    A user without rights is an ordinary client. With the addition of permissions,
    the corresponding functionality becomes available
    """

    twitch_account = models.ManyToManyField('TwitchApp.TwitchAccount', related_name="user", blank=True)

    # objects = UserManager()
    USERNAME_FIELD = 'username'
    # any required fields besides username and password
    REQUIRED_FIELDS = []

    class Meta:
        verbose_name = 'User'
        verbose_name_plural = 'Users'
        permissions = [
            ("twitch_chatter", "Can use Twitch Chat"),
            ("kick_chatter", "Can use Kick Chat"),
        ]

    def __str__(self):
        return f'{self.username}'
