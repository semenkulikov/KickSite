from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth import get_user_model
from django import forms
from django.shortcuts import render, redirect
from django.contrib import messages
from django.urls import path
from .models import KickAccount, KickAccountAssignment, StreamerStatus, AutoResponse, StreamerMessage, HydraBotSettings
import logging

logger = logging.getLogger(__name__)

User = get_user_model()

class MassImportForm(forms.Form):
    """Форма для массового импорта аккаунтов"""
    accounts_data = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 10, 'cols': 50}),
        label='Данные аккаунтов',
        help_text='Введите данные аккаунтов в формате: логин|токен|сессионный_токен (каждый аккаунт с новой строки)'
    )
    assign_to_user = forms.ModelChoiceField(
        queryset=User.objects.all(),
        required=False,
        label='Назначить пользователю',
        help_text='Выберите пользователя, которому будут назначены все импортированные аккаунты'
    )

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

@admin.register(KickAccount)
class KickAccountAdmin(admin.ModelAdmin):
    list_display = ['login', 'status', 'owner', 'proxy', 'created']
    list_filter = ['status', 'created', 'owner']
    search_fields = ['login']
    readonly_fields = ['created', 'updated']
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('owner', 'proxy')
    
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('mass-import/', self.mass_import_view, name='kickaccount_mass_import'),
        ]
        return custom_urls + urls
    
    def mass_import_view(self, request):
        """Представление для массового импорта аккаунтов"""
        if not request.user.is_superuser:
            messages.error(request, 'Доступ только для супер-администраторов')
            return redirect('admin:index')
        
        if request.method == 'POST':
            form = MassImportForm(request.POST)
            if form.is_valid():
                accounts_data = form.cleaned_data['accounts_data']
                assign_to_user = form.cleaned_data['assign_to_user']
                
                # Обрабатываем данные аккаунтов
                lines = accounts_data.strip().split('\n')
                created_count = 0
                
                for line in lines:
                    line = line.strip()
                    if not line:
                        continue
                    
                    parts = line.split('|')
                    if len(parts) >= 2:
                        login = parts[0].strip()
                        token = parts[1].strip()
                        session_token = parts[2].strip() if len(parts) > 2 else ''
                        
                        # Создаем аккаунт
                        account, created = KickAccount.objects.get_or_create(
                            login=login,
                            defaults={
                                'token': token,
                                'session_token': session_token,
                                'owner': request.user
                            }
                        )
                        
                        if created:
                            created_count += 1
                            
                            # Назначаем пользователю если указан
                            if assign_to_user:
                                KickAccountAssignment.objects.get_or_create(
                                    kick_account=account,
                                    user=assign_to_user,
                                    defaults={
                                        'assigned_by': request.user,
                                        'assignment_type': 'admin_assigned'
                                    }
                                )
                
                messages.success(request, f'Успешно импортировано {created_count} аккаунтов')
                return redirect('admin:KickApp_kickaccount_changelist')
        else:
            form = MassImportForm()
        
        context = {
            'form': form,
            'title': 'Массовый импорт аккаунтов',
            'opts': self.model._meta,
        }
        return render(request, 'admin/kickaccount_mass_import.html', context)

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

@admin.register(StreamerStatus)
class StreamerStatusAdmin(admin.ModelAdmin):
    list_display = ['vid', 'status', 'assigned_user', 'last_updated']
    list_filter = ['status', 'last_updated']
    search_fields = ['vid']
    readonly_fields = ['last_updated']

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
    list_filter = ['assignment_type', 'is_active', 'assigned_at']
    search_fields = ['kick_account__login', 'user__username']
    readonly_fields = ['assigned_at']
