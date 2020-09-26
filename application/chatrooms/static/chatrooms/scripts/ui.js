(function($) {
    window.ChatUI = {
        // The parent UI object where all the magic happens.
        _parent: null,

        // Status of the ui: closed, opening, open.
        _status: 'closed',

        start: function(parent) {
            let ctx = this;
            if (this._status === 'closed') {
                this._roomsSidebar = $('<div/>').addClass('rooms-sidebar');
                this._rooms = {};
                this._roomLinks = {};
                this._activeRoom = '';
                this._messageBar = $('<div/>').addClass('message');
                this._parent = parent;
                this._parent.append(this._messageBar).append(this._roomsSidebar);
                this._initServerLogsAndSidebar();
                this._initMessageBar();
                Chat.Incoming.oncustom = ctx._commandReceived.bind(ctx);
                Chat.Incoming.onjoin = ctx._joinedRoom.bind(ctx);
                Chat.Incoming.onpart = ctx._partedRoom.bind(ctx);
                Chat.Incoming.onusers = ctx._listUsers.bind(ctx);
                Chat.Incoming.onlist = ctx._listRooms.bind(ctx);
                Chat.Incoming.onmessage = ctx._messageReceived.bind(ctx);
                Chat.Incoming.onhistorymessage = ctx._historyMessageReceived.bind(ctx);
            }
        },

        _initMessageBar: function() {
            let ctx = this;
            this._messageBarText = $('<input type="text" placeholder="Write your message..." />');
            this._messageBar.append(this._messageBarText);
            this._messageBarButton = $('<button value="Send" />');
            this._messageBar.append(this._messageBarButton);
            this._messageBarButton.click(function() {
                let value = ctx._messageBarText.val().trim();
                if (!value) return;

                if (this._activeRoom) {
                    if (value[0] === '/') {
                        let parts = value.substr(1).split('=', 2);
                        Chat.custom(this._activeRoom, value[0], value[1]);
                    } else {
                        Chat.talk(this._activeRoom, value);
                    }
                }
            });
        },

        _initServerLogsAndSidebar: function() {
            let ctx = this;
            let logs = $('<div class="server-logs" />');
            this._rooms[''] = logs;
            this._roomLinks = {};
            this._parent.append(logs);
            this._logsLink = $('<div/>').text('Server Logs').addClass('server-logs active');
            this._logsLink.click(function() {
                ctx._selectActiveRoom('');
            });
            this._roomsSidebar.append(this._logsLink);
            this._refreshLink = $('<div/>').text('Refresh rooms').addClass('reload');
            this._refreshLink.click(function() {
                Chat.list();
            });
            this._roomsSidebar.append(this._refreshLink);
        },

        _selectActiveRoom: function(roomName) {
            if (this._rooms[roomName]) {
                Object.values(this._rooms).forEach(function(v) {
                    v.hide();
                });
                this._rooms[roomName].show();
                this._roomsSidebar.find('.server-logs, .room-item').removeClass('active');
                if (roomName === '') {
                    this._logsLink.addClass('active');
                } else {
                    this._roomLinks[roomName].addClass('active');
                }
                this._activeRoom = roomName;
            }
        },

        // Handles joining a room.
        _joinedRoom: function(roomName, stamp, username, you) {
            if (you) {
                if (this._rooms[roomName]) {
                    this._rooms[roomName].remove();
                    delete this._rooms[roomName];
                }

                let room = $('<div class="room"><div class="messages"></div><div class="users"></div></div>');
                room.hide();
                this._parent.append(room);
                this._rooms[roomName] = room;
                this._selectActiveRoom(roomName);
            }

            this._rooms[roomName].find(".messages").append(
                $('<div/>').append(
                    $('<div class="stamp" />').text(stamp)
                ).append(
                    $('<div class="author" />').text(username + (you ? ' (you)' : ''))
                ).append(
                    $('<div class="join" />').text('joined the room')
                )
            );
        },

        // Handles parting from a room.
        _partedRoom: function(roomName, stamp, username, you) {
            if (you) {
                if (this._rooms[roomName]) {
                    this._rooms[roomName].remove();
                    delete this._rooms[roomName];
                }
            } else {
                this._rooms[roomName].find(".messages").append(
                    $('<div/>').append(
                        $('<div class="stamp" />').text(stamp)
                    ).append(
                        $('<div class="author" />').text(username + (you ? ' (you)' : ''))
                    ).append(
                        $('<div class="part" />').text('left the room')
                    )
                );
            }
        },

        // Handles receiving a custom command message.
        _commandReceived: function(roomName, stamp, username, you, command, payload) {
            this._rooms[roomName].find(".messages").append(
                $('<div/>').append(
                    $('<div class="stamp" />').text(stamp)
                ).append(
                    $('<div class="author" />').text(username + (you ? ' (you)' : ''))
                ).append(
                    $('<div class="part" />').text("/" + command + '=' + payload)
                )
            );
        },

        // Handles receiving a message.
        _messageReceived: function(roomName, stamp, username, you, body) {
            this._rooms[roomName].find(".messages").append(
                $('<div/>').append(
                    $('<div class="stamp" />').text(stamp)
                ).append(
                    $('<div class="author" />').text(username + (you ? ' (you)' : ''))
                ).append(
                    $('<div class="part" />').text(body)
                )
            );
        },

        // Handles receiving a history message.
        _historyMessageReceived: function(roomName, stamp, username, you, body) {
            this._rooms[roomName].find(".messages").prepend(
                $('<div/>').append(
                    $('<div class="stamp" />').text(stamp)
                ).append(
                    $('<div class="author" />').text(username + (you ? ' (you)' : ''))
                ).append(
                    $('<div class="part" />').text(body)
                )
            );
        },

        // Handles receiving the rooms list.
        _listRooms: function(roomList) {
            let ctx = this;
            this._roomLinks = {};
            this._roomsSidebar.find('.room-item').remove();
            roomList.forEach(function(room) {
                let roomLink = new $('<div class="room-item" />').text(room.name);
                if (room.joined) roomLink.addClass('joined');
                ctx._roomLinks[room.name] = roomLink;
            })
        },

        // Handles receiving the users list.
        _listUsers: function(roomName, users) {
            let usersList = this._rooms[roomName].find('.users');
            usersList.empty();
            users.forEach(function(user) {
                let entry = $('<div class="user"/>').text(user.name);
                if (user.you) entry.addClass("you");
                usersList.append(entry);
            })
        },

        // Stops the socket.
        stop: function() {
            if (this._status !== 'closed') {
                if (Chat.connected()) Chat.disconnect();
                Chat.Incoming.oncustom = function(roomName, stamp, username, you, command, payload) {};
                Chat.Incoming.onjoin = function(roomName, stamp, username, you) {};
                Chat.Incoming.onpart = function(roomName, stamp, username, you) {};
                Chat.Incoming.onusers = function(roomName, users) {};
                Chat.Incoming.onlist = function(roomList) {};
                Chat.Incoming.onmessage = function(roomName, stamp, username, you, body) {};
                Chat.Incoming.onhistorymessage = function(roomName, stamp, username, you, body) {};
                this._parent.empty();
                this._parent = null;
                this._rooms = {};
                this._roomLinks = {};
                this._status = 'closed';
            }
        }
    }
})(jQuery);