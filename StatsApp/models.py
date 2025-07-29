from typing import Union
from datetime import timedelta
from django.db import models
from django.utils import timezone
from ServiceApp.Validators import validate_statistic_data
from pytz import timezone as pytz_timezone
from django.conf import settings
import json


class Shift(models.Model):
    """Модель для отслеживания смен пользователей"""
    user = models.ForeignKey('ServiceApp.User', related_name='shifts', on_delete=models.CASCADE, verbose_name='User')
    start_time = models.DateTimeField(verbose_name='Start Time', auto_now_add=True)
    end_time = models.DateTimeField(verbose_name='End Time', null=True, blank=True)
    is_active = models.BooleanField(verbose_name='Active', default=True)
    total_messages = models.IntegerField(verbose_name='Total Messages', default=0)
    auto_messages = models.IntegerField(verbose_name='Auto Messages', default=0)
    average_speed = models.FloatField(verbose_name='Average Speed (msg/min)', default=0.0)
    auto_speed = models.FloatField(verbose_name='Auto Speed (msg/min)', default=0.0)
    set_frequency = models.FloatField(verbose_name='Set Frequency (msg/min)', default=0.0)  # Выставленная частота
    timeouts_count = models.IntegerField(verbose_name='Timeouts Count', default=0)
    total_timeout_duration = models.IntegerField(verbose_name='Total Timeout Duration (seconds)', default=0)
    
    class Meta:
        verbose_name = 'Shift'
        verbose_name_plural = 'Shifts'
        ordering = ['-start_time']
    
    def __str__(self):
        return f'{self.user.username} - {self.start_time.strftime("%d.%m.%Y %H:%M")}'
    
    @property
    def duration(self) -> timedelta:
        end = self.end_time if self.end_time else timezone.now()
        return end - self.start_time
    
    @property
    def duration_str(self) -> str:
        duration = self.duration
        hours = int(duration.total_seconds() // 3600)
        minutes = int((duration.total_seconds() % 3600) // 60)
        seconds = int(duration.total_seconds() % 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    
    def end_shift(self):
        """Завершить смену и рассчитать статистику"""
        if self.is_active:
            self.end_time = timezone.now()
            self.is_active = False
            
            # Рассчитываем среднюю скорость
            duration_minutes = self.duration.total_seconds() / 60
            if duration_minutes > 0:
                self.average_speed = round(self.total_messages / duration_minutes, 2)
                # Рассчитываем скорость автосообщений
                if self.auto_messages > 0:
                    self.auto_speed = round(self.auto_messages / duration_minutes, 2)
            
            # Рассчитываем общую длительность таймаутов
            total_timeout_seconds = sum(
                timeout.duration_seconds for timeout in self.timeouts.all() 
                if timeout.duration_seconds > 0
            )
            self.total_timeout_duration = total_timeout_seconds
            
            self.save()
            print(f"Shift {self.id} ended: duration={self.duration_str}, messages={self.total_messages}, timeouts={self.timeouts_count}")
    
    def update_speed(self):
        """Обновляет скорость в реальном времени"""
        duration_minutes = self.duration.total_seconds() / 60
        if duration_minutes > 0:
            self.average_speed = round(self.total_messages / duration_minutes, 2)
            if self.auto_messages > 0:
                self.auto_speed = round(self.auto_messages / duration_minutes, 2)
            self.save()
    
    def add_message(self, message_type='m'):
        """Добавляет сообщение и обновляет статистику"""
        self.total_messages += 1
        if message_type == 'a':
            self.auto_messages += 1
        self.update_speed()
        self.save()

    def finish(self):
        """Завершает смену и рассчитывает финальную статистику"""
        if self.is_active:
            self.end_time = timezone.now()
            self.is_active = False
            
            # Рассчитываем среднюю скорость
            duration_minutes = self.duration.total_seconds() / 60
            if duration_minutes > 0:
                self.average_speed = round(self.total_messages / duration_minutes, 2)
                # Рассчитываем скорость автосообщений
                if self.auto_messages > 0:
                    self.auto_speed = round(self.auto_messages / duration_minutes, 2)
            
            # Рассчитываем общую длительность таймаутов
            total_timeout_seconds = sum(
                timeout.duration_seconds for timeout in self.timeouts.all() 
                if timeout.duration_seconds > 0
            )
            self.total_timeout_duration = total_timeout_seconds
            
            self.save()
            print(f"Shift {self.id} finished: duration={self.duration_str}, messages={self.total_messages}, auto_messages={self.auto_messages}")


class MessageLog(models.Model):
    """Модель для логирования сообщений в смене"""
    shift = models.ForeignKey(Shift, related_name='messages', on_delete=models.CASCADE, verbose_name='Shift')
    timestamp = models.DateTimeField(verbose_name='Timestamp', auto_now_add=True)
    channel = models.CharField(verbose_name='Channel', max_length=100)
    account = models.CharField(verbose_name='Account', max_length=100)
    message_type = models.CharField(verbose_name='Message Type', max_length=10)  # 'a' for auto, 'm' for manual
    message = models.TextField(verbose_name='Message')
    
    class Meta:
        verbose_name = 'Message Log'
        verbose_name_plural = 'Message Logs'
        ordering = ['timestamp']
    
    def __str__(self):
        return f'{self.shift.user.username} - {self.timestamp.strftime("%H:%M:%S")} - {self.message[:50]}'


class TimeoutLog(models.Model):
    """Модель для логирования таймаутов (отходов)"""
    shift = models.ForeignKey(Shift, related_name='timeouts', on_delete=models.CASCADE, verbose_name='Shift')
    start_time = models.DateTimeField(verbose_name='Start Time', auto_now_add=True)
    end_time = models.DateTimeField(verbose_name='End Time', null=True, blank=True)
    duration_seconds = models.IntegerField(verbose_name='Duration (seconds)', default=0)
    
    class Meta:
        verbose_name = 'Timeout Log'
        verbose_name_plural = 'Timeout Logs'
        ordering = ['start_time']
    
    def __str__(self):
        return f'{self.shift.user.username} - {self.start_time.strftime("%H:%M:%S")} ({self.duration_seconds}s)'
    
    def end_timeout(self):
        """Завершить таймаут и рассчитать длительность"""
        if not self.end_time:
            self.end_time = timezone.now()
            self.duration_seconds = int((self.end_time - self.start_time).total_seconds())
            self.save()


class ShiftLog(models.Model):
    """Единая модель для логирования всех действий пользователя во время смены"""
    ACTION_TYPES = [
        ('shift_start', 'Начало смены'),
        ('shift_end', 'Конец смены'),
        ('channel_select', 'Выбор канала'),
        ('account_select', 'Выбор аккаунта'),
        ('account_deselect', 'Снятие выбора аккаунта'),
        ('auto_start', 'Запуск авто-рассылки'),
        ('auto_stop', 'Остановка авто-рассылки'),
        ('manual_send', 'Ручная отправка сообщения'),
        ('message_sent', 'Сообщение отправлено'),
        ('message_error', 'Ошибка отправки'),
        ('checkbox_toggle', 'Переключение галочки'),
        ('frequency_change', 'Изменение частоты'),
        ('message_change', 'Изменение текста сообщения'),
        ('proxy_change', 'Изменение прокси'),
        ('work_start', 'Начало работы'),
        ('work_stop', 'Остановка работы'),
        ('timeout_start', 'Начало таймаута'),
        ('timeout_end', 'Конец таймаута'),
        ('settings_change', 'Изменение настроек'),
        ('error', 'Ошибка'),
        ('other', 'Другое'),
    ]
    
    shift = models.ForeignKey(Shift, related_name='logs', on_delete=models.CASCADE, verbose_name='Shift')
    timestamp = models.DateTimeField(verbose_name='Timestamp', auto_now_add=True)
    action_type = models.CharField(verbose_name='Action Type', max_length=20, choices=ACTION_TYPES)
    description = models.TextField(verbose_name='Description')
    details = models.JSONField(verbose_name='Details', null=True, blank=True)
    
    class Meta:
        verbose_name = 'Shift Log'
        verbose_name_plural = 'Shift Logs'
        ordering = ['timestamp']
    
    def __str__(self):
        return f'{self.shift.user.username} - {self.timestamp.strftime("%H:%M:%S")} - {self.get_action_type_display()}'


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
        result = {'start': self.start.astimezone(pytz_timezone(settings.TIME_ZONE)).strftime('%H:%M:%S %d.%m.%Y'),
                  'end': self.end.astimezone(pytz_timezone(settings.TIME_ZONE)).strftime('%H:%M:%S %d.%m.%Y'),
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
        return f'[{self.start.astimezone(pytz_timezone(settings.TIME_ZONE))}] {self.user.username} - {self.data_count}'

    class Meta:
        verbose_name = 'Statistic'
        verbose_name_plural = 'Statistics'
