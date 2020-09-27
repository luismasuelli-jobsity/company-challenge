# Financial Chat

This application consists of the following components:

 - A compose file with three containers:
   - A postgreql (version 13) database.
   - A redis (version 6) database.
   - The server application.
 - A decoupled bot, which connects to the server and attends commands.

Installation
------------

First, copy `.env.sample` as `.env`. This has several configurations related to database and redis settings.

The second step requires Docker and, in particular, `docker-compose`. Once the .env file is configured appropriately,
the whole stack can be run with the following command:

    $ docker-compose up

Be wary, for the stack will fail if one or more of the following ports are already used by another process:

 - 8000, used by the web server.
 - 6379, used by Redis, just for debugging purposes.
 - 15432, used by PostgreSQL.

The third step involves copying the static files, migrating the database, and setting the site's superuser:

    $ docker-compose exec server bash
    root@container-id:/code# sh setup.sh
    # ... a lot of prompt involving copying static files and migrations
    # ... the prompt is slightly interactive.
    root@container-id:/code# python manage.py createsuperuser
    Username (leave blank to use 'root'): su-username-of-choice
    Email address: username@whatev.er
    Password: (custom password)
    Password (again): (same custom password)

If everything goes OK, now you have a running Django application.

Setup
-----

Go to [the admin site](http://localhost:8000/admin) with the chosen username and password.
Create more than one room. As an example, create these rooms:

 - friends: This is a regular room. Chat-only.
 - family: This is a regular room as well. Chat-only.
 - investments: This will be a special room in the next section. Just for now, it is as regular as the others.

Manual web test
---------------

Once the rooms are created, [visit the site](http://localhost:8000/admin).  

You have two available forms:

 - Register: Creates a new user and automatically logs in.
 - Login: Logs in with an existing user.

This test involves opening several different browser sessions, like:

 - Normal and incognito / private browser sessions.
 - Sessions in different browsers.

And registering (via the register form, with different usernames and e-mails) several users.

 - "Server Logs" room: This is intended for server commands.
 - "Refresh rooms": Refreshes the whole rooms list.
 - room link(s): They will exist provided you created some rooms, like the 3 sample rooms already mentioned.
 
Clicking a room link will lead the user to a room, displaying:

 - History: Up to the last 50 messages in the room.
 - User list: The currently connected users.
 - Current messages:
   - Regular messages: Once received they will be stored and become part of the history.
   - Join notifications: They will not be stored, and will appear in green. Notify when a user joins the room.
   - Part notifications: They will not be stored, and will appear in red. Notify when a user leaves the room.
   - Commands: They will not be stored, and will appear in purple. They look like /foo=bar.

So far, issuing commands does nothing. To make them work, a custom API client or bot must exist.

API flow & docs
---------------

If you want to use a custom client to connect to this API, you will need two components:

 - A REST client that will hit the following endpoints:
   - POST /register: If you send a json like `{"username": "youruser", "password": "yourpassword", "email": "your@email"}`
     and a content-type of application/json, a `200`-status response will carry the whole new user data if valid.
   - POST /login: If you send a json like `{"username": "youruser", "password": "yourpassword"}` and a content-type of
     application/json, a `200`-status response will carry a `{"token": "foo..."}` payload if valid. Keep the `"foo..."` somewhere.
   - POST /logout: Passing an `Authorization: Token foo...` header will attempt a logout. The expected status code is `204`.
   - GET /profile: Passing an `Authorization: Token foo...` header will attempt to retrieve the profile data. When valid,
     a `200`-status response will carry a `{"username": "youruser", "email": "your@email"}` payload.
 - A Websockets client, provided it is fully compatible with the default browser protocols. All the messages being sent
   via that websocket are of text format, and will have a json structure. To build a websocket request, two alternatives exist:
   - Connect to `ws://localhost:8000/ws/chat?token=foo...`.
   - Connect to `ws://localhost:8000/ws/chat` with a `Authorization: Token foo...` header.

A client websocket can send the following messages (as string values) once it is connected:

 - `{"type": "help"}`
   - Display this help again.
 - `{"type": "list"}`
   - List all the available rooms in this server.
 - `{"type": "message", "room_name": "making_friends", "body": "Hello everyone!"}`
   - Sends "Hello everyone!" to the "making_friends" channel.
   - The channel must exist.
   - It must be already joined in the channel.
 - `{"type": "message", "room_name": "making_friends", "command": "foo", "payload": "bar"}`
   - Sends "a /foo=bar" command to the "making_friends" channel.
   - The channel must exist.
   - It must be already joined in the channel.
 - `{"type": "join", "room_name": "making_friends"}`
   - Joins the channel, if not already joined.
 - `{"type": "part", "room_name": "making_friends"}`
   - Leaves the channel, if already joined.

And may receive the following messages from the server:

 - `{"type": "notification", "code": "api-motd": "content": "..."}`
   - A Message Of The Day, received right upon connection, only for API clients.
 - `{"type": "notification", "code": "logged-out"}`
   - Received when the session was destroyed via HTTP logout.
   - The user is being disconnected from the chat room as well.
 - `{"type": "notification", "code": "list", "list": [{"name": "...", "joined": bool}, ...]}`
   - Received as response to a room-listing command.
   - Retrieves the name of each room and a flag telling whether the user is already in that room.
 - `{"type": "fatal", "code": "not-authenticated"}`
   - Received when trying to connect to the chatroom without authentication token.
   - The connection to the chatroom is then closed.
 - `{"type": "fatal", "code": "already-chatting"}`
   - Received when trying to connect to the chatroom being authenticated with a user who is already in the chatroom.
   - The connection to the chatroom is then closed.
 - `{"type": "error", "code": "invalid-format"}`
   - Received as response to a JSON message not being a literal object.
   - Also received when one or more fields of the message do not come in the appropriate type.
 - `{"type": "error", "code": "unsupported-command", "details": {"type": "..."}}`
   - Received as response to a JSON message with an unknown command type.
 - `{"type": "error", "code": "room:empty-message"}`
   - Received as response when a sent message is empty.
 - `{"type": "error", "code": "room:empty-custom"}`
   - Received as response when a sent custom command has empty command code or payload.
 - `{"type": "error", "code": "room:not-joined", "details": {"name": "..."}}`
   - Received when trying to leave a room, send a message, or send a custom command from a user
     not present in that room.
 - `{"type": "error", "code": "room:already-joined", "details": {"name": room_name}}`
   - Received when trying to join a room, a user who is already present in that room.
 - `{"type": "error", "code": "room:invalid", "details": {"name": room_name}}`
   - Received when trying to join a non-existing room.
 - `{"type": "room:notification", "code": "joined", "you": bool, "user": username, "room_name": room_name, "stamp": stamp}`
   - Received when any user joins a room the current user is in.
   - It will have the `you` flag in true, if the user who joins is the current one.
   - In that case, it will also have a value under the `"status"` key with two member keys itself:
     - `"users"`: A structure like `[{"name": "...", "you": bool}, ...]` with all the users (including the current one)
       currently in the room.
     - `"messages"`: A descending-ordered list of the last 50 messages posted in this room. The structure has the format:
       `[{"stamp": "2020-09-26 12:12:13", "user": "...", "you": bool, "body": "..."}]`.
       - They will have the `you` flag in true, if the user who leaves is the current one.
 - `{"type": "room:notification", "code": "parted", "you": bool, "user": username, "room_name": room_name, "stamp": stamp}`
   - Received when any user leaves a room the current user is in.
   - It will have the `you` flag in true, if the user who leaves is the current one.
 - `{"type": "room:notification", "code": "message", "you": bool, "user": "...", "room_name": "...", "body": "...", "stamp": "2020-09-26 12:12:13"}`
   - Received when any user posts a message in a room the current user is in.
   - It will have the `you` flag in true, if the user who posted it is the current one.
 - `{"type": "room:notification", "code": "custom", "you": bool, "user": "...", "room_name": "...", "command": "...", "payload": "...", "stamp": "2020-09-26 12:12:13"}`
   - Received when any user posts a command in a room the current user is in.
   - It will have the `you` flag in true, if the user who posted it is the current one.
   - Bots will typically pay attention to these messages.

Bot
---

You can run the bot included in this repository to answer stock queries. There are two ways to run this both:

 - As a python script:
   - Pros: You need no additional docker setup for networking.
   - Cons: You need to manually install the dependencies in `requirements.txt` in a virtualenv.
 - As a docker image:
   - Pros: Running and ensuring dependencies is straightforward.
   - Cons: You need to configure an external network for both the docker-compose file for the application
           or constrain yourself to configure an external, public url, where you have the server application.

To work with the bot, first ensure you create a standard user for the bot (by manual registration or django admin).

The related environment variables for the bot are:

 - `FINBOT_HOST`: An optional host. If omitted or empty, localhost:8000 will be used.
 - `FINBOT_USERNAME`: The username for the bot account.
 - `FINBOT_PASSWORD`: The password for the bot account.
 - `FINBOT_ROOMS`: A colon-separated list of existing rooms for the bot to connect to.
   This environment variable may be absent or empty. In this case, the bot will list
   all the rooms and join all of them.

As long as the host is reachable, the credentials are valid, at least one room is valid, and the account is not 
already in-use, this bot will respond to commands like /stock=aapl.us or /stock=WIG and ignore other commands.

To run the bot via command line, an example would be:

```
$ FINBOT_USERNAME=botuser FINBOT_PASSWORD=botpwassword FINBOT_ROOMS=investments python bot.py
```

To run the bot via docker, an example would be:

```
$ docker build . --tag=finbot:latest && docker run --name=my-bot-container -e FINBOT_USERNAME=botuser -e FINBOT_PASSWORD=botpwassword -e FINBOT_ROOMS=investments -e FINBOT_HOST=foo.bar.baz:8888 finbot:latest
```