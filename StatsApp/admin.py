from django.contrib import admin
from StatsApp.models import Statistic, Shift, ShiftLog
from django.conf import settings


@admin.register(Statistic)
class StatisticAdmin(admin.ModelAdmin):
    list_display = ('user', 'data_count', 'duration')
    list_filter = ('start', 'end')
    save_on_top = True
    ordering = ('start', 'end')

    change_form_template = "admin/model_change_form.html"

    # FIXME Fix after develop
    if settings.DEBUG:
        def has_add_permission(self, request) -> bool:
            return False

        def has_change_permission(self, request, obj=None) -> bool:
            return False


@admin.register(Shift)
class ShiftAdmin(admin.ModelAdmin):
    list_display = ('user', 'start_time', 'end_time', 'duration_display', 'total_messages', 'average_speed', 'timeouts_count', 'is_active')
    list_filter = ('is_active', 'start_time', 'user')
    search_fields = ('user__username',)
    readonly_fields = ('start_time', 'end_time', 'total_messages', 'average_speed', 'timeouts_count', 'total_timeout_duration')
    ordering = ('-start_time',)
    
    def duration_display(self, obj):
        return obj.duration_str
    duration_display.short_description = 'Duration'


@admin.register(ShiftLog)
class ShiftLogAdmin(admin.ModelAdmin):
    list_display = ('shift', 'timestamp', 'action_type', 'description_preview')
    list_filter = ('action_type', 'shift__user', 'timestamp')
    search_fields = ('shift__user__username', 'description')
    readonly_fields = ('timestamp', 'shift', 'action_type', 'description', 'details')
    ordering = ('-timestamp',)
    
    def description_preview(self, obj):
        return obj.description[:100] + '...' if len(obj.description) > 100 else obj.description
    description_preview.short_description = 'Description'
