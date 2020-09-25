from django.core.exceptions import ValidationError
from django.forms import Form
from django.forms.fields import CharField, EmailField
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
    email = EmailField()
    password = CharField(widget=PasswordInput)
    password_confirm = CharField(widget=PasswordInput)

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data['password'] != cleaned_data['password_confirm']:
            raise ValidationError("Passwords do not match")
        return cleaned_data
