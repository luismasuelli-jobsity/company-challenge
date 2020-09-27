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
ROOMS = ['friends', 'family', 'stockmarket', 'forex']


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
    message = await communicator.receive_json_from()
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
    message = await communicator.receive_json_from()
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
    message = await communicator.receive_json_from()
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
    _ = await alice_communicator.receive_json_from()
    assert alice_connected
    await should_be_websocket_rejected_because_duplicated(tokens['alice'])

    # Now we destroy the session for alice via logout.
    await attempt_logout(tokens['alice'])
    message = await alice_communicator.receive_json_from()
    # A message will be received: logged-out
    assert message.get('type') == 'notification'
    assert message.get('code') == 'logged-out'
    await alice_communicator.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_chatroom_commands():
    """
    Tests all the commands exchanged via the chatrooms.
    This includes double-join and double-part.
    """

    # Login all the users.
    tokens = {}
    for name in USERS:
        username = name
        password = name * 2 + '$12345'
        tokens[name] = await attempt_login(username, password)

    # Alice will:
    # 1. Connect and retrieve MOTD.
    # 2. List rooms, and expect the four in the example.
    # 3. Join "family" room, and receive a success.
    # 4. List rooms, and expect the four ones, with "family" having "joined": true.
    # 3. Join "family" room, and receive an error.
    # 4. List rooms, and expect the four ones, with "family" having "joined": true.
    alice_communicator = make_communicator(tokens['alice'])
    alice_connected, _ = await alice_communicator.connect()
    motd = await alice_communicator.receive_json_from()
    assert motd['type'] == 'notification'
    assert motd['code'] == 'api-motd'
    await alice_communicator.send_json_to({'type': 'list'})
    list_ = await alice_communicator.receive_json_from()
    assert list_['type'] == 'notification'
    assert list_['code'] == 'list'
    assert list_['list'] == [{'name': 'family', 'joined': False}, {'name': 'forex', 'joined': False}, {'name': 'friends', 'joined': False}, {'name': 'stockmarket', 'joined': False}]
    await alice_communicator.send_json_to({'type': 'join', 'room_name': 'family'})
    joined = await alice_communicator.receive_json_from()
    assert joined['type'] == 'room:notification'
    assert joined['code'] == 'joined'
    assert joined['user'] == 'alice'
    assert joined['you']
    assert joined['room_name'] == 'family'
    await alice_communicator.send_json_to({'type': 'list'})
    list_ = await alice_communicator.receive_json_from()
    assert list_['type'] == 'notification'
    assert list_['code'] == 'list'
    assert list_['list'] == [{'name': 'family', 'joined': True}, {'name': 'forex', 'joined': False}, {'name': 'friends', 'joined': False}, {'name': 'stockmarket', 'joined': False}]
    await alice_communicator.send_json_to({'type': 'join', 'room_name': 'family'})
    error = await alice_communicator.receive_json_from()
    assert error['type'] == 'error'
    assert error['code'] == 'room:already-joined'
    assert error['details']['name'] == 'family'
    await alice_communicator.send_json_to({'type': 'list'})
    list_ = await alice_communicator.receive_json_from()
    assert list_['type'] == 'notification'
    assert list_['code'] == 'list'
    assert list_['list'] == [{'name': 'family', 'joined': True}, {'name': 'forex', 'joined': False}, {'name': 'friends', 'joined': False}, {'name': 'stockmarket', 'joined': False}]
    # Bob will:
    # 1. Connect and retrieve MOTD.
    # 2. Join "family" room, and receive a success.
    # 3. Send a message in the "family" room: "Hello Alice", and receive a success.
    # 4. Leave the room, and receive a success.
    # 5. Leave the room, and receive an error.
    # 6. Disconnect.
    # Alice will:
    # 1. Receive the "Bob joined" message.
    # 2. Receive the "Hello Alice" message.
    # 3. Receive the "Bob left" message.
    # ~~ Bob interactions ~~
    bob_communicator = make_communicator(tokens['bob'])
    bob_connected, _ = await bob_communicator.connect()
    motd = await bob_communicator.receive_json_from()
    assert motd['type'] == 'notification'
    assert motd['code'] == 'api-motd'
    await bob_communicator.send_json_to({'type': 'join', 'room_name': 'family'})
    joined = await bob_communicator.receive_json_from()
    assert joined['type'] == 'room:notification'
    assert joined['code'] == 'joined'
    assert joined['user'] == 'bob'
    assert joined['you']
    assert joined['room_name'] == 'family'
    await bob_communicator.send_json_to({'type': 'message', 'room_name': 'family', 'body': 'Hello Alice'})
    message = await bob_communicator.receive_json_from()
    assert message['type'] == 'room:notification'
    assert message['code'] == 'message'
    assert message['you']
    assert message['user'] == 'bob'
    assert message['room_name'] == 'family'
    assert message['body'] == 'Hello Alice'
    await bob_communicator.send_json_to({'type': 'part', 'room_name': 'family'})
    parted = await bob_communicator.receive_json_from()
    assert parted['type'] == 'room:notification'
    assert parted['code'] == 'parted'
    assert parted['user'] == 'bob'
    assert parted['you']
    assert parted['room_name'] == 'family'
    await bob_communicator.send_json_to({'type': 'part', 'room_name': 'family'})
    error = await bob_communicator.receive_json_from()
    assert error['type'] == 'error'
    assert error['code'] == 'room:not-joined'
    assert error['details']['name'] == 'family'
    await bob_communicator.disconnect()
    # ~~ Alice interactions ~~
    joined = await alice_communicator.receive_json_from()
    assert joined['type'] == 'room:notification'
    assert joined['code'] == 'joined'
    assert joined['user'] == 'bob'
    assert not joined['you']
    assert joined['room_name'] == 'family'
    message = await alice_communicator.receive_json_from()
    assert message['type'] == 'room:notification'
    assert message['code'] == 'message'
    assert not message['you']
    assert message['user'] == 'bob'
    assert message['room_name'] == 'family'
    assert message['body'] == 'Hello Alice'
    parted = await alice_communicator.receive_json_from()
    assert parted['type'] == 'room:notification'
    assert parted['code'] == 'parted'
    assert parted['user'] == 'bob'
    assert not parted['you']
    assert parted['room_name'] == 'family'
    await alice_communicator.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db
async def test_chatroom_broadcast():
    """
    Test the actions of a user, in a room, and how is it reflected
      to other users.
    """

    # Login all the users.
    tokens = {}
    for name in USERS:
        username = name
        password = name * 2 + '$12345'
        tokens[name] = await attempt_login(username, password)

    # Alice, Bob, Carl connect to the server.
    communicators = {}
    for name in ['alice', 'bob', 'carl']:
        communicator = make_communicator(tokens[name])
        communicators[name] = communicator
        connected, _ = await communicator.connect()
        assert connected
        motd = await communicator.receive_json_from()
        assert motd['type'] == 'notification'
        assert motd['code'] == 'api-motd'
        await communicator.send_json_to({'type': 'join', 'room_name': 'family'})
        await asyncio.sleep(0.5)
    # Alice expects 3 joins.
    joined = await communicators['alice'].receive_json_from()
    assert joined['type'] == 'room:notification'
    assert joined['code'] == 'joined'
    assert joined['user'] == 'alice'
    assert joined['you']
    assert joined['room_name'] == 'family'
    joined = await communicators['alice'].receive_json_from()
    assert joined['type'] == 'room:notification'
    assert joined['code'] == 'joined'
    assert joined['user'] == 'bob'
    assert not joined['you']
    assert joined['room_name'] == 'family'
    joined = await communicators['alice'].receive_json_from()
    assert joined['type'] == 'room:notification'
    assert joined['code'] == 'joined'
    assert joined['user'] == 'carl'
    assert not joined['you']
    assert joined['room_name'] == 'family'
    # Bob expects 2 joins.
    joined = await communicators['bob'].receive_json_from()
    assert joined['type'] == 'room:notification'
    assert joined['code'] == 'joined'
    assert joined['user'] == 'bob'
    assert joined['you']
    assert joined['room_name'] == 'family'
    joined = await communicators['bob'].receive_json_from()
    assert joined['type'] == 'room:notification'
    assert joined['code'] == 'joined'
    assert joined['user'] == 'carl'
    assert not joined['you']
    assert joined['room_name'] == 'family'
    # Carl expects 1 join.
    joined = await communicators['carl'].receive_json_from()
    assert joined['type'] == 'room:notification'
    assert joined['code'] == 'joined'
    assert joined['user'] == 'carl'
    assert joined['you']
    assert joined['room_name'] == 'family'
    # Now Alice sends a "Hello guys" message, and bob and carl
    # will read it.
    await communicators['alice'].send_json_to({'type': 'message', 'room_name': 'family', 'body': 'Hello guys'})
    message = await communicators['alice'].receive_json_from()
    assert message['type'] == 'room:notification'
    assert message['code'] == 'message'
    assert message['you']
    assert message['user'] == 'alice'
    assert message['room_name'] == 'family'
    assert message['body'] == 'Hello guys'
    message = await communicators['bob'].receive_json_from()
    assert message['type'] == 'room:notification'
    assert message['code'] == 'message'
    assert not message['you']
    assert message['user'] == 'alice'
    assert message['room_name'] == 'family'
    assert message['body'] == 'Hello guys'
    message = await communicators['carl'].receive_json_from()
    assert message['type'] == 'room:notification'
    assert message['code'] == 'message'
    assert not message['you']
    assert message['user'] == 'alice'
    assert message['room_name'] == 'family'
    assert message['body'] == 'Hello guys'
    # Now they all leave the channel.
    for name in ['alice', 'bob', 'carl']:
        await communicators[name].send_json_to({'type': 'part', 'room_name': 'family'})
        await asyncio.sleep(0.5)
    # And they will receive all the part messages.
    parted = await communicators['alice'].receive_json_from()
    assert parted['type'] == 'room:notification'
    assert parted['code'] == 'parted'
    assert parted['user'] == 'alice'
    assert parted['you']
    assert parted['room_name'] == 'family'
    parted = await communicators['bob'].receive_json_from()
    assert parted['type'] == 'room:notification'
    assert parted['code'] == 'parted'
    assert parted['user'] == 'alice'
    assert not parted['you']
    assert parted['room_name'] == 'family'
    parted = await communicators['bob'].receive_json_from()
    assert parted['type'] == 'room:notification'
    assert parted['code'] == 'parted'
    assert parted['user'] == 'bob'
    assert parted['you']
    assert parted['room_name'] == 'family'
    parted = await communicators['carl'].receive_json_from()
    assert parted['type'] == 'room:notification'
    assert parted['code'] == 'parted'
    assert parted['user'] == 'alice'
    assert not parted['you']
    assert parted['room_name'] == 'family'
    parted = await communicators['carl'].receive_json_from()
    assert parted['type'] == 'room:notification'
    assert parted['code'] == 'parted'
    assert parted['user'] == 'bob'
    assert not parted['you']
    assert parted['room_name'] == 'family'
    parted = await communicators['carl'].receive_json_from()
    assert parted['type'] == 'room:notification'
    assert parted['code'] == 'parted'
    assert parted['user'] == 'carl'
    assert parted['you']
    assert parted['room_name'] == 'family'
    # And the 3 will disconnect.
    for name in ['alice', 'bob', 'carl']:
        await communicator.disconnect()
