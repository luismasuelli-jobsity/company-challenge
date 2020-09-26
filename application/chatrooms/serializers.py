from django.core import exceptions as django_exceptions
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from rest_framework.serializers import Serializer, ModelSerializer, CharField, as_serializer_error, ValidationError


class UserCreateSerializer(ModelSerializer):
    """
    Validates and creates a user.
    """

    password = CharField(style={"input_type": "password"}, write_only=True)

    class Meta:
        model = User
        fields = ("username", "email", "password")

    def validate(self, attrs):
        user = User(**attrs)
        password = attrs.get("password")

        try:
            validate_password(password, user)
        except django_exceptions.ValidationError as e:
            serializer_error = as_serializer_error(e)
            raise ValidationError(
                {"password": serializer_error["non_field_errors"]}
            )

        return attrs

    def create(self, validated_data):
        password = validated_data.pop("password")
        instance = super().create(validated_data)
        instance.set_password(password)
        instance.save()
        return instance


class UserLoginSerializer(Serializer):
    """
    User login has only username and password.
    """

    def save(self, **kwargs):
        raise Exception("This serializer is not meant to save any object")

    def create(self, validated_data):
        raise Exception("This serialized is not meant to create any object")

    def update(self, instance, validated_data):
        raise Exception("This serialized is not meant to update any object")

    username = CharField(required=True)
    password = CharField(required=True)

    def validate(self, attrs):
        validated = super().validate(attrs)
        user = authenticate(**validated)
        if user is None:
            raise ValidationError({
                'Username/Password mismatch', 'invalid'
            })
        validated['user'] = user
        return validated
