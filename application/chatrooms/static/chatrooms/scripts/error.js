function ChatError(message, code, details, filename, line) {
    Error.call(this, message, filename, line);
    this.code = code;
    this.message = message;
}

ChatError.prototype = Object.create(Error.prototype, {
    constructor: {
        value: Error,
        enumerable: false,
        writable: true,
        configurable: true
    }
});

if (Object.setPrototypeOf){
    Object.setPrototypeOf(ChatError, Error);
} else {
    ChatError.__proto__ = Error;
}