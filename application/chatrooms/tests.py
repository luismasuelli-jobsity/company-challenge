import pytest
from channels.routing import URLRouter
from django.contrib.auth.models import User
from channels.db import database_sync_to_async
from channels.testing import WebsocketCommunicator
from channels_authtoken import TokenAuthMiddlewareStack
from chatrooms.routing import websocket_urlpatterns
from .models import Room, Message
from .api import UserLoginView, UserCreateView, MyProfileView, UserLogoutView
from rest_framework.test import APIRequestFactory
import logging


# The factory for the requests.
factory = APIRequestFactory()


USERS = ["alice", "bob", "carl", "david", "erin", "frank"]


def make_communicator(token):
    """
    Creates a chatrooms communicator for the given input token.
    :param token: The token to use. It must correspond to a valid
      token (i.e. a user must be logged in with that token).
    :return: The communicator.
    """

    return WebsocketCommunicator(TokenAuthMiddlewareStack(
        URLRouter(
            websocket_urlpatterns
        )
    ), '/ws/chat/?token=' + token)


async def attempt_login(username, password, expect=200):
    """
    Attempts a login with a given username and password.
    :param username: The username to login with.
    :param password: The password to login with.
    :param expect: The http status code to expect.
    :return: The token.
    """

    response = await database_sync_to_async(UserLoginView.as_view())(factory.post('/login', {"username": username, "password": password}))
    assert response.status_code == expect
    return response.data['token']


async def attempt_register(username, password, email, expect=201):
    """
    Attempts a user registration with a given username, password and e-mail.
    :param username: The username to register with.
    :param password: The password to register with.
    :param email: The e-mail to register with.
    :param expect: The http status code to expect.
    """

    response = await database_sync_to_async(UserCreateView.as_view())(factory.post('/register', {"username": username, "password": password, "email": email}))
    assert response.status_code == expect


async def attempt_profile(token, expect=200):
    """
    Attempts a profile retrieval using a given token.
    :param token: The token to use for authentication.
    :param expect: The http status code to expect.
    """

    response = await database_sync_to_async(MyProfileView.as_view())(factory.get('/profile', HTTP_AUTHORIZATION='Token ' + token))
    assert response.status_code == expect


async def attempt_logout(token, expect=204):
    """
    Attempts a logout using a given token.
    :param token: The token to use for authentication.
    :param expect: The http status code to expect.
    """

    response = await database_sync_to_async(UserLogoutView.as_view())(factory.post('/logout', HTTP_AUTHORIZATION='Token ' + token))
    assert response.status_code == expect


@pytest.fixture()
async def rooms():
    """
    Fixture for the rooms.
    :return: Four rooms: "friends", "family", "stockmarket", "forex".
    """

    @pytest.mark.django_db()
    def _rooms():
        return Room.objects.bulk_create([
            Room(name=name) for name in ['friends', 'family', 'stockmarket', 'forex']
        ])
    return await database_sync_to_async(_rooms)()


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_chatrooms(rooms):
    """
    Tests the whole chatrooms interaction, given a valid token, with
      several simultaneous users.
    """

    # Register all the users.
    for name in USERS:
        username = name
        password = name * 2 + '$12345'
        email = name + '@example.org'
        await attempt_register(username, password, email)

    # Login all the users.
    tokens = {}
    for name in USERS:
        username = name
        password = name * 2 + '$12345'
        tokens[name] = await attempt_login(username, password)

    # Test profile for all of them.
    for name in USERS:
        await attempt_profile(tokens[name])

    # "erin" and "frank" will logout.
    for name in ["erin", "frank"]:
        await attempt_logout(tokens[name])

    # "erin" and "frank" are not authorized for the profile endpoint.
    for name in ["erin", "frank"]:
        await attempt_profile(tokens[name], 401)

    # The others are still authorized:
    for name in ["alice", "bob", "carl", "david"]:
        await attempt_profile(tokens[name])

    ####################################################
    #########
    ####################################################
