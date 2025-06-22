from django.shortcuts import render, redirect

from Django.forms import LoginForm
from django.contrib.auth import authenticate, login
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required


@login_required(login_url="login")
def index_view(request):
    if request.method == "GET":
        return render(request, template_name="index.html",)


def login_view(request):
    if request.user.is_authenticated:
        return redirect("/")

    login_form = LoginForm(request.POST)
    if login_form:
        if login_form.is_valid():
            input_login = login_form.cleaned_data["login"]
            input_password = login_form.cleaned_data["password"]

            user = authenticate(username=input_login, password=input_password)
            if user is not None:
                login(request, user)
                return redirect(request.path)
            else:
                return render(request,
                              template_name="login.html",
                              context={"form": login_form, "errors": "Incorrect login or password"})

    return render(request, template_name="login.html", context={"form": login_form})


def logout_view(request):
    logout(request)
    return redirect("/")

# ERRORS VIEWS
# ======================================================================================================================


# HTTP Error 404
def page_not_found(request, exception):
    return render(request,
                  template_name="error_page.html",
                  status=404,
                  context={"header": "404 | Page not found",
                           "text": "We don't have such a page :("})


# HTTP Error 500
def error_view(request, exception):
    return render(request,
                  template_name="error_page.html",
                  status=500,
                  context={"header": "500 | Error accessing the service",
                           "text": "We are already working on this bug. Try to log in after a while"})


# HTTP Error 403
def permission_denied_view(request, exception):
    return render(request,
                  template_name="error_page.html",
                  status=403,
                  context={"header": "403 | Access error",
                           "text": "You do not have access to this page"})


# HTTP Error 400
def bad_request(request, exception):
    return render(request,
                  template_name="error_page.html",
                  status=400,
                  context={"header": "400 | Invalid request",
                           "text": "The request cannot be understood by the server."})