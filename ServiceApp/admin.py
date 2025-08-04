from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User, UserRole

class UserRoleAdmin(admin.ModelAdmin):
    list_display = ('name', 'description')
    search_fields = ('name', 'description')
    ordering = ('name',)

class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'is_active', 'date_joined')
    list_filter = ('is_active', 'is_staff', 'date_joined')
    search_fields = ('username', 'email', 'first_name', 'last_name')
    ordering = ('username',)

    def get_queryset(self, request):
        """Фильтруем пользователей в зависимости от роли текущего пользователя"""
        qs = super().get_queryset(request)
        
        # Супер админ видит всех
        if request.user.is_superuser or (hasattr(request.user, 'is_super_admin') and request.user.is_super_admin):
            return qs
        
        # Обычный админ видит всех пользователей, кроме супер админов
        if hasattr(request.user, 'is_admin') and request.user.is_admin:
            return qs.exclude(role__name='super_admin')
        
        # Обычный пользователь видит только себя
        return qs.filter(id=request.user.id)
    
    def has_add_permission(self, request):
        """Обычные админы не могут добавлять пользователей"""
        if request.user.is_superuser:
            return True
        return False
    
    def has_change_permission(self, request, obj=None):
        """Обычные админы могут изменять только обычных пользователей"""
        if request.user.is_superuser:
            return True
        elif hasattr(request.user, 'role') and request.user.role and request.user.role.name == 'ADMIN':
            if obj and hasattr(obj, 'role') and obj.role and obj.role.name == 'USER':
                return True
        return False
    
    def has_delete_permission(self, request, obj=None):
        """Обычные админы не могут удалять пользователей"""
        if request.user.is_superuser:
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
