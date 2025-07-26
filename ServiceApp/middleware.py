from django.db import transaction, OperationalError
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render, redirect
import time
import logging
from django.urls import reverse
from django.contrib import messages
from django.conf import settings

logger = logging.getLogger(__name__)


class TransactionMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        max_retries = 3
        retry_delay = 0.1  # 100ms delay between retries
        
        for attempt in range(max_retries):
            try:
                with transaction.atomic():
                    response = self.get_response(request)
                return response
            except OperationalError as e:
                if "database is locked" in str(e).lower() and attempt < max_retries - 1:
                    logger.warning(f"Database locked, retry {attempt + 1}/{max_retries}")
                    time.sleep(retry_delay * (attempt + 1))  # Exponential backoff
                    continue
                else:
                    # Final attempt failed or different error
                    logger.error(f"Database operation failed: {str(e)}")
                    
                    # Return user-friendly error instead of Django debug page
                    if request.is_ajax() or request.content_type == 'application/json':
                        return JsonResponse({
                            'error': 'Database temporarily unavailable. Please try again.',
                            'details': 'The system is currently processing other requests. Please wait a moment and retry.'
                        }, status=503)
                    else:
                        # For regular HTTP requests, render a user-friendly error page
                        return render(request, 'error_pages/database_locked.html', {
                            'error_message': 'Database temporarily unavailable',
                            'error_details': 'The system is currently busy. Please wait a moment and try again.',
                            'retry_url': request.get_full_path()
                        }, status=503)
        
        # This should never be reached, but just in case
        return HttpResponse("Service temporarily unavailable", status=503)

class AdminAccessMiddleware:
    """
    Middleware для контроля доступа к админке Django
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        try:
            # Проверяем, является ли запрос к админке
            if request.path.startswith('/admin/'):
                # Если пользователь не аутентифицирован, пропускаем (Django сам перенаправит на логин)
                if not request.user.is_authenticated:
                    return self.get_response(request)
                
                # Проверяем права доступа
                if not self.has_admin_access(request.user):
                    messages.error(request, 'У вас нет прав для доступа к админке.')
                    return redirect('index')  # Перенаправляем на главную страницу
            
            return self.get_response(request)
        except Exception as e:
            print(f"[AdminAccessMiddleware] Error: {e}")
            # В случае ошибки пропускаем запрос
            return self.get_response(request)
    
    def has_admin_access(self, user):
        """
        Проверяет, есть ли у пользователя права на доступ к админке
        """
        # Суперпользователь Django всегда имеет доступ
        if user.is_superuser:
            return True
        
        # Проверяем роль пользователя - только админы и супер админы
        if hasattr(user, 'role') and user.role:
            if user.role.name in ['super_admin', 'admin']:
                return True
        
        # Также проверяем is_admin свойство (для обратной совместимости)
        if hasattr(user, 'is_admin') and user.is_admin:
            return True
        
        # Проверяем is_staff (если пользователь назначен как staff)
        if user.is_staff:
            return True
        
        # Обычные пользователи не имеют доступа к админке
        return False