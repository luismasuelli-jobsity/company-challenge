from django.contrib.auth.mixins import LoginRequiredMixin
from rest_framework.authtoken.models import Token
from rest_framework.generics import CreateAPIView
from rest_framework.response import Response
from rest_framework.views import APIView
from .serializers import UserCreateSerializer, UserLoginSerializer
from .signals import session_destroyed


class UserCreateView(CreateAPIView):
    """
    Registers a user. The iser is immediately available
      for log-in.
    """

    serializer_class = UserCreateSerializer


class UserLoginView(APIView):
    """
    Performs a log-in for a user.
    """

    def post(self, request, *args, **kwargs):
        serializer = UserLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']
        token = Token.objects.get_or_create(user=user)
        # Everything is fine in this login process.
        # Let's return the key.
        return Response({
            'token': token
        }, status=200)


class MyProfileView(APIView, LoginRequiredMixin):
    """
    Retrieves the current user profile.
    """

    def get(self, request, *args, **kwargs):
        return Response({
            "username": request.user.username,
            "email": request.user.email
        }, status=200)


class UserLogoutView(APIView, LoginRequiredMixin):
    """
    Performs a log-out for a user.
    """

    def post(self, request, *args, **kwargs):
        token = Token.objects.get(user=request.user)
        session_destroyed.send(sender=token)
        token.delete()
        return Response('', status=204)
