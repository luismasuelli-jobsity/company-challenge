from django.forms import Form
from django.forms.fields import CharField
from django.forms.widgets import PasswordInput
from django.contrib.auth.forms import UsernameField


class LoginForm(Form):
    """
    username/password login form.
    """

    username = UsernameField()
    password = CharField(widget=PasswordInput)


class RegisterForm(Form):
    """
    username/password/confirm login form.
    """

    username = UsernameField()
    password = CharField(widget=PasswordInput)
    password_confirm = CharField(widget=PasswordInput)
