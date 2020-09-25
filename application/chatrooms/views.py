from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.shortcuts import render, redirect
from .forms import LoginForm, RegisterForm


def welcome(request):
    """
    A login/signup view.

    GET: It just displays the login and signup form.
    POST: Processes the form errors.
    """

    if request.method == 'GET':
        return render(request, 'chatrooms/welcome.html', {
            'login': LoginForm(initial={}, prefix='login'),
            'register': RegisterForm(initial={}, prefix='register')
        })
    else:
        if 'login_username' in request.POST:
            form = LoginForm(request.POST, prefix='login')
            if not form.is_valid():
                for key, errors in form.errors.items():
                    for error in errors:
                        messages.error(request, error)
                for error in form.non_field_errors():
                    messages.error(request, error)
            else:
                data = form.cleaned_data
                username = data['username']
                password = data['password']
                user = authenticate(username=username, password=password)
                if user is None:
                    messages.error(request, "Username/Password mismatch")
                    return render(request, 'chatrooms/welcome.html', {
                        'login': LoginForm(initial={'username': username}, prefix='login'),
                        'register': RegisterForm(initial={}, prefix='register')
                    })
                else:
                    login(request, user)
                    return redirect('chatrooms:main')
        elif 'register_username' in request.POST:
            form = RegisterForm(request.POST, prefix='register')
            if not form.is_valid():
                for key, errors in form.errors.items():
                    for error in errors:
                        messages.error(request, error)
                for error in form.non_field_errors():
                    messages.error(request, error)
            else:
                data = form.cleaned_data
                username = data['username']
                email = data['email']
                password = data['password']
                # First, the username must be normalized and
                # also a check must be done to ensure the
                # username is not in-use.
                username = User.normalize_username(username)
                if User.objects.filter(username=username):
                    messages.error(request, "The username is already in use")
                    return render(request, 'chatrooms/welcome.html', {
                        'login': LoginForm(initial={}, prefix='login'),
                        'register': RegisterForm(initial={'username': username}, prefix='register')
                    })
                # Then the user is created.
                try:
                    User.objects.create_user(username, email, password)
                except:
                    messages.error(request, "An unknown error has occurred while creating the user")
                    return render(request, 'chatrooms/welcome.html', {
                        'login': LoginForm(initial={}, prefix='login'),
                        'register': RegisterForm(initial={'username': username}, prefix='register')
                    })
                # Finally, login the new user.
                login(request, authenticate(username=username, password=password))
                return redirect('chatrooms:main')
        else:
            return redirect('chatrooms:welcome')


@login_required
def goodbye(request):
    logout(request)
    return render(request, 'chatrooms/goodbye.html')


@login_required
def main(request):
    return render(request, 'chatrooms/main.html')
