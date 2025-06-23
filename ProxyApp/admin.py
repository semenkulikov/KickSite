from django.contrib import admin
from django.http import HttpResponseRedirect
from ProxyApp.models import Proxy
from django.urls import path
from ProxyApp.importer import ProxyImporter
from django.db import IntegrityError
from django.contrib import messages
from django.core.exceptions import ValidationError
from django import forms


class ProxyAdminForm(forms.ModelForm):
    """Custom form to handle validation errors gracefully"""
    
    class Meta:
        model = Proxy
        fields = '__all__'
    
    def clean(self):
        cleaned_data = super().clean()
        url = cleaned_data.get('url')
        
        # Check for duplicate URL if this is a new instance
        if url and not self.instance.pk:
            if Proxy.objects.filter(url=url).exists():
                raise ValidationError({
                    'url': 'A proxy with this URL already exists.'
                })
        
        return cleaned_data


@admin.register(Proxy)
class ProxyAdmin(admin.ModelAdmin):
    form = ProxyAdminForm
    change_list_template = "admin/model_change_list.html"

    def save_model(self, request, obj, form, change):
        """Override save_model to handle IntegrityError gracefully"""
        try:
            super().save_model(request, obj, form, change)
        except IntegrityError as e:
            # Handle specific constraint violations
            if 'url' in str(e).lower() or 'unique' in str(e).lower():
                messages.error(
                    request, 
                    f"Error saving proxy: A proxy with this URL already exists. "
                    f"Please enter a different URL."
                )
            else:
                messages.error(
                    request,
                    f"Error saving proxy: {str(e)}"
                )
            # Re-raise to prevent saving
            raise ValidationError("Database constraint violation prevented saving.")

    def get_urls(self):
        urls = super(ProxyAdmin, self).get_urls()
        custom_urls = [
            path("import/", self.process_import, name='process_import'),
        ]
        return custom_urls + urls

    def process_import(self, request):
        try:
            result = ProxyImporter.commit_to_db(request.POST["multiImport"])
            self.message_user(request, *result)
        except Exception as e:
            messages.error(request, f"Import failed: {str(e)}")
        return HttpResponseRedirect("../")

    list_display = ('url', 'status')
    list_filter = ('status', )
    search_fields = ('url', )
    save_on_top = True
    ordering = ('url', )
