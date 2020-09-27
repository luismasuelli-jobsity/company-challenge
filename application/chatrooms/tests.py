import asyncio
import json

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


async def should_be_websocket_welcome(token):
    """
    Attempts a websocket channel connection and expects
      to receive a MOTD.
    :param token: The token to use.
    """

    communicator = make_communicator(token)
    connected, _ = await communicator.connect()
    assert connected
    message = json.loads(await communicator.receive_from())
    await communicator.disconnect()
    assert message.get('type') == 'notification'
    assert message.get('code') == 'api-motd'


async def should_be_websocket_rejected_because_anonymous(token):
    """
    Attempts a websocket channel connection and expects
      to receive a rejection because the user is not
      logged in (invalid token).
    :param token: The token to use.
    """

    communicator = make_communicator(token)
    connected, _ = await communicator.connect()
    assert connected
    message = json.loads(await communicator.receive_from())
    await communicator.disconnect()
    assert message.get('type') == 'fatal'
    assert message.get('code') == 'not-authenticated'


async def should_be_websocket_rejected_because_duplicated(token):
    """
    Attempts a websocket channel connection and expects
      to receive a rejection because the user is already
      logged in and chatting.
    :param token: The token to use.
    """

    communicator = make_communicator(token)
    connected, _ = await communicator.connect()
    assert connected
    message = json.loads(await communicator.receive_from())
    await communicator.disconnect()
    assert message.get('type') == 'fatal'
    assert message.get('code') == 'already-chatting'


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
async def test_chatrooms_accounts(rooms):
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

    ###################################################
    # Now testing the websockets side of the session. #
    ###################################################

    # The four still-valid tokens should connect with no issue.
    for name in ["alice", "bob", "carl", "david"]:
        await should_be_websocket_welcome(tokens[name])

    # The other two, should receive a not-authenticated error.
    for name in ["erin", "frank"]:
        await should_be_websocket_rejected_because_anonymous(tokens[name])

    # Now alice connects and, in the meantime, she should fail
    # to connect again, simultaneously.
    alice_communicator = make_communicator(tokens['alice'])
    alice_connected, _ = await alice_communicator.connect()
    motd_message = json.loads(await alice_communicator.receive_from())
    assert alice_connected
    await should_be_websocket_rejected_because_duplicated(tokens['alice'])

    # Now we destroy the session for alice via logout.
    await attempt_logout(tokens['alice'])
    message = json.loads(await alice_communicator.receive_from())
    # A message will be received: logged-out
    assert message.get('type') == 'notification'
    assert message.get('code') == 'logged-out'
    await alice_communicator.disconnect()
