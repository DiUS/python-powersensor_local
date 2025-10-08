import sys
from pathlib import Path
project_root = str(Path(__file__).parents[1])
if project_root not in sys.path:
    sys.path.append(project_root)

from powersensor_local.async_event_emitter import AsyncEventEmitter
from powersensor_local.plug_listener_tcp import PlugListenerTcp
from powersensor_local.plug_listener_udp import PlugListenerUdp
from powersensor_local.xlatemsg import translate_raw_message

class PlugApi(AsyncEventEmitter):
    """
    The primary interface to access the interpreted event stream from a plug.

    The plug may be relaying messages from one or more sensors, in addition
    to its own reports.

    Acts as an AsyncEventEmitter. Events which can be registered for are
    documented in xlatemsg.translate_raw_message.
    """

    def __init__(self, mac, ip, port=49476, proto='udp'):
        """
        Instantiates a new PlugApi for the given plug.

        Args:
          - mac: The MAC address of the plug (typically found in the "id" field
            in the mDNS/ZeroConf discovery).
          - ip: The IP address of the plug.
          - port: The port number of the API service on the plug.
          - proto: One of 'udp' or 'tcp'.
        """
        super().__init__()
        self._mac = mac
        if proto == 'udp':
            self._listener = PlugListenerUdp(ip, port)
        elif proto == 'tcp':
            self._listener = PlugListenerTcp(ip, port)
        else:
            raise ValueError(f'Unsupported proto: {proto}')
        self._listener.subscribe('message', self._on_message)
        self._listener.subscribe('exception', self._on_exception)
        self._seen = set()

    def connect(self):
        """
        Initiates a connection to the plug.

        Will automatically retry on failure or if the connection is lost,
        until such a time disconnect() is called.
        """
        self._listener.connect()

    async def disconnect(self):
        """Disconnects from the plug and stops further connection attempts."""
        await self._listener.disconnect()

    async def _on_message(self, _, message):
        """Translates the raw message and emits the resulting messages, if any.

        Also synthesises 'now_relaying_for' messages as needed.
        """
        evs = None
        try:
            evs = translate_raw_message(message, self._mac)
        except KeyError:
            # Ignore malformed messages
            return

        msgmac = message.get('mac')
        if msgmac != self._mac and msgmac not in self._seen:
            self._seen.add(msgmac)
            # We want to emit this prior to events with data
            ev = {
                'mac': msgmac,
                'device_type': message.get('device'),
                'role': message.get('role'),
            }
            await self.emit('now_relaying_for', ev)

        for name, ev in evs.items():
            await self.emit(name, ev)

    async def _on_exception(self, _, e):
        """Propagates exceptions from the plug listener."""
        await self.emit('exception', e)
