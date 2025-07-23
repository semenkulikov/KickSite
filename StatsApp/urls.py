from django.urls import path
from . import views

app_name = 'StatsApp'

urlpatterns = [
    path('shifts/', views.shift_statistics, name='shift_statistics'),
    path('shifts/user/<int:user_id>/', views.user_shifts, name='user_shifts'),
    path('shifts/<int:shift_id>/details/', views.shift_details, name='shift_details'),
    path('shifts/<int:shift_id>/download/', views.shift_log_download, name='shift_log_download'),
] 