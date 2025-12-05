"""The legacy alternative to using mDNS discovery."""
import asyncio
import json
import socket

PORT = 49476

class LegacyDiscovery(asyncio.DatagramProtocol):
    """The legacy alternative to using mDNS discovery."""

    def __init__(self, broadcast_addr = '<broadcast>'):
        """Initialises a new discovery object.
        Optionally takes a specific broadcast address to use.
        """
        super().__init__()
        self._dst_addr = broadcast_addr
        self._found = {}

    async def scan(self, timeout_sec = 2.0):
        """Scans the local network for discoverable devices.
        Returns the list of devices found, with each device represented
        in the format:

        {
          "ip": "n.n.n.n",
          "id": "aabbccddeeff",
        }
        """
        self._found = {}

        loop = asyncio.get_running_loop()
        transport, _ = await loop.create_datagram_endpoint(
            self.protocol_factory,
            family = socket.AF_INET,
            local_addr=('0.0.0.0', 0)
        )
        sock = transport.get_extra_info('socket')
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        message = b'discover()\n'
        while timeout_sec > 0:
            transport.sendto(message, (self._dst_addr, PORT))
            await asyncio.sleep(0.5)
            timeout_sec -= 0.5

        transport.close()
        return list(self._found.values())

    def protocol_factory(self):
        """UDP protocol factory."""
        return self

    def datagram_received(self, data, addr):
        try:
            response = json.loads(data.decode('utf-8'))
            ip = response['ip']
            mac = response['mac']
            self._found[mac] = { "ip": ip, "id": mac }
        except (json.JSONDecodeError, KeyError):
            pass
