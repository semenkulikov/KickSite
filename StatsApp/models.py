from typing import Union
from datetime import timedelta
from django.db import models
from ServiceApp.Validators import validate_statistic_data
from pytz import timezone
from django.conf import settings


class Statistic(models.Model):
    class Types(models.TextChoices):
        TWITCH: str = 'TWITCH'
        KICK: str = 'KICK'

    type = models.CharField(verbose_name='Type', max_length=100, choices=Types.choices)
    data = models.TextField(verbose_name='Data', validators=[validate_statistic_data],
                            help_text='hh:mm:ss.f DD.MM.YYYY|«twitch_channel»|«twitch_account»|a/m|«message»')
    start = models.DateTimeField(verbose_name='Start')
    end = models.DateTimeField(verbose_name='End', auto_now_add=True)
    user = models.ForeignKey('ServiceApp.User', related_name='statistics', on_delete=models.CASCADE,
                             verbose_name='User')

    @property
    def duration(self) -> timedelta:
        return self.end - self.start

    @property
    def data_count(self) -> int:
        return len(self.data.split('\n'))

    @property
    def serialized_object(self) -> dict[str, Union[str, list[dict[str, str]]]]:
        result = {'start': self.start.astimezone(timezone(settings.TIME_ZONE)).strftime('%H:%M:%S %d.%m.%Y'),
                  'end': self.end.astimezone(timezone(settings.TIME_ZONE)).strftime('%H:%M:%S %d.%m.%Y'),
                  'duration': str(self.duration).split('.')[0],
                  'messages': list()}
        for line in self.data.split('\n'):
            datetime_str, channel, account, message_type, message = line.split('|', 4)
            message_data = {'channel': channel,
                            'account': account,
                            'message_type': message_type,
                            'message': message.rstrip('\r\n')}
            result['messages'].append({'time': datetime_str, 'data': message_data})
        return result

    @property
    def serialized_data_to_js(self):
        # return "['sdfdfg43e5:dsg','dfgdf:3425|']"
        return self.serialized_object

    def __str__(self) -> str:
        return f'[{self.start.astimezone(timezone(settings.TIME_ZONE))}] {self.user.username} - {self.data_count}'

    class Meta:
        verbose_name = 'Statistic'
        verbose_name_plural = 'Statistics'
