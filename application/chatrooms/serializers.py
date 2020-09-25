from django.contrib.auth.models import User
from rest_framework.serializers import Serializer, ModelSerializer, CharField


class UserCreateSerializer(ModelSerializer):
    """
    User registration has password and confirmation.
    """

    password = CharField(required=True)
    password_confirm = CharField(required=True)

    class Meta:
        model = User
        fields = ('username', 'password', 'email')


class UserLoginSerializer(Serializer):
    """
    User login has only username and password.
    """

    username = CharField(required=True)
    password = CharField(required=True)
