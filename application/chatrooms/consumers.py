import datetime
from asgiref.sync import async_to_sync
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from .models import Room, Message
from .signals import session_destroyed
import logging


logger = logging.getLogger(__name__)


class ChatConsumer(AsyncJsonWebsocketConsumer):
    """
    A chat consumer is aware of:

    - The existing rooms: Only to existing rooms can the consumers
      be joined.
    - A map of (user.id) => channel for the users being logged in.
    """

    USERS = {}
    ROOMS = {}

    @classmethod
    def _on_session_destroyed(cls, sender):
        """
        This handler is invoked when a token session is destroyed.
          The websocket that is connected to this channel server
          is popped out (closed).
        :param sender: The session token being destroyed.
        """

        user = sender.user
        consumer = cls.USERS.get(user and user.id)
        if consumer:
            async_to_sync(consumer.send_json)({"type": "notification", "code": "logged-out"}, True)

    @classmethod
    def _on_room_destroyed(cls, sender, instance, using):
        """
        This handler is invoked when a room is destroyed.
        :param sender: Room class.
        :param instance: A Room instance.
        :param using: 'default'.
        """

        room_consumers = cls.ROOMS.pop(instance.name, set())
        for consumer in room_consumers:
            async_to_sync(consumer.receive_part)(instance.name)

    async def accept_user(self):
        """
        Accepts the current connection, provided it is authenticated
          and not already connected. Also the signal is setup for the
          first time to appropriately end the connection when a session
          ends.
        """

        # Set the signal for when the token sessions are destroyed.
        session_destroyed.connect(self._on_session_destroyed, dispatch_uid='on_session_destroyed')

        user = self.scope["user"]
        if not user or user.is_anonymous:
            await self.send_json({"type": "error", "code": "not-authenticated"}, True)
            return False
        elif user.id in self.USERS:
            await self.send_json({"type": "error", "code": "already-chatting"}, True)
            return False
        else:
            self.USERS[user.id] = self
            await self.accept()
            return True

    async def connect(self):
        """
        A connection lifecycle involves checking the user and then
          sending a greeting message (involving some help).
        """

        # Check the user and accept the connection.
        accepted = await self.accept_user()

        # Send a MOTD with help.
        if accepted:
            await self.send_json({
                "type": "notification",
                "code": "api-motd",
                "content": 'Welcome to finchat!\n\nIf you see this message, this means you\'re using an API '
                           'instead of the given UI. Send a {"type": "help"} message for details about this '
                           'server\'s commands'
            })

    async def disconnect(self, close_code):
        """
        Ensures the connection's user is disconnected from each room,
          and from the server tracking.
        :param close_code: The close code of the connection.
        """

        user = self.scope.get("user")
        if user:
            for room_name in getattr(self, 'rooms', set()):
                await self._notify_user_leaving_room(room_name)
                await self._remove_from_room(room_name)
            self.USERS.pop(user.id, None)

    async def receive_json(self, content, **kwargs):
        """
        Processes the incoming message from the client websocket.

        Allowed commands are:

         - {"type": "help"}
         - {"type": "list"}
         - {"type": "join", "room_name": "..."}
         - {"type": "part", "room_name": "..."}
         - {"type": "message", "room_name": "...", "content": "..."}
         - {"type": "custom", "code": "...", "payload": "..."}
           - These "custom" messages are not stored in log.
           - Special clients may attend these messages when sent
             to a room. One example is:
             {"type": "custom", "code": "stock", "payload": "aapl.us"}
        :param content: The message body.
        :param kwargs: Other arguments - unused.
        """

        # await self.channel_layer.group_send(room_name, ...)
        # ... = {"type": "on_broadcast",  ...more data}

        if not isinstance(content, dict):
            await self.send_json({"type": "error", "code": "invalid-format"})
        else:
            type_ = content.get('type')
            if type_ == "help":
                await self.receive_help()
            elif type_ == "list":
                await self.receive_list()
            if type_ == "join":
                await self.receive_join(content.get('room_name'))
            elif type_ == "part":
                await self.receive_part(content.get('room_name'))
            elif type_ == "message":
                await self.receive_message(content.get('room_name'), content.get('body'))
            elif type_ == "custom":
                await self.receive_custom(content.get('room_name'), content.get('command'), content.get('payload'))
            else:
                await self.send_json({"type": "error", "code": "unsupported-command", "content": type_})

    async def receive_help(self):
        """
        Processes a help command. This command will return
          the help text for this server.
        """

        await self.send_json({"type": "notification", "code": "help", "help": """
        This help is only meaningful if you're using the API directly instead of through the given UI.
        
        The following list of commands are allowed in this server:
        - {"type": "help"}
          - Display this help again.
        - {"type": "list"}
          - List all the available rooms in this server.
        - {"type": "message", "room_name": "making_friends", "body": "Hello everyone!"}
          - Sends "Hello everyone!" to the "making_friends" channel.
          - The channel must exist.
          - You must be already joined in the channel.
        """})

    async def receive_list(self):
        """
        Processes a list command. This command will return
          a list of all the available rooms in the server,
          also telling which one is the user joined to.
        """

        await self.send_json({"type": "notification", "code": "list", "list": [{
            "name": room.name, "joined": room.name in self.rooms
        } for room in Room.objects.order_by('name')]})

    async def _expect_types(self, specs):
        """
        Tells whether the values/types are compatible.
        Notifies the user if there are incompatibilities.
        :param specs: The list of values to check.
        :return: Whether they're all compatible.
        """

        for spec in specs:
            if len(spec) == 2:
                value, type_ = spec
                if not isinstance(value, type_):
                    break
            elif len(spec) == 3:
                value, type_, optional = spec
                if not (optional and value is None) and not isinstance(value, type_):
                    break
        else:
            return True
        await self.send_json({"type": "error", "code": "invalid-format"})
        return False

    async def _add_to_room(self, room_name):
        """
        Adds the user to the room.
        :param room_name: The room to add the user to.
        """

        self.rooms.add(room_name)
        self.ROOMS.setdefault(room_name, set()).add(self)
        await self.channel_layer.group_add(room_name, self.channel_layer)

    async def _remove_from_room(self, room_name):
        """
        Removes the user from the room.
        :param room_name: The room to remove the user from.
        """

        self.ROOMS.setdefault(room_name, set()).discard(self)
        self.rooms.discard(room_name)
        await self.channel_layer.group_discard(room_name, self.channel_layer)

    async def _notify_user_joining_room(self, room_name):
        """
        Tells the room users about the incoming user. The
          current user will also receive the same message.
        :param room_name: The room the user is joining.
        """

        await self.channel_layer.group_send(room_name, {
            "type": "broadcast_joined",
            "user": self.scope["user"].username, "room_name": room_name,
            "stamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })

    async def _send_last_50_room_messages(self, room_name):
        """
        Sends the last 50 messages, of a room, to the user.
        :param room_name: The room to grab the last messages from.
        """

        await self.send_json({"type": "room:notification", "code": "messages", "messages": [
            {"stamp": message.created_on.strftime("%Y-%m-%d %H:%M:%S"),
             "user": message.user.username, "room_name": room_name,
             "body": message.content, "you": message.user == self.scope["user"]}
        for message in reversed(Message.objects.order_by("-created_on")[:50])]})

    async def _send_room_users(self, room_name):
        """
        Sends all the room users (including self) to the user.
        :param room_name: The room to get the users from.
        """

        await self.send_json({"type": "room:notification", "code": "users", "users": sorted([
            user.username for user in self.ROOMS[room_name]
        ])})

    async def receive_join(self, room_name):
        """
        Processes a join command. If the user is not present
          in a room, we join it and notify the whole room.
        :param room_name: The name of the room to join.
        """

        if not self._expect_types([(room_name, str)]):
            return

        try:
            Room.objects.get(name=room_name)
            self.rooms = getattr(self, 'rooms', set())
            if room_name in self.rooms:
                await self.send_json({"type": "error", "code": "room:already-joined", "name": room_name})
            else:
                await self._add_to_room(room_name)
                await self._notify_user_joining_room(room_name)
                await self._send_room_users(room_name)
                await self._send_last_50_room_messages(room_name)
        except Room.DoesNotExist:
            await self.send_json({"type": "error", "code": "room:invalid", "name": room_name})

    async def _notify_user_leaving_room(self, room_name):
        """
        Tells the room users about the leaving user. The
          current user will also receive the same message.
        :param room_name: The room the user is leaving.
        """

        await self.channel_layer.group_send(room_name, {
            "type": "broadcast_parted",
            "user": self.scope["user"].username, "room_name": room_name,
            "stamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })

    async def receive_part(self, room_name):
        """
        Processes a part command. If the user is present in a
          room, we pop it and notify the whole room.
        :param room_name: The name of the room to part from.
        """

        if not self._expect_types([(room_name, str)]):
            return

        self.rooms = getattr(self, 'rooms', set())
        if room_name in self.rooms:
            await self._notify_user_leaving_room(room_name)
            await self._remove_from_room(room_name)
        else:
            await self.send_json({"type": "error", "code": "room:not-joined", "name": room_name})

    def _store_message(self, room_name, body):
        """
        Stores the message, sent by the user, in database.
        :param room_name: The name of the room where the message
          was sent.
        :param body: The message body.
        :return: The stored message
        """

        try:
            return Message.objects.create(room=Room.objects.get(
                name=room_name, content=body[:512], user=self.scope["user"]
            ))
        except Room.DoesNotExist:
            logger.warning("Trying to store a message for non-existing room: " + room_name)

    async def _broadcast_message(self, room_name, body, stamp):
        """
        Broadcasts the message in the channel.
        :param room_name: The room where the message was sent.
        :param body: The message body.
        :param stamp: The message timestamp.
        """

        await self.channel_layer.group_send(room_name, {
            "type": "broadcast_message",
            "user": self.scope["user"].username, "room_name": room_name, "body": body, "stamp": stamp
        })

    async def receive_message(self, room_name, body):
        """
        Processes a message command. If the user is present in the
          intended room, we broadcast the message. Messages are also
          stored in the database when the room exists.
        :param room_name: The name of the room to send the message to.
        :param body: The message body.
        """

        if not self._expect_types([(room_name, str), (body, str)]):
            return

        if room_name in self.rooms:
            body = body.strip()
            if body:
                message = self._store_message(room_name, body)
                await self._broadcast_message(room_name, body, message.created_on.strftime("%Y-%m-%d %H:%M:%S"))
            else:
                await self.send_json({"type": "error", "code": "room:empty-message"})
        else:
            await self.send_json({"type": "error", "code": "room:not-joined", "name": room_name})

    async def _broadcast_custom(self, room_name, code, payload):
        """
        Broadcasts the message in the channel.
        :param room_name: The name of the room to send the custom command to.
        :param code: The payload code.
        :param payload: The payload data.
        """

        await self.channel_layer.group_send(room_name, {
            "type": "broadcast_custom",
            "user": self.scope["user"].username, "room_name": room_name, "code": code, "payload": payload,
            "stamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })

    async def receive_custom(self, room_name, command, payload):
        """
        Processes a custom command. If the user is present in the
          intended room, we broadcast the command. They are never
          stored in the database, and are only useful to bots that
          are also connected to the server.
        :param room_name: The name of the room to send the custom command to.
        :param command: The command code.
        :param payload: The payload data.
        """

        if not self._expect_types([(room_name, str), (command, str), (payload, str)]):
            return

        if room_name in self.rooms:
            command = command.strip()
            if command != '':
                await self._broadcast_custom(room_name, command, payload)
            else:
                await self.send_json({"type": "error", "code": "room:empty-custom"})
        else:
            await self.send_json({"type": "error", "code": "room:not-joined", "name": room_name})

    # From this point, the broadcast_* methods are listed. They
    # have a different logic depending on the user: whether the
    # same or different user broadcast it, how is a notification
    # sent to the client side.

    async def broadcast_joined(self, event):
        """
        Sends a message about a joining user, to the
          current user. If the user is the same, then
          a different message is sent.
        :param event: A {"user": ..., "room_name": ...} message.
        """

        username = event["user"]
        room_name = event["room_name"]
        stamp = event["stamp"]

        await self.send_json({
            "type": "room:notification",
            "code": "joined",
            "you": self.scope["user"].username == username,
            "user": username,
            "room_name": room_name,
            "stamp": stamp
        })

    async def broadcast_parted(self, event):
        """
        Sends a message about a leaving user, to the
          current user. If the user is the same, then
          a different message is sent.
        :param event: A {"user": ..., "room_name": ...} packet.
        """

        username = event["user"]
        room_name = event["room_name"]
        stamp = event["stamp"]

        await self.send_json({
            "type": "room:notification",
            "code": "parted",
            "you": self.scope["user"].username == username,
            "user": username,
            "room_name": room_name,
            "stamp": stamp
        })

    async def broadcast_message(self, event):
        """
        Sends a message about an in-room message,
          by a particular user. If the user is
          the same, a different message is sent.
        :param event: A {"user": ..., "room_name": ...,
          "body": ..., "stamp": ...} packet.
        """

        username = event['user']
        room_name = event['room']
        body = event['body']
        stamp = event['stamp']

        await self.send_json({
            "type": "room:notification",
            "code": "message",
            "you": self.scope["user"].username == username,
            "user": username,
            "room_name": room_name,
            "body": body,
            "stamp": stamp
        })

    async def broadcast_custom(self, event):
        """
        Sends a message about an in-room command,
          by a particular user. If the user is
          the same, a different message is sent.
        :param event: A {"user": ..., "room_name": ...,
          "command": ..., "payload": ..., "stamp": ...}
          packet.
        """

        username = event['user']
        room_name = event['room']
        command = event['command']
        payload = event['payload']
        stamp = event['stamp']

        await self.send_json({
            "type": "room:notification",
            "code": "custom",
            "you": self.scope["user"].username == username,
            "user": username,
            "room_name": room_name,
            "command": command,
            "payload": payload,
            "stamp": stamp
        })
