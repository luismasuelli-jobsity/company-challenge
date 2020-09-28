(function($) {
    $.fn.serializeObject = $.fn.serializeObject || function()  {
        let o = {};
        let a = this.serializeArray();
        $.each(a, function() {
            if (o[this.name]) {
                if (!o[this.name].push) {
                    o[this.name] = [o[this.name]];
                }
                o[this.name].push(this.value || '');
            } else {
                o[this.name] = this.value || '';
            }
        });
        return o;
    };

    window.Chat = {
        // Token-related utility functions start here.

        /**
         * Sets the token into the local storage.
         */
        setToken: function(token) {
            window.localStorage.setItem('token', token);
        },
        /**
         * Retrieves the token from the local storage.
         */
        getToken: function() {
            return window.localStorage.getItem('token');
        },
        /**
         * Clears the token from the local storage.
         */
        clearToken: function() {
            window.localStorage.removeItem('token');
        },

        // Session-related auxiliary functions start here.

        /**
         * Gets the current profile, if any. This, given
         * the current token. It will return 401 if not
         * authenticated, which is useful to update the
         * front-end.
         */
        me: function() {
            return $.get('/profile', null, 'json');
        },
        /**
         * Performs a log-in with the current username and
         *   password. The ajax query request
         * @param username The account username.
         * @param password The account password.
         */
        login: function(username, password) {
            return $.post('/login', {
                username: username,
                password: password
            }, null, 'json');
        },
        /**
         * Performs the registration of a new user account
         *   given username, email, and password.
         * @param username The account username.
         * @param email The account e-mail address.
         * @param password The account password.
         */
        register: function(username, email, password) {
            return $.post('/register', {
                username: username,
                email: email,
                password: password
            }, null, 'json');
        },
        /**
         * Performs a logout of the current account.
         */
        logout: function() {
            return $.post('/logout', null, 'json');
        },

        // Socket-related utility functions start here.

        // The current socket.
        _socket: null,

        // Utility function to send a json message.
        _send: function(obj) {
            this._socket.send(JSON.stringify(obj));
        },

        /**
         * Connects to the chat server.
         */
        connect: function() {
            let ctx = this;

            if (ctx._socket) throw new ChatError("The connection is already established", "already-connected");

            let connection = new WebSocket("ws://" + window.location.host + "/ws/chat/?token=" + ctx.getToken());
            connection.onopen = function(e) {
                console.log("Connection started...", e);
                ctx._socket = this;
                ctx.Incoming.onopen();
            };
            connection.onmessage = function(e) {
                let message = JSON.parse(e.data);
                console.log("Receiving message:", message);
                switch(message.type) {
                    case "fatal":
                        ctx.Incoming.onfatal(message.code);
                        break;
                    case "error":
                        ctx.Incoming.onerror(message.code, message.details);
                        break;
                    default:
                        switch(message.code) {
                            case "list":
                                ctx.Incoming.onlist(message.list);
                                break;
                            case "users":
                                ctx.Incoming.onusers(message.room_name);
                                break;
                            case "message":
                                ctx.Incoming.onmessage(message.room_name, message.stamp, message.user, message.you, message.body);
                                break;
                            case "custom":
                                ctx.Incoming.oncustom(message.room_name, message.stamp, message.user, message.you, message.command, message.payload);
                                break;
                            case "joined":
                                ctx.Incoming.onjoin(message.room_name, message.stamp, message.user, message.you, message.status);
                                break;
                            case "parted":
                                ctx.Incoming.onpart(message.room_name, message.stamp, message.user, message.you);
                                break;
                        }
                }
            };
            connection.onclose = function(e) {
                console.log("closing connection...", e);
                ctx._socket = null;
            };
            connection.onerror = function(m) {
                console.log("Websocket error:", m);
                ctx.Incoming.onfatal("websocket");
            };
        },
        /**
         * Disconnects the chat.
         */
        disconnect: function() {
            if (!this._socket) throw new ChatError("The connection is not established", "not-connected");
        },
        /**
         * Tells whether a connection is established.
         */
        connected: function() {
            return !!this._socket;
        },
        /**
         * Requests a list of the available channels.
         */
        list: function() {
            if (!this._socket) throw new ChatError("The connection is not established", "not-connected");

            this._send({type: "list"});
        },
        /**
         * Requests to join to a channel.
         */
        join: function(roomName) {
            if (!this._socket) throw new ChatError("The connection is not established", "not-connected");

            this._send({type: "join", room_name: roomName});
        },
        /**
         * Requests to leave to a channel.
         */
        part: function(roomName) {
            if (!this._socket) throw new ChatError("The connection is not established", "not-connected");

            this._send({type: "part", room_name: roomName});
        },
        /**
         * Requests to broadcast a message.
         */
        talk: function(roomName, content) {
            if (!this._socket) throw new ChatError("The connection is not established", "not-connected");

            this._send({type: "message", room_name: roomName, body: content});
        },
        /**
         * Requests to broadcast a message.
         */
        custom: function(roomName, command, payload) {
            if (!this._socket) throw new ChatError("The connection is not established", "not-connected");

            this._send({type: "custom", room_name: roomName, command: command, payload: payload});
        },

        // This part stands for the received messages
        // Each callback must be assigned on its own.

        Incoming: {
            onopen: function() {},
            onerror: function(code, details) {},
            onfatal: function(code) {},
            onlist: function(roomList) {},
            onusers: function(roomName, users) {},
            onhistorymessage: function(roomName, stamp, username, you, body) {},
            onmessage: function(roomName, stamp, username, you, body) {},
            oncustom: function(roomName, stamp, username, you, command, payload) {},
            onjoin: function(roomName, stamp, username, you, status) {},
            onpart: function(roomName, stamp, username, you) {}
        }
    };

    $(function() {
        // Pre-sets the token on each ajax request, if available.
        $(document).ajaxSend(function(e, xhr, opts) {
            let token = Chat.getToken();
            if (token) xhr.setRequestHeader('Authorization', 'Token ' + token);
        });
    });
})(jQuery);
