#!/bin/sh
# A small setup file to run the staticfiles collection and database migration.
# This file should be manually run via docker exec, and not during build.
DIR=`pwd`
cd /code
python manage.py collectstatic
python manage.py migrate
cd $DIR
