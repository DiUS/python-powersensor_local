"""An interface for accessing the event stream from a Powersensor plug."""
import asyncio
import json
import socket
import sys

from pathlib import Path
PROJECT_ROOT = str(Path(__file__).parents[1])
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

# pylint: disable=C0413
from powersensor_local.async_event_emitter import AsyncEventEmitter

# pylint: disable=R0902
# @todo: dream up a base class for PlugListener that TCP/UDP subclass
class PlugListenerUdp(AsyncEventEmitter, asyncio.DatagramProtocol):
    """An interface class for accessing the event stream from a single plug.
    The following events may be emitted:
      - ("connecting")   Whenever a connection attempt is made.
      - ("connected")    When a connection is successful.
      - ("disconnected") When a connection is dropped, be it intentional or not.
      - ("message",{...}) For each event message received from the plug. The
      plug's JSON message is decoded into a dict which is passed as the second
      argument to the registered event handler(s).
      - ("malformed",line) If JSON decoding of a message fails. The raw line
      is included (as a byte string).

      The event handlers must be async.
    """

    def __init__(self, ip, port=49476):
        """
        Create a :class:`PlugListenerUdp` bound to the given IP address.

        Parameters
        ----------
        ip : str
            The IPv4 or IPv6 address of the plug to listen to.
        port : int, optional
            UDP port used by the plug (default ``49476``).
        """
        super().__init__()
        self._ip = ip
        self._port = port
        self._backoff = 0               # exponential backoff
        self._transport = None          # UDP transport/socket
        self._reconnect = None          # reconnect timer
        self._inactive = None           # inactivity timer
        self._disconnecting = False     # disconnecting flag
        self._was_connected = False     # 'disconnected' event armed?

    def connect(self):
        """Initiates the connection to the plug. The object will automatically
        retry as necessary if/when it can't connect to the plug, until such
        a time disconnect() is called."""
        self._disconnecting = False
        self._backoff = 0
        if self._transport is None:
            asyncio.create_task(self._do_connection())

    async def disconnect(self):
        """Goes through the disconnection process towards a plug. No further
        automatic reconnects will take place, until connect() is called."""
        self._disconnecting = True

        await self._close_connection()

    async def _close_connection(self, unsub = True):
        if self._reconnect is not None:
            self._reconnect.cancel()
            self._reconnect = None

        if self._inactive is not None:
            self._inactive.cancel()
            self._inactive = None

        if self._transport is not None:
            if unsub:
                self._transport.sendto(b'subscribe(0)\n')
            self._transport.close()
            self._transport = None

        if self._was_connected:
            await self.emit('disconnected')
        self._was_connected = False

        if not self._disconnecting:
            await self._do_connection()

    def _retry(self):
        self._reconnect = None
        asyncio.create_task(self._do_connection())

    async def _do_connection(self):
        if self._disconnecting:
            return
        if self._backoff < 9:
            self._backoff += 1
        await self.emit('connecting')
        loop = asyncio.get_running_loop()
        await loop.create_datagram_endpoint(
            self.protocol_factory,
            family = socket.AF_INET,
            remote_addr = (self._ip, self._port))
        self._reconnect = loop.call_later(
            min(5*60, 2**self._backoff + 2), self._retry) # noqa

    def _send_subscribe(self):
        if self._transport is not None:
            self._transport.sendto(b'subscribe(60)\n')

    def _on_inactivity(self):
        asyncio.create_task(self._close_connection())

    # DatagramProtocol support below

    def protocol_factory(self):
        """UDP protocol factory for self."""
        return self

    def connection_made(self, transport):
        self._transport = transport
        self._send_subscribe()

    def datagram_received(self, data, addr):
        if self._reconnect is not None:
            self._reconnect.cancel()
            self._reconnect = None
            self._backoff = 0
            asyncio.create_task(self.emit('connected'))

        if not self._was_connected:
            self._was_connected = True

        if self._inactive is not None:
            self._inactive.cancel()
        loop = asyncio.get_running_loop()
        self._inactive = loop.call_later(60, self._on_inactivity) # noqa

        lines = data.decode('utf-8').splitlines()
        for line in lines:
            try:
                message = json.loads(line)
                typ = message['type']
                if typ == 'subscription':
                    if message['subtype'] == 'warning':
                        self._send_subscribe()
                elif typ == 'discovery':
                    pass
                else:
                    asyncio.create_task(self.emit('message', message))
            except json.decoder.JSONDecodeError:
                asyncio.create_task(self.emit('malformed', data))

    def error_received(self, exc):
        asyncio.create_task(self._close_connection(False))

    def connection_lost(self, exc):
        if self._transport is not None:
            asyncio.create_task(self._close_connection(False))

    @property
    def port(self):
        """Return the TCP port this listener is bound to."""
        return self._port

    @property
    def ip(self):
        """Return the IP address this listener is bound to."""
        return self._ip
