from django.urls import path
from django.shortcuts import redirect
from . import views
 
urlpatterns = [
    # Существующие маршруты
    # path('', views.kick_index, name='kick_index'),  # Закомментирован старый URL
    path('', lambda request: redirect('kick_accounts_dashboard'), name='kick_index'),  # Редирект на управление аккаунтами
    path('chat/', views.kick_chat, name='kick_chat'),
    path('stats/', views.kick_stats, name='kick_stats'),
    path('api/channel_info/', views.channel_info, name='kick_channel_info'),
    path('api/channel_stream/', views.channel_stream, name='kick_channel_stream'),
    path('api/streams_list/', views.streams_list, name='kick_streams_list'),
    path('api/user_info/', views.channel_info, name='kick_user_info'),
    
    # Новые маршруты для управления аккаунтами
    path('accounts/', views.kick_accounts_dashboard, name='kick_accounts_dashboard'),
    path('accounts/assign/<int:account_id>/', views.assign_kick_account, name='assign_kick_account'),
    path('accounts/unassign/<int:assignment_id>/', views.unassign_kick_account, name='unassign_kick_account'),
    path('accounts/add-own/', views.add_own_kick_account, name='add_own_kick_account'),
    path('accounts/ajax-get-users/', views.ajax_get_users, name='ajax_get_users'),
] 