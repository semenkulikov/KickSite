from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from django.contrib.auth.forms import ReadOnlyPasswordHashField
from ServiceApp.models import User
from django import forms


class CustomUserCreationForm(UserCreationForm):

    class Meta:
        model = User
        fields = ("username",)


class CustomUserChangeForm(UserChangeForm):

    class Meta:
        model = User
        fields = ("username",)
