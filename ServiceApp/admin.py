from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .forms import CustomUserCreationForm, CustomUserChangeForm
from .models import User


class UserAdmin(UserAdmin):
    add_form = CustomUserCreationForm
    form = CustomUserChangeForm
    model = User
    search_fields = ('username',)
    list_display = ('username',)
    list_filter = ('is_active',)
    ordering = ('username',)

    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Permissions', {'fields': ('is_staff',)}),
        ('Groups', {'fields': ('groups',)}),
        ('Primary personal information', {
            'fields': ('first_name', 'last_name')}),
        ('Status', {'fields': ('is_active',)}),
    )

    filter_horizontal = ('groups',)


admin.site.register(User, UserAdmin)
