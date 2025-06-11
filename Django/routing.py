from django.urls import re_path
from Django.consumers import DjangoWS
from TwitchApp.consumers import TwitchAppChatWs, TwitchAppStatsWs

websocket_urlpatterns = [
    re_path(r'^ws/$', DjangoWS.as_asgi()),
    re_path(r'^ws-twitch/chat$', TwitchAppChatWs.as_asgi()),
    re_path(r'^ws-twitch/stats$', TwitchAppStatsWs.as_asgi())
]
