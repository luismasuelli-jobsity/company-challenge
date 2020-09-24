from django.contrib.admin import site, ModelAdmin, TabularInline
from .models import Room, Message


class RoomAdmin(ModelAdmin):
    """
    Just a name display and its date(s).
    """

    class InlineMessageAdmin(TabularInline):
        """
        Shows the last messages in the room.
        """

    list_display = ["created_on", "updated_on", "name"]
    ordering = ["name"]
    inlines = []


class MessageAdmin(ModelAdmin):
    """
    Allows a lookup of a message by its content.
    """

    list_display = ["created_on", "user", "room" "content"]
    list_display_links = ["created_on"]
    search_fields = ["content"]
    ordering = ["created_on"]


# Register your models here.
site.register(Room, RoomAdmin)
site.register(Message, Message)