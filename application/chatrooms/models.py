from django.core.validators import RegexValidator
from django.db import models


class Room(models.Model):
    """
    Chat rooms have only its name as relevant value.
    """

    created_on = models.DateTimeField(auto_now_add=True, editable=False)
    updated_on = models.DateTimeField(auto_now=True, editable=False)
    name = models.CharField(max_length=50, validators=[RegexValidator("^[a-zA-Z][a-zA-Z0-9_]?(-[a-zA-Z0-9_]+)*$")])


# User model: It will plainly be auth.User


class Message(models.Model):
    """
    These messages exist as a log, and will be restored
      when the server is started, in a per-channel basis.
    """

    created_on = models.DateTimeField(auto_now_add=True, editable=False)
    user = models.ForeignKey('auth.User', on_delete=models.PROTECT)
    room = models.ForeignKey(Room, on_delete=models.PROTECT)
    content = models.CharField(max_length=512)
