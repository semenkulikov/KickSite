from django.contrib import admin
from .models import KickAccount, KickAccountAssignment
from ProxyApp.models import Proxy
from django import forms
from django.urls import path
from django.shortcuts import render, redirect
from django.contrib import messages
from django.db import models
import json

class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True

class MultipleFileField(forms.FileField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("widget", MultipleFileInput())
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        single_file_clean = super().clean
        if isinstance(data, (list, tuple)):
            result = [single_file_clean(d, initial) for d in data]
        else:
            result = single_file_clean(data, initial)
        return result

class MassImportForm(forms.Form):
    files = MultipleFileField(label='Файлы аккаунтов (JSON)', required=True)

class MassProxyUpdateForm(forms.Form):
    proxy_file = forms.FileField(label='Файл с прокси (по одной на строку)', required=True)

def normalize_proxy_url(proxy_str):
    if proxy_str.startswith('socks5://'):
        return proxy_str
    parts = proxy_str.split(':')
    if len(parts) == 4:
        host, port, user, pwd = parts
        return f'socks5://{user}:{pwd}@{host}:{port}'
    elif len(parts) == 2:
        host, port = parts
        return f'socks5://{host}:{port}'
    else:
        return proxy_str  # fallback, возможно уже валидный

class KickAccountAdmin(admin.ModelAdmin):
    list_display = ('login', 'owner', 'proxy', 'status', 'created', 'updated', 'assigned_users_count')
    search_fields = ('login',)
    list_filter = ('status', 'proxy')
    change_list_template = "admin/KickApp/kickaccount/change_list.html"
    actions = ['mass_proxy_update_action']
    
    def assigned_users_count(self, obj):
        """Количество назначенных пользователей"""
        return obj.assigned_users.count()
    assigned_users_count.short_description = 'Назначено пользователей'
    
    def get_queryset(self, request):
        """Фильтруем аккаунты в зависимости от роли пользователя"""
        qs = super().get_queryset(request)
        
        # Супер админ видит все
        if request.user.is_superuser or request.user.is_super_admin:
            return qs
        
        # Обычные админы видят все аккаунты
        if request.user.is_admin:
            return qs
        
        # Обычные пользователи не имеют доступа к админке (блокируется middleware)
        return qs.none()
    
    def mass_proxy_update_action(self, request, queryset):
        # Перенаправляем на страницу массового обновления прокси
        selected_ids = list(queryset.values_list('id', flat=True))
        request.session['selected_account_ids'] = selected_ids
        return redirect('mass_proxy_update/')
    
    mass_proxy_update_action.short_description = "Заменить прокси для выбранных аккаунтов"

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('mass_import/', self.admin_site.admin_view(self.mass_import_view), name='kickaccount_mass_import'),
            path('mass_proxy_update/', self.admin_site.admin_view(self.mass_proxy_update_view), name='kickaccount_mass_proxy_update'),
        ]
        return custom_urls + urls

    def mass_import_view(self, request):
        if request.method == 'POST':
            form = MassImportForm(request.POST, request.FILES)
            if form.is_valid():
                files = form.cleaned_data['files']
                imported, errors = 0, []
                for f in files:
                    try:
                        login = f.name.split('.')[0]
                        data = json.loads(f.read().decode('utf-8'))
                        token = data.get('authorization', '').replace('Bearer ', '')
                        session_token = None
                        cookies = data.get('cookie', '')
                        for part in cookies.split(';'):
                            if 'kick_session=' in part:
                                session_token = part.split('kick_session=')[1].strip()
                        proxy_obj = None
                        proxy_str = data.get('proxy', '')
                        if proxy_str:
                            proxy_url = normalize_proxy_url(proxy_str)
                            proxy_obj, _ = Proxy.objects.get_or_create(url=proxy_url)
                        KickAccount.objects.update_or_create(
                            login=login,
                            owner=request.user,
                            defaults={
                                'token': token,
                                'session_token': session_token,
                                'proxy': proxy_obj,
                            }
                        )
                        imported += 1
                    except Exception as e:
                        errors.append(f"{f.name}: {str(e)}")
                if imported:
                    messages.success(request, f"Импортировано аккаунтов: {imported}")
                if errors:
                    messages.error(request, "Ошибки импорта: " + "; ".join(errors))
                return redirect('..')
        else:
            form = MassImportForm()
        context = self.admin_site.each_context(request)
        context['opts'] = self.model._meta
        context['form'] = form
        return render(request, 'admin/kickaccount_mass_import.html', context)

    def mass_proxy_update_view(self, request):
        if request.method == 'POST':
            # Проверяем, есть ли файл с прокси
            if 'proxy_file' in request.FILES:
                form = MassProxyUpdateForm(request.POST, request.FILES)
                if form.is_valid():
                    proxy_file = form.cleaned_data['proxy_file']
                    
                    # Читаем прокси из файла
                    proxy_lines = []
                    try:
                        content = proxy_file.read().decode('utf-8')
                        proxy_lines = [line.strip() for line in content.split('\n') if line.strip()]
                    except Exception as e:
                        messages.error(request, f"Ошибка чтения файла: {str(e)}")
                        return redirect('..')
                    
                    # Получаем выбранные аккаунты из сессии
                    selected_account_ids = request.session.get('selected_account_ids', [])
                    if not selected_account_ids:
                        messages.error(request, "Не выбрано ни одного аккаунта")
                        return redirect('..')
                    
                    # Получаем аккаунты из базы
                    accounts = KickAccount.objects.filter(id__in=selected_account_ids)
                    accounts_count = accounts.count()
                    proxies_count = len(proxy_lines)
                    
                    # Обновляем прокси
                    updated_count = 0
                    not_updated_accounts = []
                    unused_proxies = []
                    
                    for i, account in enumerate(accounts):
                        if i < len(proxy_lines):
                            proxy_str = proxy_lines[i]
                            proxy_url = normalize_proxy_url(proxy_str)
                            
                            # Создаем или получаем прокси
                            proxy_obj, created = Proxy.objects.get_or_create(url=proxy_url)
                            
                            # Обновляем аккаунт
                            account.proxy = proxy_obj
                            account.save()
                            updated_count += 1
                        else:
                            not_updated_accounts.append(account.login)
                    
                    # Проверяем неиспользованные прокси
                    if proxies_count > accounts_count:
                        unused_proxies = proxy_lines[accounts_count:]
                    
                    # Формируем сообщения
                    if updated_count > 0:
                        messages.success(request, f"Обновлено прокси для {updated_count} аккаунтов")
                    
                    if not_updated_accounts:
                        messages.warning(request, f"Не хватило прокси для аккаунтов: {', '.join(not_updated_accounts)}")
                    
                    if unused_proxies:
                        messages.info(request, f"Неиспользованные прокси ({len(unused_proxies)}): {', '.join(unused_proxies[:10])}{'...' if len(unused_proxies) > 10 else ''}")
                    
                    # Очищаем сессию
                    if 'selected_account_ids' in request.session:
                        del request.session['selected_account_ids']
                    
                    return redirect('..')
            else:
                # Обрабатываем выбор аккаунтов
                selected_accounts = request.POST.getlist('_selected_action')
                if selected_accounts:
                    request.session['selected_account_ids'] = selected_accounts
                    form = MassProxyUpdateForm()
                else:
                    messages.error(request, "Не выбрано ни одного аккаунта")
                    return redirect('..')
        else:
            form = MassProxyUpdateForm()
        
        context = self.admin_site.each_context(request)
        context['opts'] = self.model._meta
        context['form'] = form
        
        # Добавляем информацию о выбранных аккаунтах
        selected_account_ids = request.session.get('selected_account_ids', [])
        if selected_account_ids:
            selected_accounts = KickAccount.objects.filter(id__in=selected_account_ids)
            context['selected_accounts'] = selected_accounts
            context['selected_count'] = selected_accounts.count()
        
        return render(request, 'admin/kickaccount_mass_proxy_update.html', context)

class KickAccountAssignmentAdmin(admin.ModelAdmin):
    list_display = ('kick_account', 'user', 'assigned_by', 'assignment_type', 'assigned_at', 'is_active')
    list_filter = ('assignment_type', 'is_active', 'assigned_at')
    search_fields = ('kick_account__login', 'user__username', 'assigned_by__username')
    ordering = ('-assigned_at',)
    
    def get_queryset(self, request):
        """Фильтруем назначения в зависимости от роли пользователя"""
        qs = super().get_queryset(request)
        
        # Супер админ видит все
        if request.user.is_superuser or request.user.is_super_admin:
            return qs
        
        # Обычные админы видят все назначения
        if request.user.is_admin:
            return qs
        
        # Обычные пользователи не имеют доступа к админке (блокируется middleware)
        return qs.none()
    
    def save_model(self, request, obj, form, change):
        """Автоматически устанавливаем assigned_by при создании"""
        if not change:  # Только при создании
            obj.assigned_by = request.user
        super().save_model(request, obj, form, change)

# Регистрируем только KickAccount в стандартной админке
admin.site.register(KickAccount, KickAccountAdmin)
admin.site.register(KickAccountAssignment, KickAccountAssignmentAdmin)
