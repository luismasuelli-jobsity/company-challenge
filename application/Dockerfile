FROM python:3
ENV PYTHONUNBUFFERED=1
# Remember: during build time the volumes do not exist.
# This means that the /code directory must be created
# manually, and then the WORKDIR must be set (which is
# a build-time setting and also for the CMD execution),
# and also all the needed files must be manually moved
# (even being later available in the same /code volume).
RUN mkdir /code
WORKDIR /code
COPY requirements.txt /code
RUN pip install --upgrade pip
RUN pip install -r requirements.txt
# Special care to be taken regarding the binding interface:
# If 0.0.0.0 is not chosen, and instead the default 127.0.0.1
# is left, then Django will not listen in the container's
# virtual network interface and so the connection will not
# be exposed up to the compose virtual network and to the
# host mapping.
CMD python manage.py runserver 0.0.0.0:8000