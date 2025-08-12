from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import JsonResponse, HttpResponse
from .models import Shift, ShiftLog
from .shift_manager import get_shift_manager
from ServiceApp.models import User
import json


def is_staff_user(user):
    return user.is_staff


@login_required
@user_passes_test(is_staff_user)
def shift_statistics(request):
    """Страница статистики смен"""
    users = User.objects.filter(is_staff=False).order_by('username')
    return render(request, 'StatsApp/shift_statistics.html', {
        'users': users
    })


@login_required
@user_passes_test(is_staff_user)
def user_shifts(request, user_id):
    """Получить все смены пользователя"""
    user = get_object_or_404(User, id=user_id)
    shifts = Shift.objects.filter(user=user).order_by('-start_time')
    
    shifts_data = []
    for shift in shifts:
        shifts_data.append({
            'id': shift.id,
            'start_time': shift.start_time.strftime('%d.%m.%Y %H:%M:%S'),
            'end_time': shift.end_time.strftime('%d.%m.%Y %H:%M:%S') if shift.end_time else 'Active',
            'duration': shift.duration_str,
            'total_messages': shift.total_messages,
            'auto_messages': shift.auto_messages,
            'average_speed': shift.average_speed,
            'auto_speed': shift.auto_speed,
            'set_frequency': shift.set_frequency,  # Добавляем выставленную частоту
            'timeouts_count': shift.timeouts_count,
            'is_active': shift.is_active
        })
    
    return JsonResponse({
        'user': user.username,
        'shifts': shifts_data
    })


@login_required
@user_passes_test(is_staff_user)
def shift_details(request, shift_id):
    """Получить детальную статистику смены"""
    shift = get_object_or_404(Shift, id=shift_id)
    shift_manager = get_shift_manager(shift.user)
    
    statistics = shift_manager.get_shift_statistics(shift)
    return JsonResponse(statistics)


@login_required
@user_passes_test(is_staff_user)
def shift_log_download(request, shift_id):
    """Скачать лог смены в текстовом формате"""
    shift = get_object_or_404(Shift, id=shift_id)
    shift_manager = get_shift_manager(shift.user)
    
    statistics = shift_manager.get_shift_statistics(shift)
    
    # Формируем текстовый лог
    log_content = f"=== СМЕНА ПОЛЬЗОВАТЕЛЯ {statistics['user']} ===\n"
    log_content += f"Начало: {statistics['start_time']}\n"
    log_content += f"Конец: {statistics['end_time']}\n"
    log_content += f"Длительность: {statistics['duration']}\n"
    log_content += f"Всего сообщений: {statistics['total_messages']}\n"
    log_content += f"Автосообщений: {statistics['auto_messages']}\n"
    log_content += f"Средняя скорость: {statistics['average_speed']} сообщений/мин\n"
    log_content += f"Скорость авто: {statistics['auto_speed']} сообщений/мин\n"
    log_content += f"Выставленная частота: {statistics['set_frequency']} сообщений/мин\n"
    log_content += f"Количество отходов: {statistics['timeouts_count']}\n"
    log_content += f"Общее время отходов: {statistics['total_timeout_duration']} сек\n\n"
    
    log_content += "\n"
    
    # Единый лог всех действий
    log_content += "=== ПОЛНЫЙ ЛОГ ДЕЙСТВИЙ ===\n"
    for action in statistics['action_log']:
        # Компактный формат для сообщений
        if action['type'] in ['Ручная отправка сообщения', 'Автоотправка сообщения', 'Ошибка отправки']:
            log_content += f"{action['time']} {action['description']}\n"
        else:
            # Для остальных действий оставляем полный формат
            details_str = ""
            if action.get('details'):
                if isinstance(action['details'], dict):
                    details_str = f" | {action['details']}"
                else:
                    details_str = f" | {action['details']}"
            log_content += f"[{action['time']}] {action['type']} | {action['description']}{details_str}\n"
    
    response = HttpResponse(log_content, content_type='text/plain; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="shift_{shift_id}_{statistics["user"]}.txt"'
    return response
