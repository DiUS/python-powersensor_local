import asyncio
import json
import socket
import time

PORT = 49476
DISCOVERY_TIMEOUT_S = 2

class PowersensorListener(asyncio.DatagramProtocol):
    def __init__(self, bcast_addr='<broadcast>'):
        """Initialises a listener object.
        Optionally takes the broadcast address to use.
        """
        self._known_addresses = dict()
        self._connections = {}
        self._tasks = dict()
        self._callback = None
        self._exiting = False
        self._bcast = bcast_addr

    async def scan(self):
        """Scans the local network for discoverable devices with a timeout.
        Returns the list of IP addresses of the discovered gateways (plugs).
        """
        self._known_addresses.clear()
        loop = asyncio.get_running_loop()
        transport, _ = await loop.create_datagram_endpoint(
            self.protocol_factory,
            family=socket.AF_INET,
            local_addr=('0.0.0.0', 0))
        sock = transport.get_extra_info('socket')
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        message = 'discover()\n'.encode('utf-8')

        timeout = DISCOVERY_TIMEOUT_S
        while timeout > 0:
            transport.sendto(message, (self._bcast, PORT))
            await asyncio.sleep(0.5)
            timeout -= 0.5

        transport.close()
        return self._known_addresses.keys()

    def protocol_factory(self):
        return self

    def datagram_received(self, data, addr):
        try:
            response = json.loads(data.decode('utf-8'))
            ip = response['ip']
            self._known_addresses[ip] = response['mac']
        except (json.JSONDecodeError, KeyError):
            pass

    async def subscribe(self, callback):
        """Subscribes to updates from known devices."""
        self._callback = callback

        for ip, mac in self._known_addresses.items():
            if not self._tasks.get(ip):
                self._tasks[ip] = asyncio.create_task(
                    self._connect_to_device(ip, mac))

    async def _send_subscribe(self, writer):
        writer.write(b'subscribe(60)\n')
        await writer.drain()

    async def _processline(self, ip, mac, reader, writer):
        data = await reader.readline()
        if data != b'' and data != b'\n':
            try:
                message = json.loads(data.decode('utf-8'))
                typ = message['type']
                if typ == 'subscription':
                    if message['subtype'] == 'warning':
                        await self._send_subscribe(writer)
                elif typ == 'discovery':
                    pass
                else:
                    if message.get('device') == 'sensor':
                        message['via'] = mac
                    await self._callback(message)
            except (json.decoder.JSONDecodeError) as ex:
                print(f"JSON error {ex} from {data}")

    async def _connect_to_device(self, ip, mac, backoff=0):
        """Connects to a single device and handles reconnections."""
        backoff += 1
        try:
            reader, writer = await asyncio.open_connection(ip, PORT)
            self._connections[ip] = (reader, writer)

            await self._send_subscribe(writer)
            backoff = 1

            while not self._exiting:
                await self._processline(ip, mac, reader, writer)

        except (ConnectionResetError, asyncio.TimeoutError):
            # Handle disconnection and retry with exponential backoff
            del self._connections[ip]
            await asyncio.sleep(min(5 * 60, 2**backoff * 1))
            return await self._connect_to_device(ip, mac, backoff)

    async def unsubscribe(self):
        """Unsubscribes from all devices."""
        for (reader, writer) in self._connections.values():
            writer.close()

        self._connections = {}

    async def stop(self):
        """Disconnects from all devices."""
        self._exiting = True
        for task in self._tasks.values():
            await task
