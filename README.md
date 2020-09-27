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

Manual test
-----------

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
