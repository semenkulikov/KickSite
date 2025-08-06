from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.forms import UserCreationForm, UserChangeForm, AdminPasswordChangeForm
from .models import User, UserRole

class UserRoleAdmin(admin.ModelAdmin):
    list_display = ('name', 'description')
    search_fields = ('name', 'description')
    ordering = ('name',)

class CustomUserCreationForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = User

class CustomUserChangeForm(UserChangeForm):
    class Meta(UserChangeForm.Meta):
        model = User

class CustomUserAdmin(UserAdmin):
    add_form = CustomUserCreationForm
    form = CustomUserChangeForm
    change_password_form = AdminPasswordChangeForm
    model = User
    list_display = ('username', 'email', 'role', 'is_active', 'is_staff', 'is_superuser', 'date_joined')
    list_filter = ('is_active', 'is_staff', 'is_superuser', 'role', 'date_joined')
    search_fields = ('username', 'email', 'first_name', 'last_name')
    ordering = ('username',)

    def get_queryset(self, request):
        """Фильтруем пользователей в зависимости от роли текущего пользователя"""
        qs = super().get_queryset(request)
        
        # Суперпользователь видит всех
        if request.user.is_superuser:
            return qs
        
        # Супер админ видит всех
        if hasattr(request.user, 'is_super_admin') and request.user.is_super_admin:
            return qs
        
        # Обычный админ видит всех пользователей, кроме супер админов
        if hasattr(request.user, 'is_admin') and request.user.is_admin:
            return qs.exclude(role__name=UserRole.SUPER_ADMIN)
        
        # Обычный пользователь видит только себя
        return qs.filter(id=request.user.id)
    
    def has_add_permission(self, request):
        """Обычные админы могут добавлять пользователей"""
        return request.user.is_superuser or (hasattr(request.user, 'is_super_admin') and request.user.is_super_admin) or (hasattr(request.user, 'is_admin') and request.user.is_admin)
    
    def has_change_permission(self, request, obj=None):
        """Права на изменение пользователей"""
        # Суперпользователь может изменять всех
        if request.user.is_superuser:
            return True
        
        # Супер админ может изменять всех
        if hasattr(request.user, 'is_super_admin') and request.user.is_super_admin:
            return True
        
        # Обычный админ может изменять всех, кроме супер админов
        if hasattr(request.user, 'is_admin') and request.user.is_admin:
            if obj is None:  # Список пользователей
                return True
            # Не может изменять супер админов
            if hasattr(obj, 'role') and obj.role and obj.role.name == UserRole.SUPER_ADMIN:
                return False
            return True
        
        # Обычный пользователь может изменять только себя
        if obj and obj.id == request.user.id:
            return True
        
        return False
    
    def has_delete_permission(self, request, obj=None):
        """Только суперпользователи и супер админы могут удалять пользователей"""
        return request.user.is_superuser or (hasattr(request.user, 'is_super_admin') and request.user.is_super_admin)
    
    def has_view_permission(self, request, obj=None):
        """Права на просмотр пользователей"""
        # Суперпользователь видит всех
        if request.user.is_superuser:
            return True
        
        # Супер админ видит всех
        if hasattr(request.user, 'is_super_admin') and request.user.is_super_admin:
            return True
        
        # Обычный админ видит всех, кроме супер админов
        if hasattr(request.user, 'is_admin') and request.user.is_admin:
            if obj and hasattr(obj, 'role') and obj.role and obj.role.name == UserRole.SUPER_ADMIN:
                return False
            return True
        
        # Обычный пользователь видит только себя
        if obj and obj.id == request.user.id:
            return True
        
        return False
    
    fieldsets = UserAdmin.fieldsets + (
        ('Дополнительная информация', {
            'fields': ('role', 'phone', 'telegram')
        }),
    )
    
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Дополнительная информация', {
            'fields': ('role', 'phone', 'telegram')
        }),
    )

admin.site.register(UserRole, UserRoleAdmin)
admin.site.register(User, CustomUserAdmin)
