from django.urls import path
from . import views
 
urlpatterns = [
    path('', views.kick_index, name='kick_index'),
    path('chat/', views.kick_chat, name='kick_chat'),
    path('stats/', views.kick_stats, name='kick_stats'),
    path('api/channel_info/', views.channel_info, name='kick_channel_info'),
    path('api/channel_stream/', views.channel_stream, name='kick_channel_stream'),
    path('api/streams_list/', views.streams_list, name='kick_streams_list'),
    path('api/user_info/', views.channel_info, name='kick_user_info'),
] 