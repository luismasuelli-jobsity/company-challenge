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