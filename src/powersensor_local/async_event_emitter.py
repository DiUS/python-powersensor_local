class AsyncEventEmitter:
    """Small helper class for pub/sub functionality with async handlers."""
    def __init__(self):
        self._listeners = {}

    def subscribe(self, evstr, cb):
        """Registers an event handler for the given event key. The handler must
        be async. Duplicate registrations are ignored."""
        if self._listeners.get(evstr) is None:
            self._listeners[evstr] = []
        if not cb in self._listeners[evstr]:
            self._listeners[evstr].append(cb)

    def unsubscribe(self, evstr, cb):
        """Unregisters the given event handler from the given event type."""
        if self._listeners.get(evstr) is None:
            return
        if cb in self._listeners[evstr]:
            self._listeners[evstr].remove(cb)

    async def emit(self, evstr, *args):
        """Emits an event to all registered listeners for that event type.
        Additional arguments may be supplied with event as appropriate. Each
        event handler is awaited before delivering the event to the next."""
        if self._listeners.get(evstr) is None:
            return
        for cb in self._listeners[evstr]:
            await cb(evstr, *args)
