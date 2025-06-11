from django import forms


class LoginForm(forms.Form):
    login = forms.CharField(widget=forms.TextInput(attrs={
        "type": "text",
        "name": "login__form__username",
        "id": "floatingInput",
        "class": "form-control",
        "placeholder": "name@example.com",
    }))
    password = forms.CharField(widget=forms.TextInput(attrs={
        "type": "password",
        "name": "login__form__password",
        "id": "floatingPassword",
        "class": "form-control",
        "placeholder": "Password",
    }))