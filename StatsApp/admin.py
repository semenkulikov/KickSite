from django.contrib import admin
from StatsApp.models import Statistic
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
