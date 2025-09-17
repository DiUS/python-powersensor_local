import asyncio
import json

import sys
from pathlib import Path

project_root = str(Path(__file__).parents[1])
if project_root not in sys.path:
    sys.path.append(project_root)

from powersensor_local.async_event_emitter import AsyncEventEmitter


async def _send_subscribe(writer):
    writer.write(b'subscribe(60)\n')
    await writer.drain()


class PlugListener(AsyncEventEmitter):
    """An interface class for accessing the event stream from a single plug.
    The following events may be emitted:
      - ("connecting")   Whenever a connection attempt is made.
      - ("connected")    When a connection is successful.
      - ("disconnected") When a connection is dropped, be it intentional or not.
      - ("message",{...}) For each event message received from the plug. The
      plug's JSON message is decoded into a dict which is passed as the second
      argument to the registered event handler(s). The event handlers must be
      async.
    """

    def __init__(self, ip, port=49476):
        """Initialises a PlugListener object, bound to the given IP address.
        The port number may be overridden if necessary."""
        super().__init__()
        self._ip = ip
        self._port = port
        self._task = None
        self._connection = None
        self._disconnecting = False

    def connect(self):
        """Initiates the connection to the plug. The object will automatically
        retry as necessary if/when it can't connect to the plug, until such
        a time disconnect() is called."""
        if self._task is not None:
            raise RuntimeError("already connected/connecting")
        self._disconnecting = False
        self._task = asyncio.create_task(self._do_connection())

    async def disconnect(self):
        """Goes through the disconnection process towards a plug. No further
        automatic reconnects will take place, until connect() is called."""
        if self._task is None:
            return

        self._disconnecting = True

        await self._close_connection()

        if self._task is not None:
            await self._task
            self._task = None

    async def _close_connection(self):
        if self._connection is not None:
            (reader, writer) = self._connection
            self._connection = None

            writer.close()
            await writer.wait_closed()

            await self.emit('disconnected')

    async def _do_connection(self, backoff = 0):
        if backoff < 9:
            backoff += 1
        try:
            await self.emit('connecting')
            reader, writer = await asyncio.open_connection(self._ip, self._port)
            self._connection = (reader, writer)

            await _send_subscribe(writer)
            backoff = 1

            await self.emit('connected')

            while not self._disconnecting:
                await self._process_line(reader, writer)

        except (ConnectionResetError, asyncio.TimeoutError):
            # Handle disconnection and retry with exponential backoff
            await self._close_connection()
            if self._disconnecting:
                return None
            await asyncio.sleep(min(5 * 60, 2**backoff * 1))
            return await self._do_connection(backoff)

    async def _process_line(self, reader, writer):
        data = await reader.readline()
        if data == b'':
            raise ConnectionResetError
        if data != b'\n': # Silently ignore empty lines
            try:
                message = json.loads(data.decode('utf-8'))
                typ = message['type']
                if typ == 'subscription':
                    if message['subtype'] == 'warning':
                        await _send_subscribe(writer)
                elif typ == 'discovery':
                    pass
                else:
                    await self.emit('message', message)
            except json.decoder.JSONDecodeError as ex:
                print(f"JSON error {ex} from {data}")
