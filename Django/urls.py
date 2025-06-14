"""
URL configuration for Django project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path

from django.urls import include, re_path
from django.conf import settings
from django.conf.urls.static import static
from Django import views

# from django.conf.urls import (handler400, handler403, handler404, handler500)

urlpatterns = [re_path(r"^login", views.login_view, name='login'),
               re_path(r'^panel/', admin.site.urls),
               re_path(r'^logout', views.logout_view, name='logout'),
               re_path(r"^twitch/", include('TwitchApp.urls')),
               re_path(r"^$", views.index_view, name='index'),
               ] + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

handler404 = 'Django.views.page_not_found'
handler500 = 'Django.views.error_view'
handler403 = 'Django.views.permission_denied_view'
handler400 = 'Django.views.bad_request'
