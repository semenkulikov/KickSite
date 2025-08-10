from django.contrib import admin
from .models import KickAccount, KickAccountAssignment, StreamerStatus, AutoResponse, StreamerMessage, HydraBotSettings, StreamerHydraSettings
from ProxyApp.models import Proxy
from django import forms
from django.urls import path
from django.shortcuts import render, redirect
from django.contrib import messages
from django.db import models
import json
from django.contrib.auth import get_user_model
from django.contrib.admin import SimpleListFilter
import threading

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
    assign_to_user = forms.ModelChoiceField(
        queryset=get_user_model().objects.filter(is_active=True).order_by('username'),
        label='Привязать к пользователю (необязательно)',
        required=False,
        empty_label="Не привязывать к пользователю",
        help_text='Если выбран пользователь, все импортируемые аккаунты будут привязаны к нему'
    )

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

class AssignedUserFilter(SimpleListFilter):
    """Фильтр для отображения KickAccount по назначенным пользователям"""
    title = 'Назначен пользователю'
    parameter_name = 'assigned_user'

    def lookups(self, request, model_admin):
        # Получаем всех пользователей, которым назначены аккаунты
        users = get_user_model().objects.filter(
            assigned_kick_accounts__isnull=False
        ).distinct().order_by('username')
        return [(user.id, user.username) for user in users]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(assigned_users__id=self.value()).distinct()
        return queryset

class KickAccountAdmin(admin.ModelAdmin):
    list_display = ('login', 'owner', 'proxy', 'status', 'created', 'updated', 'assigned_users_count')
    search_fields = ('login',)
    list_filter = ('status', 'proxy', AssignedUserFilter)
    change_list_template = "admin/KickApp/kickaccount/change_list.html"
    actions = ['mass_proxy_update_action', 'assign_to_user_action']
    
    def assigned_users_count(self, obj):
        """Количество назначенных пользователей"""
        return obj.assigned_users.count()
    assigned_users_count.short_description = 'Назначено пользователей'
    
    def get_queryset(self, request):
        """Фильтруем аккаунты в зависимости от роли пользователя"""
        qs = super().get_queryset(request)
        
        # Оптимизируем запросы для связанных данных
        qs = qs.select_related('proxy', 'owner').prefetch_related('assigned_users')
        
        # Супер админ видит все
        if request.user.is_superuser or request.user.is_super_admin:
            return qs
        
        # Обычные админы видят все аккаунты
        if request.user.is_admin:
            return qs
        
        # Обычные пользователи не имеют доступа к админке (блокируется middleware)
        return qs.none()
    
    def assign_to_user_action(self, request, queryset):
        """Массовое назначение кик аккаунтов пользователю"""
        print(f"DEBUG: assign_to_user_action вызван")
        print(f"DEBUG: POST данные: {request.POST}")
        
        # Если это первичный вызов действия (выбор аккаунтов)
        if 'action' in request.POST and 'apply' not in request.POST:
            print(f"DEBUG: Первичный вызов действия - показываем форму")
            # Показываем форму выбора пользователя
            users = get_user_model().objects.filter(is_active=True).order_by('username')
            context = {
                'title': 'Выберите пользователя для назначения аккаунтов',
                'queryset': queryset,
                'users': users,
                'opts': self.model._meta,
            }
            return render(request, 'admin/KickApp/kickaccount/assign_to_user.html', context)
        
        # Если это отправка формы с выбранным пользователем
        if 'apply' in request.POST:
            user_id = request.POST.get('user')
            print(f"DEBUG: Отправка формы с apply=1")
            print(f"DEBUG: user_id = {user_id}")
            print(f"DEBUG: Все POST данные: {dict(request.POST)}")
            
            if user_id:
                try:
                    user = get_user_model().objects.get(id=user_id)
                    assigned_count = 0
                    
                    print(f"DEBUG: Начинаем назначение аккаунтов пользователю {user.username}")
                    print(f"DEBUG: Выбрано аккаунтов: {queryset.count()}")
                    
                    for account in queryset:
                        print(f"DEBUG: Обрабатываем аккаунт {account.login}")
                        
                        # Проверяем, есть ли уже назначение
                        existing_assignment = KickAccountAssignment.objects.filter(
                            kick_account=account,
                            user=user
                        ).first()
                        
                        if existing_assignment:
                            print(f"DEBUG: Назначение уже существует для {account.login}")
                            if not existing_assignment.is_active:
                                existing_assignment.is_active = True
                                existing_assignment.save()
                                assigned_count += 1
                                print(f"DEBUG: Активировано существующее назначение для {account.login}")
                        else:
                            # Создаем новое назначение
                            assignment = KickAccountAssignment.objects.create(
                                kick_account=account,
                                user=user,
                                assigned_by=request.user,
                                assignment_type='admin_assigned',
                                is_active=True
                            )
                            assigned_count += 1
                            print(f"DEBUG: Создано новое назначение для {account.login}")
                    
                    print(f"DEBUG: Итого назначено {assigned_count} аккаунтов пользователю {user.username}")
                    
                    # Добавляем отладочную информацию для уведомлений
                    print(f"DEBUG: Добавляем уведомление об успехе")
                    messages.success(request, f'Успешно назначено {assigned_count} аккаунтов пользователю {user.username}')
                    print(f"DEBUG: Уведомления в request: {list(request._messages)}")
                    print(f"DEBUG: Количество уведомлений: {len(list(request._messages))}")
                    
                    # Проверяем сессию
                    print(f"DEBUG: Сессия содержит уведомления: {request.session.get('_messages', [])}")
                    print(f"DEBUG: Сессия до сохранения: {dict(request.session)}")
                    
                    # Принудительно сохраняем уведомления в сессии для ASGI
                    try:
                        from django.contrib.messages.storage.session import SessionStorage
                        storage = SessionStorage(request)
                        for message in request._messages:
                            storage.add(message.level, message.message, message.extra_tags)
                        print(f"DEBUG: Уведомления принудительно сохранены в сессии")
                    except Exception as e:
                        print(f"DEBUG: Ошибка при принудительном сохранении уведомлений: {e}")
                    
                    # Принудительно сохраняем уведомления в сессии
                    request.session.modified = True
                    print(f"DEBUG: Сессия помечена как измененная")
                    
                    # Проверяем, что происходит с уведомлениями после сохранения
                    print(f"DEBUG: Уведомления после сохранения: {list(request._messages)}")
                    print(f"DEBUG: Сессия после сохранения: {request.session.get('_messages', [])}")
                    
                    # Проверяем middleware (только для WSGI)
                    try:
                        middleware_chain = getattr(request, '_middleware_chain', None)
                        print(f"DEBUG: MIDDLEWARE: {middleware_chain}")
                    except AttributeError:
                        print(f"DEBUG: MIDDLEWARE: ASGI режим - _middleware_chain недоступен")
                    
                    return redirect('admin:KickApp_kickaccount_changelist')
                except Exception as e:
                    print(f"DEBUG: Ошибка при назначении: {str(e)}")
                    messages.error(request, f'Ошибка при назначении аккаунтов: {str(e)}')
                    return redirect('admin:KickApp_kickaccount_changelist')
            else:
                print(f"DEBUG: Пользователь не выбран")
                messages.error(request, 'Пользователь не выбран')
                return redirect('admin:KickApp_kickaccount_changelist')
        
        # Если это не POST запрос, показываем форму
        users = get_user_model().objects.filter(is_active=True).order_by('username')
        context = {
            'title': 'Выберите пользователя для назначения аккаунтов',
            'queryset': queryset,
            'users': users,
            'opts': self.model._meta,
        }
        return render(request, 'admin/KickApp/kickaccount/assign_to_user.html', context)
    
    def changelist_view(self, request, extra_context=None):
        """Переопределяем changelist_view для обработки действий"""
        print(f"DEBUG: changelist_view вызван")
        
        # Проверяем уведомления
        print(f"DEBUG: Уведомления в changelist_view: {list(request._messages)}")
        print(f"DEBUG: Количество уведомлений в changelist_view: {len(list(request._messages))}")
        print(f"DEBUG: Сессия в changelist_view: {request.session.get('_messages', [])}")
        print(f"DEBUG: Полная сессия в changelist_view: {dict(request.session)}")
        
        # Проверяем, есть ли действие в POST
        if request.method == 'POST' and 'action' in request.POST:
            action = request.POST.get('action')
            print(f"DEBUG: Действие: {action}")
            
            if action == 'assign_to_user_action':
                # Получаем выбранные объекты
                selected = request.POST.getlist('_selected_action')
                print(f"DEBUG: Выбранные объекты: {selected}")
                
                if selected:
                    queryset = self.get_queryset(request).filter(pk__in=selected)
                    return self.assign_to_user_action(request, queryset)
        
        return super().changelist_view(request, extra_context)
    
    assign_to_user_action.short_description = "Привязать выбранные Кик аккаунты к пользователю"
    
    def mass_proxy_update_action(self, request, queryset):
        # Перенаправляем на страницу массового обновления прокси
        selected_ids = list(queryset.values_list('id', flat=True))
        request.session['selected_account_ids'] = selected_ids
        return redirect('mass_proxy_update/')
    
    mass_proxy_update_action.short_description = "Заменить прокси для выбранных аккаунтов"

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('bulk-import/', self.admin_site.admin_view(self.mass_import_view), name='kickaccount_mass_import'),
            path('mass_proxy_update/', self.admin_site.admin_view(self.mass_proxy_update_view), name='kickaccount_mass_proxy_update'),
        ]
        return custom_urls + urls

    def mass_import_view(self, request):
        if request.method == 'POST':
            form = MassImportForm(request.POST, request.FILES)
            if form.is_valid():
                files = form.cleaned_data['files']
                assign_to_user = form.cleaned_data['assign_to_user']
                imported, errors = 0, []
                assigned_count = 0
                
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
                        
                        # Создаем или обновляем аккаунт
                        account, created = KickAccount.objects.update_or_create(
                            login=login,
                            defaults={
                                'token': token,
                                'session_token': session_token,
                                'proxy': proxy_obj,
                                'owner': request.user,
                            }
                        )
                        
                        # Если выбран пользователь для привязки
                        if assign_to_user and account not in assign_to_user.assigned_kick_accounts.all():
                            # Создаем назначение аккаунта пользователю
                            KickAccountAssignment.objects.get_or_create(
                                kick_account=account,
                                user=assign_to_user,
                                defaults={
                                    'assigned_by': request.user,
                                    'assignment_type': 'admin_assigned',
                                    'is_active': True,
                                }
                            )
                            assigned_count += 1
                        
                        imported += 1
                    except Exception as e:
                        errors.append(f"{f.name}: {str(e)}")
                
                # Формируем сообщения о результатах
                if imported:
                    messages.success(request, f"Импортировано аккаунтов: {imported}")
                    if assigned_count > 0:
                        messages.success(request, f"Привязано к пользователю '{assign_to_user.username}': {assigned_count}")
                if errors:
                    messages.error(request, "Ошибки импорта: " + "; ".join(errors))
                return redirect('..')
        else:
            form = MassImportForm()
        context = self.admin_site.each_context(request)
        context['opts'] = self.model._meta
        context['form'] = form
        return render(request, 'admin/KickApp/kickaccount/mass_import.html', context)

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

class HydraBotSettingsForm(forms.ModelForm):
    """Форма для настроек бота "Гидра" """
    class Meta:
        model = HydraBotSettings
        fields = ['is_enabled', 'message_interval', 'cycle_interval', 'sync_interval', 'max_concurrent_sends', 'min_message_interval']
        widgets = {
            'is_enabled': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'message_interval': forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'max': 60}),
            'cycle_interval': forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'max': 3600}),
            'sync_interval': forms.NumberInput(attrs={'class': 'form-control', 'min': 30, 'max': 3600}),
            'max_concurrent_sends': forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'max': 10000}),
            'min_message_interval': forms.NumberInput(attrs={'class': 'form-control', 'min': 60, 'max': 3600}),
        }

class HydraEnabledFilter(SimpleListFilter):
    """Фильтр для отображения стримеров в гидре"""
    title = 'Статус в Гидре'
    parameter_name = 'hydra_status'
    
    def lookups(self, request, model_admin):
        return (
            ('enabled', 'Включен в Гидре'),
            ('disabled', 'Отключен в Гидре'),
        )
    
    def queryset(self, request, queryset):
        if self.value() == 'enabled':
            return queryset.filter(is_hydra_enabled=True)
        if self.value() == 'disabled':
            return queryset.filter(is_hydra_enabled=False)

class StreamerHydraSettingsInline(admin.TabularInline):
    """Инлайн для настроек Гидры стримера"""
    model = StreamerHydraSettings
    extra = 0
    fields = ['is_active', 'message_interval', 'cycle_interval']
    readonly_fields = ['created_at', 'updated_at']

@admin.register(StreamerStatus)
class StreamerStatusAdmin(admin.ModelAdmin):
    list_display = ['vid', 'status', 'last_updated', 'is_hydra_enabled', 'assigned_user']
    list_filter = ['status', 'is_hydra_enabled', HydraEnabledFilter]
    search_fields = ['vid']
    readonly_fields = ['last_updated']
    inlines = [StreamerHydraSettingsInline]
    
    def save_model(self, request, obj, form, change):
        """Принудительно обновляем индивидуальные настройки при изменении is_hydra_enabled"""
        super().save_model(request, obj, form, change)
        
        # Принудительно обновляем индивидуальные настройки
        try:
            from .models import StreamerHydraSettings
            hydra_settings, created = StreamerHydraSettings.objects.get_or_create(
                streamer=obj,
                defaults={
                    'is_active': obj.is_hydra_enabled,
                    'message_interval': None,
                    'cycle_interval': None,
                }
            )
            
            if not created:
                hydra_settings.is_active = obj.is_hydra_enabled
                hydra_settings.save(update_fields=['is_active'])
            
            print(f"🔄 Принудительно обновлены настройки Гидры для стримера {obj.vid}: is_active={obj.is_hydra_enabled}")
            
        except Exception as e:
            print(f"❌ Ошибка принудительного обновления настроек Гидры для стримера {obj.vid}: {e}")
            import traceback
            traceback.print_exc()
    
    def get_actions(self, request):
        actions = super().get_actions(request)
        actions['enable_hydra'] = (self.enable_hydra_action, 'enable_hydra', "Включить в гидру")
        actions['disable_hydra'] = (self.disable_hydra_action, 'disable_hydra', "Отключить от гидры")
        return actions
    
    def enable_hydra_action(self, modeladmin, request, queryset):
        """Включить выбранных стримеров в гидру"""
        updated = queryset.update(is_hydra_enabled=True)
        
        # Принудительно обновляем индивидуальные настройки
        for streamer in queryset:
            try:
                from .models import StreamerHydraSettings
                hydra_settings, created = StreamerHydraSettings.objects.get_or_create(
                    streamer=streamer,
                    defaults={
                        'is_active': True,
                        'message_interval': None,
                        'cycle_interval': None,
                    }
                )
                
                if not created:
                    hydra_settings.is_active = True
                    hydra_settings.save(update_fields=['is_active'])
                
                print(f"🔄 Принудительно обновлены настройки Гидры для стримера {streamer.vid}: is_active=True")
                
            except Exception as e:
                print(f"❌ Ошибка принудительного обновления настроек Гидры для стримера {streamer.vid}: {e}")
        
        self.message_user(request, f"Включено в гидру: {updated} стримеров")
    enable_hydra_action.short_description = "Включить в гидру"
    
    def disable_hydra_action(self, modeladmin, request, queryset):
        """Отключить выбранных стримеров от гидры"""
        updated = queryset.update(is_hydra_enabled=False)
        
        # Принудительно обновляем индивидуальные настройки
        for streamer in queryset:
            try:
                from .models import StreamerHydraSettings
                hydra_settings, created = StreamerHydraSettings.objects.get_or_create(
                    streamer=streamer,
                    defaults={
                        'is_active': False,
                        'message_interval': None,
                        'cycle_interval': None,
                    }
                )
                
                if not created:
                    hydra_settings.is_active = False
                    hydra_settings.save(update_fields=['is_active'])
                
                print(f"🔄 Принудительно обновлены настройки Гидры для стримера {streamer.vid}: is_active=False")
                
            except Exception as e:
                print(f"❌ Ошибка принудительного обновления настроек Гидры для стримера {streamer.vid}: {e}")
        
        self.message_user(request, f"Отключено от гидры: {updated} стримеров")
    disable_hydra_action.short_description = "Отключить от гидры"

@admin.register(StreamerMessage)
class StreamerMessageAdmin(admin.ModelAdmin):
    list_display = ['streamer', 'message_short', 'is_active', 'created_at', 'last_sent']
    list_filter = ['is_active', 'created_at', 'streamer']
    search_fields = ['message', 'streamer__vid']
    readonly_fields = ['created_at', 'last_sent']
    
    def message_short(self, obj):
        return obj.message[:50] + '...' if len(obj.message) > 50 else obj.message
    message_short.short_description = 'Сообщение'

@admin.register(AutoResponse)
class AutoResponseAdmin(admin.ModelAdmin):
    list_display = ['streamer_vid', 'response_type', 'message_short', 'is_active', 'priority']
    list_filter = ['response_type', 'is_active', 'priority']
    search_fields = ['streamer_vid', 'message']
    
    def message_short(self, obj):
        return obj.message[:50] + '...' if len(obj.message) > 50 else obj.message
    message_short.short_description = 'Сообщение'

@admin.register(KickAccountAssignment)
class KickAccountAssignmentAdmin(admin.ModelAdmin):
    list_display = ['kick_account', 'user', 'assigned_by', 'assignment_type', 'is_active', 'assigned_at']
    list_filter = ['assignment_type', 'is_active', 'assigned_at', 'user']
    search_fields = ['kick_account__login', 'user__username']
    readonly_fields = ['assigned_at']

@admin.register(StreamerHydraSettings)
class StreamerHydraSettingsAdmin(admin.ModelAdmin):
    list_display = ['streamer', 'is_active', 'message_interval', 'cycle_interval', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['streamer__vid']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Основные настройки', {
            'fields': ('streamer', 'is_active')
        }),
        ('Интервалы', {
            'fields': ('message_interval', 'cycle_interval'),
            'description': 'Оставьте пустым для использования глобальных настроек Гидры'
        }),
        ('Системная информация', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('streamer')

@admin.register(HydraBotSettings)
class HydraBotSettingsAdmin(admin.ModelAdmin):
    """Админка для управления ботом "Гидра" """
    
    def has_add_permission(self, request):
        """Запрещаем создание новых записей - только одна запись настроек"""
        return not HydraBotSettings.objects.exists()
    
    def has_delete_permission(self, request, obj=None):
        """Запрещаем удаление настроек"""
        return False
    
    def get_queryset(self, request):
        """Показываем только одну запись настроек"""
        return HydraBotSettings.objects.filter(id=1)
    
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('hydra-dashboard/', self.hydra_dashboard_view, name='hydra_dashboard'),
        ]
        return custom_urls + urls
    
    def hydra_dashboard_view(self, request):
        """Дашборд для управления ботом "Гидра" """
        if not request.user.is_superuser:
            messages.error(request, 'Доступ только для супер-администраторов')
            return redirect('admin:index')
        
        # Получаем статистику
        active_streamers = StreamerStatus.objects.filter(status='active').count()
        total_messages = StreamerMessage.objects.filter(is_active=True).count()
        total_accounts = KickAccount.objects.filter(status='active').count()
        
        # Получаем настройки
        settings = HydraBotSettings.get_settings()
        
        if request.method == 'POST':
            form = HydraBotSettingsForm(request.POST, instance=settings)
            if form.is_valid():
                form.save()
                messages.success(request, 'Настройки бота "Гидра" обновлены')
                return redirect('admin:hydra_dashboard')
        else:
            form = HydraBotSettingsForm(instance=settings)
        
        context = {
            'form': form,
            'settings': settings,
            'active_streamers': active_streamers,
            'total_messages': total_messages,
            'total_accounts': total_accounts,
            'title': 'Управление ботом "Гидра"',
            'opts': self.model._meta,
        }
        return render(request, 'admin/hydra_dashboard.html', context)

# Регистрируем только KickAccount в стандартной админке
admin.site.register(KickAccount, KickAccountAdmin)
