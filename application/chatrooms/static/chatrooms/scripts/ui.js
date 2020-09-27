(function($) {
    window.ChatUI = {
        // The parent UI object where all the magic happens.
        _parent: null,

        // Status of the ui: closed, opening, open.
        _status: 'closed',

        start: function(parent, onfatal) {
            let ctx = this;
            if (this._status === 'closed') {
                this._roomsSidebar = $('<div/>').addClass('rooms-sidebar');
                this._rooms = {};
                this._roomLinks = {};
                this._activeRoom = '';
                this._messageBar = $('<div/>').addClass('message');
                this._parent = parent;
                this._parent.append(this._messageBar).append(this._roomsSidebar);
                Chat.Incoming.onopen = function() {
                    ctx._status = 'open';
                    ctx._initServerLogsAndSidebar();
                    ctx._initMessageBar();
                    // Also, manually invoke to retrieve the rooms list.
                    Chat.list();
                };
                Chat.Incoming.oncustom = ctx._commandReceived.bind(ctx);
                Chat.Incoming.onjoin = ctx._joinedRoom.bind(ctx);
                Chat.Incoming.onpart = ctx._partedRoom.bind(ctx);
                Chat.Incoming.onusers = ctx._listUsers.bind(ctx);
                Chat.Incoming.onlist = ctx._listRooms.bind(ctx);
                Chat.Incoming.onmessage = ctx._messageReceived.bind(ctx);
                Chat.Incoming.onhistorymessage = ctx._historyMessageReceived.bind(ctx);
                Chat.Incoming.onerror = ctx._errorReceived.bind(ctx);
                Chat.Incoming.onfatal = function(code) {
                    if (code === "not-authenticated") {
                        onfatal(code, "You're not authenticated");
                    } else if (code === "already-chatting") {
                        onfatal(code, "This account is already chatting");
                    } else if (code === "websocket") {
                        onfatal(code, "A websocket error - check your console for more details");
                    }
                };
                this._status = 'opening';
                Chat.connect();
            }
        },

        _initMessageBar: function() {
            let ctx = this;
            this._messageBarText = $('<input type="text" placeholder="Write your message..." />');
            this._messageBar.append(this._messageBarText);
            this._messageBarButton = $('<button class="btn btn-sm btn-primary">Send</button>').css('font-size', '10px');
            this._messageBar.append(this._messageBarButton);
            this._messageBarButton.click(function() {
                // Sends the text only if the non-server tab is
                // chosen and only if the trimmed text is not empty.
                // The textbox is then cleared.

                let value = ctx._messageBarText.val().trim();
                ctx._messageBarText.val('');
                if (!value) return;

                if (ctx._activeRoom) {
                    if (value[0] === '/') {
                        let parts = value.substr(1).split('=');
                        if (parts.length >= 2) {
                            Chat.custom(ctx._activeRoom, parts[0], parts.slice(1).join('='));
                        } else {
                            Chat.talk(ctx._activeRoom, value)
                        }
                    } else {
                        Chat.talk(ctx._activeRoom, value);
                    }
                }
            });
            this._messageBarText.keyup(function(e) {
                if (e.which === 13) ctx._messageBarButton.click();
            })
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
        _joinedRoom: function(roomName, stamp, username, you, status) {
            if (you) {
                if (this._rooms[roomName]) {
                    this._rooms[roomName].remove();
                    delete this._rooms[roomName];
                }

                let room = $('<div class="room"><div class="messages"></div><div class="users"></div></div>');
                room.append(
                    $('<div class="caption"></div>').append("Room: " + roomName).append(
                        $('<a href="#" style="margin-left: 8px">Leave</a>').click(function() {
                            Chat.part(roomName)
                        })
                    )
                );
                room.hide();
                this._parent.append(room);
                this._rooms[roomName] = room;
                this._listUsers(roomName, status.users);
                this._historyMessageReceived(roomName, status.messages);
                this._selectActiveRoom(roomName);
                this._roomLinks[roomName].addClass('joined');
            } else {
                // Add the user to the users set of the room.
                this._rooms[roomName].data('users')[username] = false;
            }
            this._refreshUsers(roomName);

            let messages = this._rooms[roomName].find(".messages");
            messages.append(
                $('<div/>').append(
                    $('<span class="stamp" />').text(stamp)
                ).append(
                    $('<span class="author" />').text(username + (you ? ' (you)' : ''))
                ).append(
                    $('<span class="join" />').text('joined the room')
                )
            );
            messages.scrollTop(messages.prop("scrollHeight"));
        },

        // Handles parting from a room.
        _partedRoom: function(roomName, stamp, username, you) {
            if (you) {
                if (this._rooms[roomName]) {
                    this._rooms[roomName].remove();
                    this._roomLinks[roomName].removeClass('joined');
                    delete this._rooms[roomName];
                    this._selectActiveRoom('');
                }
            } else {
                // Add the user to the users set of the room.
                delete this._rooms[roomName].data('users')[username];
                this._refreshUsers(roomName);
                let messages = this._rooms[roomName].find(".messages");
                messages.append(
                    $('<div/>').append(
                        $('<span class="stamp" />').text(stamp)
                    ).append(
                        $('<span class="author" />').text(username + (you ? ' (you)' : ''))
                    ).append(
                        $('<span class="part" />').text('left the room')
                    )
                );
                messages.scrollTop(messages.prop("scrollHeight"));
            }
        },

        // Handles receiving a custom command message.
        _commandReceived: function(roomName, stamp, username, you, command, payload) {
            let messages = this._rooms[roomName].find(".messages");
            messages.append(
                $('<div/>').append(
                    $('<span class="stamp" />').text(stamp)
                ).append(
                    $('<span class="author" />').text(username + (you ? ' (you)' : ''))
                ).append(
                    $('<span class="command" />').text("/" + command + '=' + payload)
                )
            );
            messages.scrollTop(messages.prop("scrollHeight"));
        },

        // Handles receiving a message.
        _messageReceived: function(roomName, stamp, username, you, body) {
            let messages = this._rooms[roomName].find(".messages");
            messages.append(
                $('<div/>').append(
                    $('<span class="stamp" />').text(stamp)
                ).append(
                    $('<span class="author" />').text(username + (you ? ' (you)' : ''))
                ).append(
                    $('<span class="message" />').text(body)
                )
            );
            messages.scrollTop(messages.prop("scrollHeight"));
        },

        // Handles receiving a history message.
        _historyMessageReceived: function(roomName, messagesList) {
            let ctx = this;
            let messages = this._rooms[roomName].find(".messages");
            messagesList.forEach(function(message) {
                messages.prepend(
                    $('<div/>').append(
                        $('<span class="stamp" />').text(message.stamp)
                    ).append(
                        $('<span class="author" />').text(message.user + (message.you ? ' (you)' : ''))
                    ).append(
                        $('<span class="message" />').text(message.body)
                    )
                );
            });
            messages.scrollTop(messages.prop("scrollHeight"));
        },

        // Handles receiving the rooms list.
        _listRooms: function(roomList) {
            let ctx = this;
            this._roomLinks = {};
            this._roomsSidebar.find('.room-item').remove();
            roomList.forEach(function(room) {
                let roomLink = new $('<div class="room-item" />').text(room.name);
                if (room.joined) roomLink.addClass('joined');
                ctx._roomsSidebar.append(roomLink);
                ctx._roomLinks[room.name] = roomLink;
                roomLink.click(function() {
                    if (!ctx._rooms[room.name]) {
                        Chat.join(room.name);
                    } else {
                        ctx._selectActiveRoom(room.name);
                    }
                });
            });
            this._rooms[''].append(
                $('<div class="info" />').append("Room list successfully updated")
            );
            this._rooms[''].scrollTop(this._rooms[''].prop("scrollHeight"));
        },

        // Handles receiving the users list.
        _listUsers: function(roomName, users) {
            let room = this._rooms[roomName];
            let usersSet = {};
            users.forEach(function(user) {
                usersSet[user.name] = users.you;
            });
            room.data('users', usersSet);
        },

        // Refreshes the users in the room.
        _refreshUsers: function(roomName) {
            let room = this._rooms[roomName];
            let users = this._rooms[roomName].data('users');
            let usersList = room.find('.users');
            usersList.empty();
            Object.keys(users).sort().forEach(function(username) {
                let entry = $('<div class="user"/>').text(username);
                if (users[username]) entry.addClass("you");
                usersList.append(entry);
            });
        },

        // Handles receiving an error.
        _errorReceived: function(code, details) {
            this._selectActiveRoom('');
            this._rooms[''].append(
                $('<div class="error" />').append("Error code: " + code + ' - details: ' + JSON.stringify(details))
            );
            this._rooms[''].scrollTop(this._rooms[''].prop("scrollHeight"));
        },

        // Stops the socket.
        stop: function() {
            if (this._status !== 'closed') {
                if (Chat.connected()) Chat.disconnect();
                Chat.Incoming.oncustom = function(roomName, stamp, username, you, command, payload) {};
                Chat.Incoming.onjoin = function(roomName, stamp, username, you, status) {};
                Chat.Incoming.onpart = function(roomName, stamp, username, you) {};
                Chat.Incoming.onusers = function(roomName, users) {};
                Chat.Incoming.onlist = function(roomList) {};
                Chat.Incoming.onmessage = function(roomName, stamp, username, you, body) {};
                Chat.Incoming.onhistorymessage = function(roomName, stamp, username, you, body) {};
                Chat.Incoming.onerror = function(code, details) {};
                this._parent.empty();
                this._parent = null;
                this._rooms = {};
                this._roomLinks = {};
                this._status = 'closed';
            }
        }
    }
})(jQuery);