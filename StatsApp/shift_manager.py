from django.utils import timezone
from datetime import timedelta
from .models import Shift, ShiftLog
from ServiceApp.models import User
import logging

logger = logging.getLogger(__name__)


class ShiftManager:
    """Менеджер для управления сменами пользователей"""
    
    TIMEOUT_THRESHOLD = 60  # секунды бездействия для начала таймаута
    
    def __init__(self, user: User):
        self.user = user
        self.current_shift = None
        self.last_activity = None
        self.current_timeout = None
    
    def start_shift(self) -> Shift:
        """Начать новую смену"""
        # Завершаем предыдущую активную смену если есть
        active_shift = Shift.objects.filter(user=self.user, is_active=True).first()
        if active_shift:
            active_shift.end_shift()
        
        # Создаем новую смену
        self.current_shift = Shift.objects.create(user=self.user)
        self.last_activity = timezone.now()
        
        # Логируем начало смены
        self.log_action('shift_start', 'Начало новой смены')
        
        logger.info(f"Started shift for user {self.user.username}")
        return self.current_shift
    
    def end_shift(self) -> bool:
        """Завершить текущую смену"""
        if not self.current_shift or not self.current_shift.is_active:
            return False
        
        # Логируем завершение смены
        self.log_action('shift_end', 'Завершение смены')
        
        # Завершаем смену
        self.current_shift.end_shift()
        logger.info(f"Ended shift for user {self.user.username}, duration: {self.current_shift.duration_str}")
        return True
    
    def log_action(self, action_type: str, description: str, details: dict = None) -> bool:
        """Записать действие пользователя в лог"""
        if not self.current_shift or not self.current_shift.is_active:
            return False
        
        # Если это изменение настроек с frequency, сохраняем её в смену
        if action_type == 'settings_change' and details:
            if details.get('action') in ['frequency_and_messages_change', 'frequency_change', 'auto_frequency_set', 'frequency_loaded']:
                frequency = details.get('frequency', 0)
                if frequency > 0:
                    self.current_shift.set_frequency = frequency
                    self.current_shift.save()
                    print(f"Updated shift frequency to: {frequency}")
        
        ShiftLog.objects.create(
            shift=self.current_shift,
            action_type=action_type,
            description=description,
            details=details
        )
        
        self.last_activity = timezone.now()
        return True
    
    def log_message(self, channel: str, account: str, message_type: str, message: str) -> bool:
        """Записать сообщение в лог смены"""
        if not self.current_shift or not self.current_shift.is_active:
            return False
        
        # Определяем тип действия на основе типа сообщения
        if message_type == 'm':
            action_type = 'manual_send'
            action_desc = f'Ручная отправка сообщения от {account} в канал {channel}'
        elif message_type == 'a':
            action_type = 'auto_send'
            action_desc = f'Автоотправка сообщения от {account} в канал {channel}'
        elif message_type == 'e':
            action_type = 'message_error'
            action_desc = f'Ошибка отправки от {account} в канал {channel}: {message}'
        else:
            action_type = 'manual_send'
            action_desc = f'Отправка сообщения от {account} в канал {channel}'
        
        # Логируем действие
        self.log_action(action_type, action_desc, {
            'channel': channel,
            'account': account,
            'message_type': message_type,
            'message': message
        })
        
        # Обновляем статистику смены
        self.current_shift.total_messages += 1
        if message_type == 'a':
            self.current_shift.auto_messages += 1
        self.current_shift.save()
        
        self.last_activity = timezone.now()
        return True
    
    def check_timeout(self) -> bool:
        """Проверить и создать таймаут если нужно"""
        if not self.current_shift or not self.current_shift.is_active:
            return False
        
        if not self.last_activity:
            return False
        
        # Проверяем, прошло ли достаточно времени с последней активности
        time_since_activity = timezone.now() - self.last_activity
        
        if time_since_activity.total_seconds() >= self.TIMEOUT_THRESHOLD:
            # Логируем начало таймаута
            if not self.current_timeout:
                self.current_timeout = True
                self.current_shift.timeouts_count += 1
                self.current_shift.save()
                self.log_action('timeout_start', f'Начало таймаута после {int(time_since_activity.total_seconds())}с неактивности')
                logger.warning(f"Timeout started for user {self.user.username} after {time_since_activity.total_seconds()}s of inactivity")
            return True
        else:
            # Если время неактивности меньше порога, но есть активный таймаут - завершаем его
            if self.current_timeout:
                self.current_timeout = None
                self.log_action('timeout_end', f'Конец таймаута после {int(time_since_activity.total_seconds())}с неактивности')
                logger.info(f"Timeout ended for user {self.user.username} after {time_since_activity.total_seconds()}s of inactivity")
        
        return False
    
    def get_current_shift(self) -> Shift:
        """Получить текущую активную смену"""
        if not self.current_shift or not self.current_shift.is_active:
            self.current_shift = Shift.objects.filter(user=self.user, is_active=True).first()
        return self.current_shift
    
    def get_shift_statistics(self, shift: Shift) -> dict:
        """Получить полную статистику смены"""
        logs = ShiftLog.objects.filter(shift=shift).order_by('timestamp')
        
        # Рассчитываем среднюю скорость
        duration_minutes = shift.duration.total_seconds() / 60
        average_speed = round(shift.total_messages / duration_minutes, 2) if duration_minutes > 0 else 0
        
        # Формируем единый лог всех действий
        action_log = []
        for log in logs:
            action_log.append({
                'time': log.timestamp.strftime('%H:%M:%S'),
                'type': log.get_action_type_display(),
                'description': log.description,
                'details': log.details
            })
        
        return {
            'shift_id': shift.id,
            'user': shift.user.username,
            'start_time': shift.start_time.strftime('%d.%m.%Y %H:%M:%S'),
            'end_time': shift.end_time.strftime('%d.%m.%Y %H:%M:%S') if shift.end_time else 'Active',
            'duration': shift.duration_str,
            'total_messages': shift.total_messages,
            'auto_messages': shift.auto_messages,
            'average_speed': average_speed,
            'auto_speed': shift.auto_speed,
            'set_frequency': shift.set_frequency,  # Добавляем выставленную частоту
            'timeouts_count': shift.timeouts_count,
            'total_timeout_duration': shift.total_timeout_duration,
            'action_log': action_log
        }


# Глобальный словарь для хранения менеджеров смен
shift_managers = {}


def get_shift_manager(user: User) -> ShiftManager:
    """Получить менеджер смен для пользователя"""
    if user.id not in shift_managers:
        shift_managers[user.id] = ShiftManager(user)
    return shift_managers[user.id]


def cleanup_shift_manager(user_id: int):
    """Очистить менеджер смен пользователя"""
    if user_id in shift_managers:
        del shift_managers[user_id] 