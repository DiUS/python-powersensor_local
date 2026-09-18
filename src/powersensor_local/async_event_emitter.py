"""Small helper class for pub/sub functionality with async handlers."""
import logging
from typing import Callable

class AsyncEventEmitter:
    """Small helper class for pub/sub functionality with async handlers.
    An optional Logger can be provided, which will be used to log any
    unhandled exceptions."""
    def __init__(self, logger: logging.Logger | None = None):
        self._listeners: dict[str,list[Callable]] = {}
        self._logger = logger

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
        to an 'exception' event being emitted. If no 'exception' listener
        is registered, or an exception handler callback raises an exception,
        the exception is logged (if a logger was provided), and discarded."""
        if self._listeners.get(event_name) is None:
            return
        for callback in self._listeners[event_name]:
            try:
                await callback(event_name, *args)
            except Exception as e:
              if 'exception' not in self._listeners:
                if self._logger is not None:
                  self._logger.exception(f"Discarding unhandled exception: {e}")
              else:
                for handler in self._listeners['exception']:
                  try:
                    await handler('exception', e)
                  except Exception as e2:
                    if self._logger is not None:
                      self._logger.exception(f"Exception handling callback raised an exception itself, discarding it: {e2}")
