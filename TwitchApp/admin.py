from django.contrib import admin
from django.db.models import Value
from django.db.models.functions import Concat
from django_mysql.models import GroupConcat
from TwitchApp.models import TwitchAccount
from django.http import HttpResponseRedirect
from django.urls import path
from TwitchApp.importer import TwitchAccountImporter
from django.db import IntegrityError
from django.contrib import messages
from django.core.exceptions import ValidationError
from django import forms
from ProxyApp.models import Proxy


class TwitchAccountAdminForm(forms.ModelForm):
    """Custom form to handle validation errors gracefully"""
    
    class Meta:
        model = TwitchAccount
        fields = '__all__'
    
    def clean(self):
        cleaned_data = super().clean()
        login = cleaned_data.get('login')
        
        # Check for duplicate login if this is a new instance
        if login and not self.instance.pk:
            if TwitchAccount.objects.filter(login=login).exists():
                raise ValidationError({
                    'login': 'A Twitch account with this login already exists.'
                })
        
        return cleaned_data


@admin.register(TwitchAccount)
class TwitchAccountAdmin(admin.ModelAdmin):
    form = TwitchAccountAdminForm
    change_list_template = "admin/model_change_list.html"

    def save_model(self, request, obj, form, change):
        """Override save_model to handle IntegrityError gracefully"""
        try:
            super().save_model(request, obj, form, change)
        except IntegrityError as e:
            # Handle specific constraint violations
            if 'login' in str(e).lower() or 'unique' in str(e).lower():
                messages.error(
                    request, 
                    f"Error saving Twitch account: A record with this login already exists. "
                    f"Please choose a different login."
                )
            else:
                messages.error(
                    request,
                    f"Error saving Twitch account: {str(e)}"
                )
            # Re-raise to prevent saving
            raise ValidationError("Database constraint violation prevented saving.")

    def get_urls(self):
        urls = super(TwitchAccountAdmin, self).get_urls()
        custom_urls = [
            path("import/", self.process_import, name='process_import'),
            path("assign-proxies/", self.assign_proxies_to_accounts, name='assign_proxies_to_accounts'),
        ]
        return custom_urls + urls

    def process_import(self, request):
        try:
            result = TwitchAccountImporter.commit_to_db(request.POST["multiImport"])
            self.message_user(request, *result)
        except Exception as e:
            messages.error(request, f"Import failed: {str(e)}")
        return HttpResponseRedirect("../")

    def assign_proxies_to_accounts(self, request):
        """Назначает свободные прокси аккаунтам без прокси"""
        try:
            assigned_count = Proxy.assign_proxies_to_accounts_without_proxy()
            accounts_without_proxy = TwitchAccount.objects.filter(proxy=None).count()
            free_count = Proxy.get_free_proxy_count()
            
            if assigned_count > 0:
                messages.success(
                    request, 
                    f"Успешно назначено {assigned_count} прокси аккаунтам. "
                    f"Аккаунтов без прокси осталось: {accounts_without_proxy}. "
                    f"Свободных прокси: {free_count}."
                )
            else:
                messages.info(
                    request,
                    f"Нет аккаунтов без прокси или нет свободных прокси. "
                    f"Аккаунтов без прокси: {accounts_without_proxy}. "
                    f"Свободных прокси: {free_count}"
                )
        except Exception as e:
            messages.error(request, f"Error assigning proxies: {str(e)}")
        
        return HttpResponseRedirect("../")

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        # Annotate the queryset with a concatenated list of usernames
        queryset = queryset.annotate(
            user_list=GroupConcat('user__username', distinct=True)
        )
        return queryset

    def user_list(self, obj):
        # Use the annotated user_list field
        return obj.user_list

    def proxy_url(self, obj):
        """Отображает URL прокси или сообщение об отсутствии"""
        if obj.proxy:
            return obj.proxy.url
        return "❌ Нет прокси"
    
    proxy_url.short_description = 'Proxy URL'

    user_list.short_description = 'Users'
    user_list.admin_order_field = 'user__username'  # Make the column sortable by user__username

    list_display = ('login', 'token', 'has_proxy', 'proxy_url', 'user_list',)
    list_filter = ('proxy',)
    search_fields = ('login', 'token', 'user__username', 'proxy__url')
    save_on_top = True
    ordering = ('login',)  # Simplified ordering to avoid complex joins
