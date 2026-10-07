"""Interface abstraction for Powersensor plugs."""
import sys

from .async_event_emitter import AsyncEventEmitter
from .plug_listener_tcp import PlugListenerTcp
from .plug_listener_udp import PlugListenerUdp
from .xlatemsg import translate_raw_message, Event, Message

class PlugApi(AsyncEventEmitter):
    """
    The primary interface to access the interpreted event stream from a plug.

    The plug may be relaying messages from one or more sensors, in addition
    to its own reports.

    Acts as an AsyncEventEmitter. Events which can be registered for are
    documented in xlatemsg.translate_raw_message.
    """

    def __init__(self, mac: str, ip: str, port: int = 49476, proto: str = 'udp'):
        """Create a :class:`PlugApi` instance for a single plug.

        Parameters
        ----------
        mac : str
            MAC address of the plug (usually found in the ``id`` field of mDNS/ZeroConf discovery).
        ip : str
            IP address assigned to the plug.
        port : int, optional
            Port number of the plug’s API service. Defaults to ``49476``.
        proto : {'udp', 'tcp'}, optional
            Protocol used for communication.  ``'udp'`` selects :class:`PlugListenerUdp`,
            while ``'tcp'`` selects :class:`PlugListenerTcp`.  Any other value raises a
            :class:`ValueError`.

        Raises
        ------
        ValueError
            If *proto* is not ``'udp'`` or ``'tcp'``.
        """
        super().__init__()
        self._mac: str = mac
        self._listener: PlugListenerUdp | PlugListenerTcp
        if proto == 'udp':
            self._listener = PlugListenerUdp(ip, port)
        elif proto == 'tcp':
            self._listener = PlugListenerTcp(ip, port)
        else:
            raise ValueError(f'Unsupported proto: {proto}')
        self._listener.subscribe('message', self._on_message)
        self._listener.subscribe('exception', self._on_exception)
        self._seen: set[str] = set()

    def connect(self) -> None:
        """
        Initiates a connection to the plug.

        Will automatically retry on failure or if the connection is lost,
        until such a time disconnect() is called.
        """
        self._listener.connect()

    async def disconnect(self) -> None:
        """Disconnects from the plug and stops further connection attempts."""
        await self._listener.disconnect()

    async def _on_message(self, _: str, message: Message) -> None:
        """Translates the raw message and emits the resulting messages, if any.

        Also synthesizes 'now_relaying_for' messages as needed.
        """
        try:
            evs = translate_raw_message(message, self._mac)
        except KeyError:
            # Ignore malformed messages
            return

        msgmac = message.get('mac')
        if msgmac is not None and msgmac != self._mac and msgmac not in self._seen:
            self._seen.add(str(msgmac))
            # We want to emit this prior to events with data
            ev: Event = {
                'mac': msgmac,
            }
            dev = message.get('device')
            if dev is not None:
              ev['device_type'] = dev
            role = message.get('role')
            if role is not None:
              ev['role'] = role
            await self.emit('now_relaying_for', ev)

        for name, ev in evs.items():
            await self.emit(name, ev)

    async def _on_exception(self, _: str, e: Exception) -> None:
        """Propagates exceptions from the plug listener."""
        await self.emit('exception', e)

    @property
    def ip_address(self) -> str:
        """
        Return the IP address provided on construction.

        Returns
        -------
        str
            The IP address configured for the listener.
        """
        return self._listener.ip

    @property
    def port(self) -> int:
        """
        Return the port number provided on construction.

        Returns
        -------
        int
            The TCP/UDP port configured for the listener.
        """
        return self._listener.port
