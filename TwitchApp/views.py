from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required, permission_required
from django.core.exceptions import PermissionDenied
from StatsApp.models import Statistic


# Create your views here.
@permission_required(perm="ServiceApp.twitch_chatter", raise_exception=PermissionDenied)
@login_required(login_url="login")
def index_view(request):
    if request.method == "GET":
        return render(request, template_name="TwitchApp/index.html")


@permission_required(perm="ServiceApp.twitch_chatter", raise_exception=PermissionDenied)
@login_required(login_url="login")
def chat_view(request):
    if request.method == "GET":
        return render(request, template_name="TwitchApp/chat.html")
