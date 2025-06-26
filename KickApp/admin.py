from django.contrib import admin
from .models import KickAccount
from ProxyApp.models import Proxy
from django import forms
from django.urls import path
from django.shortcuts import render, redirect
from django.contrib import messages
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
    list_display = ('login', 'user', 'proxy', 'status', 'created', 'updated')
    search_fields = ('login',)
    list_filter = ('status', 'proxy')
    change_list_template = "admin/KickApp/kickaccount/change_list.html"

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('mass_import/', self.admin_site.admin_view(self.mass_import_view), name='kickaccount_mass_import'),
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
                            user=request.user,
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

# admin.site.unregister(KickAccount)  # Удалено, чтобы не было ошибки NotRegistered
admin.site.register(KickAccount, KickAccountAdmin)
