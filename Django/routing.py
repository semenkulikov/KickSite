from django.urls import re_path
from Django.consumers import DjangoWS
from KickApp.consumers import KickAppChatWs, KickAppStatsWs

websocket_urlpatterns = [
    re_path(r'^ws/$', DjangoWS.as_asgi()),
    re_path(r'^ws-kick/chat$', KickAppChatWs.as_asgi()),
    re_path(r'^ws-kick/stats$', KickAppStatsWs.as_asgi()),
]
