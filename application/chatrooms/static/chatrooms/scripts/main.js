var Chat = {
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
        return $.get('/profile');
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
        });
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
        });
    },
    /**
     * Performs a logout of the current account.
     */
    logout: function() {
        return $.post('/logout');
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
        var ctx = this;

        if (ctx._socket) throw new ChatError("The connection is already established", "already-connected");

        var connection = new WebSocket("/ws/chat?token=" + ctx.getToken());
        connection.onopen = function(e) {
            ctx._socket = connection;
        };
        connection.onmessage = function(message) {
            var data = JSON.parse(e.data);
            switch(message.type) {
                case "error":
                    ctx.Incoming.onerror(message);
                    break;
                default:
                    switch(message.code) {
                        case "list":
                            ctx.Incoming.onlist(message.list);
                            break;
                        case "messages":
                            message.messages.forEach(function(msg) {
                                ctx.Incoming.onmessage(msg.room_name, msg.stamp, msg.user, msg.you, msg.body);
                            });
                            break;
                        case "message":
                            ctx.Incoming.onmessage(message.room_name, message.stamp, message.user, message.you, message.body);
                            break;
                        case "custom":
                            ctx.Incoming.oncustom(message.room_name, message.stamp, message.user, message.you, message.command, message.payload);
                            break;
                        case "joined":
                            ctx.Incoming.onjoin(message.room_name, message.stamp, message.user, message.you);
                            break;
                        case "parted":
                            ctx.Incoming.onpart(message.room_name, message.stamp, message.user, message.you);
                            break;
                    }
            }
        };
        connection.onclose = function() {
            ctx._socket = null;
        };
        connection.onerror = function() {
            ctx.Incoming.onerror(null);
        };
    },
    /**
     * Requests a list of the available channels.
     */
    list: function() {
        var ctx = this;

        if (!ctx._socket) throw new ChatError("The connection is not established", "not-connected");

        ctx._socket.send({type: "list"});
    },
    /**
     * Requests to join to a channel.
     */
    join: function(roomName) {
        var ctx = this;

        if (!ctx._socket) throw new ChatError("The connection is not established", "not-connected");

        ctx._socket.send({type: "join", room_name: roomName});
    },
    /**
     * Requests to leave to a channel.
     */
    part: function(roomName) {
        var ctx = this;

        if (!ctx._socket) throw new ChatError("The connection is not established", "not-connected");

        ctx._socket.send({type: "part", room_name: roomName});
    },
    /**
     * Requests to broadcast a message.
     */
    talk: function(roomName, content) {
        var ctx = this;

        if (!ctx._socket) throw new ChatError("The connection is not established", "not-connected");

        ctx._socket.send({type: "part", room_name: roomName, body: content});
    },
    /**
     * Requests to broadcast a message.
     */
    custom: function(roomName, command, payload) {
        var ctx = this;

        if (!ctx._socket) throw new ChatError("The connection is not established", "not-connected");

        ctx._socket.send({type: "part", room_name: roomName, command: command, payload: payload});
    },

    // This part stands for the received messages
    // Each callback must be assigned on its own.

    Incoming: {
        onerror: function(msg) {},
        onlist: function(roomList) {},
        onmessage: function(roomName, stamp, username, you, body) {},
        oncustom: function(roomName, stamp, username, you, command, payload) {},
        onjoin: function(roomName, stamp, username, you) {},
        onpart: function(roomName, stamp, username, you) {}
    }
};


$(function() {
    // Pre-sets the token on each ajax request, if available.
    $(document).ajaxSend(function(e, xhr, _) {
        var token = Chat.getToken();
        if (token) xhr.setRequestHeader('Authorization', token);
    });
});