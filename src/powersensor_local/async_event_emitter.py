"""Small helper class for pub/sub functionality with async handlers."""
from typing import Callable

class AsyncEventEmitter:
    """Small helper class for pub/sub functionality with async handlers."""
    def __init__(self):
        self._listeners = {}

    def subscribe(self, event_name: str, callback: Callable):
        """Registers an event handler for the given event key. The handler must
        be async. Duplicate registrations are ignored."""
        if self._listeners.get(event_name) is None:
            self._listeners[event_name] = []
        if not callback in self._listeners[event_name]:
            self._listeners[event_name].append(callback)

    def unsubscribe(self, event_name: str, callback: Callable):
        """Unregisters the given event handler from the given event type."""
        if self._listeners.get(event_name) is None:
            return
        if callback in self._listeners[event_name]:
            self._listeners[event_name].remove(callback)

    async def emit(self, event_name: str, *args):
        """Emits an event to all registered listeners for that event type.
        Additional arguments may be supplied with event as appropriate. Each
        event handler is awaited before delivering the event to the next.
        If an event handler raises an exception, this is funneled through
        to an 'exception' event being emitted. This can chain."""
        if self._listeners.get(event_name) is None:
            return
        for callback in self._listeners[event_name]:
            try:
                await callback(event_name, *args)
            except BaseException as e: # pylint: disable=W0718
                await self.emit('exception', e)
