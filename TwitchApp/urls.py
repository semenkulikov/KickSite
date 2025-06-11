from django.urls import re_path
from TwitchApp import views

app_name = 'TwitchApp'

urlpatterns = [
    # Main
    re_path(r'^$', views.index_view, name='twitch_index'),
    re_path(r'^chat$', views.chat_view, name='twitch_chat'),
]
