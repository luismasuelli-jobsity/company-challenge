from rest_framework.authtoken.models import Token
from rest_framework.generics import CreateAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from .serializers import UserCreateSerializer, UserLoginSerializer
from .signals import session_destroyed
import logging


logger = logging.getLogger(__name__)


class UserCreateView(CreateAPIView):
    """
    Registers a user. The iser is immediately available
      for log-in.
    """

    authentication_classes = ()

    serializer_class = UserCreateSerializer


class UserLoginView(APIView):
    """
    Performs a log-in for a user.
    """

    authentication_classes = ()

    def post(self, request, *args, **kwargs):
        serializer = UserLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']
        token, _ = Token.objects.get_or_create(user=user)
        # Everything is fine in this login process.
        # Let's return the key.
        return Response({
            'token': token.key
        }, status=200)


class MyProfileView(APIView):
    """
    Retrieves the current user profile.
    """

    permission_classes = (IsAuthenticated,)

    def get(self, request, *args, **kwargs):
        logger.debug("Profile: ok")
        return Response({
            "username": request.user.username,
            "email": request.user.email
        }, status=200)


class UserLogoutView(APIView):
    """
    Performs a log-out for a user.
    """

    permission_classes = (IsAuthenticated,)

    def post(self, request, *args, **kwargs):
        logger.debug("Logout: ok")
        token = Token.objects.get(user=request.user)
        session_destroyed.send(sender=token)
        token.delete()
        return Response(status=204)
