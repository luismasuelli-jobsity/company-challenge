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

        model = Message

        def has_add_permission(self, request, obj):
            return False

        def has_change_permission(self, request, obj=None):
            return obj is None

        def has_delete_permission(self, request, obj=None):
            return False

        max_num = 50
        extra = 0
        ordering = ["-created_on"]

    list_display = ["created_on", "updated_on", "name"]
    ordering = ["name"]
    inlines = [InlineMessageAdmin]


class MessageAdmin(ModelAdmin):
    """
    Allows a lookup of a message by its content.
    """

    list_display = ["created_on", "user", "room", "content"]
    list_display_links = ["created_on"]
    search_fields = ["content"]
    ordering = ["created_on"]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return obj is None


# Register your models here.
site.register(Room, RoomAdmin)
site.register(Message, MessageAdmin)