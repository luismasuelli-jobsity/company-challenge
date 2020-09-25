from django.shortcuts import render
from .forms import LoginForm, RegisterForm
import logging


logger = logging.getLogger(__name__)


def index(request):
    """
    A login/signup view.

    GET: It just displays the login and signup form.
    POST: Processes the form errors.
    """

    return render(request, 'chatrooms/front-end.html', {
        'login': LoginForm(initial={}),
        'register': RegisterForm(initial={})
    })
